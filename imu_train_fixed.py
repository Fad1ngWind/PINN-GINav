import json
import os
import random
import sys
from collections import deque

import matplotlib
import numpy as np
import pandas as pd
import pymap3d as p3d
import pyrtklib as prl
import torch
import torch.nn.functional as F
from tqdm import tqdm

import rtk_util as util
from model import IMUFusionNet, IMUFusionNetLSTM, IMUFusionNetSmall

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def set_global_seed(seed):
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def load_gt(gt_path, add_leap=False):
    with open(gt_path, "r", encoding="utf-8") as f:
        sample = [f.readline() for _ in range(35)]

    first_data = ""
    skip_rows = 0
    for idx, line in enumerate(sample):
        text = line.strip()
        if text and not text.startswith("%") and not text.startswith("#"):
            first_data = text
            skip_rows = idx
            break

    sep = "," if "," in first_data else r"\s+"
    first_tok = first_data.split(",")[0] if "," in first_data else first_data.split()[0]
    has_header = any(ch.isalpha() for ch in first_tok)

    if has_header:
        try:
            df = pd.read_csv(gt_path, sep=sep, engine="python")
        except Exception:
            df = pd.read_csv(gt_path, engine="python")

        rename = {}
        for col in df.columns:
            name = col.lower().strip()
            if name in ("time", "timestamp", "t"):
                rename[col] = "time"
            elif name in ("lat", "latitude"):
                rename[col] = "lat"
            elif name in ("lon", "lng", "longitude"):
                rename[col] = "lon"
            elif name in ("alt", "altitude", "height", "h"):
                rename[col] = "alt"
        df.rename(columns=rename, inplace=True)
        missing = [col for col in ("time", "lat", "lon", "alt") if col not in df.columns]
        if missing:
            raise RuntimeError(f"gt file missing columns: {missing}")
        df["time"] = pd.to_numeric(df["time"], errors="coerce")
        df = df.dropna(subset=["time"]).reset_index(drop=True)
        t0 = df["time"].iloc[0]
        if t0 > 1e18:
            df["time"] /= 1e9
        elif t0 > 1e12:
            df["time"] /= 1e6
        if add_leap:
            df["time"] += 18
        return df[["time", "lat", "lon", "alt"]].reset_index(drop=True)

    df_raw = pd.read_csv(
        gt_path,
        skiprows=skip_rows,
        header=None,
        sep=sep,
        skipfooter=4,
        on_bad_lines="skip",
        engine="python",
    )
    df_raw[0] = pd.to_numeric(df_raw[0], errors="coerce")
    df_raw = df_raw.dropna(subset=[0]).reset_index(drop=True)
    if add_leap:
        df_raw[0] += 18
    df = pd.DataFrame(
        {
            "time": df_raw[0],
            "lat": df_raw[3] + df_raw[4] / 60.0 + df_raw[5] / 3600.0,
            "lon": df_raw[6] + df_raw[7] / 60.0 + df_raw[8] / 3600.0,
            "alt": df_raw[9],
        }
    )
    return df[["time", "lat", "lon", "alt"]].reset_index(drop=True)


def match_gt(gt_df, t):
    idx = (gt_df["time"] - t).abs().idxmin()
    row = gt_df.iloc[idx]
    return float(row["lat"]), float(row["lon"]), float(row["alt"])


def load_ublox_pvt(pvt_path):
    df = pd.read_csv(pvt_path)
    time_col = None
    for col in df.columns:
        if col.lower().strip() in ("time", "timestamp", "t"):
            time_col = col
            break
    if time_col is None:
        time_col = df.columns[0]
    df.rename(columns={time_col: "time"}, inplace=True)
    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).reset_index(drop=True)
    t0 = df["time"].iloc[0]
    if t0 > 1e18:
        df["time"] /= 1e9
    elif t0 > 1e12:
        df["time"] /= 1e6
    df["vel_E"] = df["vel_e"]
    df["vel_N"] = df["vel_n"]
    df["vel_U"] = -df["vel_d"]
    return df[["time", "vel_E", "vel_N", "vel_U"]].reset_index(drop=True)


def get_ublox_vel(pvt_df, t, max_dt=0.5):
    idx = (pvt_df["time"] - t).abs().idxmin()
    if abs(pvt_df["time"].iloc[idx] - t) > max_dt:
        return np.zeros(3, dtype=np.float64)
    row = pvt_df.iloc[idx]
    return np.array([row["vel_E"], row["vel_N"], row["vel_U"]], dtype=np.float64)


class MedianVelFilter:
    def __init__(self, window=5):
        self.buf_e = deque(maxlen=window)
        self.buf_n = deque(maxlen=window)
        self.buf_u = deque(maxlen=window)

    def update(self, vel):
        self.buf_e.append(vel[0])
        self.buf_n.append(vel[1])
        self.buf_u.append(vel[2])
        return np.array(
            [
                float(np.median(self.buf_e)),
                float(np.median(self.buf_n)),
                float(np.median(self.buf_u)),
            ],
            dtype=np.float64,
        )

    def reset(self):
        self.buf_e.clear()
        self.buf_n.clear()
        self.buf_u.clear()


def extract_imu_features(seg):
    zeros = {
        "mean_acc": np.zeros(3, dtype=np.float64),
        "mean_gyro": np.zeros(3, dtype=np.float64),
        "std_acc": np.zeros(3, dtype=np.float64),
    }
    if seg is None or len(seg) < 1:
        return zeros
    acc = seg[["ax", "ay", "az"]].values.astype(np.float64)
    gyro = seg[["gx", "gy", "gz"]].values.astype(np.float64)
    return {
        "mean_acc": acc.mean(0),
        "mean_gyro": gyro.mean(0),
        "std_acc": acc.std(0) if len(acc) > 1 else np.zeros(3, dtype=np.float64),
    }


def build_feature_vector(feat, vel_enu, ret, pad_snr=0.0, pad_el=0.0, pad_res=0.0):
    residuals = ret.get("residuals", [])
    snr = ret.get("snr", [])
    el = ret.get("el", [])
    sats = sorted(
        [[snr[i], el[i], residuals[i]] for i in range(len(residuals))],
        key=lambda item: item[1],
        reverse=True,
    )
    sat_flat = []
    for i in range(10):
        sat_flat.extend(sats[i] if i < len(sats) else [pad_snr, pad_el, pad_res])
    return np.concatenate(
        [
            feat["mean_acc"],
            feat["mean_gyro"],
            feat["std_acc"],
            np.clip(vel_enu, -30.0, 30.0),
            sat_flat,
        ]
    ).astype(np.float32)


def get_imu_segment(imu_df, t0, t1):
    return imu_df[(imu_df["timestamp"] >= t0) & (imu_df["timestamp"] <= t1)].reset_index(drop=True)


def build_split_indices(num_samples, mode="blocked", val_every=7, val_ratio=0.2, val_gap=5):
    if num_samples < 5:
        val_idx = [num_samples - 1]
        train_idx = [i for i in range(num_samples) if i != num_samples - 1]
        return train_idx, val_idx

    if mode == "interleaved":
        stride = max(2, int(val_every))
        val_idx = [i for i in range(num_samples) if i % stride == 0]
        train_idx = [i for i in range(num_samples) if i % stride != 0]
    else:
        val_size = max(1, int(round(num_samples * float(val_ratio))))
        val_size = min(val_size, max(1, num_samples // 3))
        gap = max(0, int(val_gap))
        if val_size + gap >= num_samples:
            gap = max(0, num_samples - val_size - 1)
        val_start = num_samples - val_size
        train_end = max(1, val_start - gap)
        train_idx = list(range(train_end))
        val_idx = list(range(val_start, num_samples))

    if not train_idx:
        train_idx = list(range(max(1, num_samples - 1)))
    if not val_idx:
        val_idx = [num_samples - 1]
        train_idx = [i for i in train_idx if i != num_samples - 1]
    return train_idx, val_idx


def build_lstm_dataset(features, gnss, gt, indices, window):
    usable = [i for i in indices if i >= window - 1]
    if not usable:
        return (
            usable,
            np.empty((0, window, features.shape[1]), dtype=np.float32),
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.float32),
        )
    seq_x = np.stack([features[i - window + 1 : i + 1] for i in usable], axis=0).astype(np.float32)
    y_gnss = gnss[usable].astype(np.float32)
    y_gt = gt[usable].astype(np.float32)
    return usable, seq_x, y_gnss, y_gt


def model_forward(net, x, use_lstm):
    if use_lstm:
        pred, _ = net(x)
        return pred[:, -1, :]
    return net(x)


def augment_inputs(x, input_std_t, sat_mask_prob, pad_triplet, feat_noise_std):
    x = x.clone()
    std_shape = [1] * (x.dim() - 1) + [x.shape[-1]]
    if feat_noise_std > 0:
        noise = torch.randn_like(x) * input_std_t.view(std_shape) * feat_noise_std
        noise[..., 9:12] = 0.0
        x = x + noise
    if sat_mask_prob > 0:
        sat = x[..., 12:].reshape(*x.shape[:-1], 10, 3)
        mask = (torch.rand(*x.shape[:-1], 10, device=x.device) < sat_mask_prob).unsqueeze(-1)
        pad = pad_triplet.view(*([1] * (sat.dim() - 1)), 3)
        sat = torch.where(mask, pad, sat)
        x[..., 12:] = sat.reshape(*x.shape[:-1], 30)
    return x


def structured_augment(x, input_std_t, feat_noise_std=0.04, sat_drop_prob=0.25, residual_scale_std=0.30):
    """Physically structured augmentation for the 42-D IMU/GNSS feature layout."""
    x = x.clone()
    prefix = x.shape[:-1]

    if sat_drop_prob > 0:
        sat = x[..., 12:].reshape(*prefix, 10, 3)
        drop_mask = (torch.rand(*prefix, 10, device=x.device) < sat_drop_prob).unsqueeze(-1)
        sat = torch.where(drop_mask, torch.zeros_like(sat), sat)
        x[..., 12:] = sat.reshape(*prefix, 30)

    bias = torch.randn(*prefix, 6, device=x.device) * 0.05
    x[..., :6] = x[..., :6] + bias

    sat = x[..., 12:].reshape(*prefix, 10, 3)
    scale = (1.0 + torch.randn(*prefix, 1, 1, device=x.device) * residual_scale_std).clamp(0.3, 3.0)
    sat[..., 2:3] = sat[..., 2:3] * scale
    x[..., 12:] = sat.reshape(*prefix, 30)

    if feat_noise_std > 0:
        std_shape = [1] * (x.dim() - 1) + [x.shape[-1]]
        noise = torch.randn_like(x) * input_std_t.view(std_shape) * feat_noise_std
        noise[..., 9:12] = 0.0
        x = x + noise
    return x


def plot_training_curves(losses, val_dists, result_path):
    epochs = np.arange(1, len(losses) + 1)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].plot(epochs, losses, color="#111827", lw=1.8)
    axes[0].set_title("Train Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Huber")
    axes[0].grid(alpha=0.3, linestyle="--")

    axes[1].plot(epochs, val_dists, color="#8B5CF6", lw=1.8)
    axes[1].set_title("Validation 3D Error")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Meters")
    axes[1].grid(alpha=0.3, linestyle="--")

    fig.tight_layout()
    fig.savefig(os.path.join(result_path, "loss_curves.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)

    np.savetxt(
        os.path.join(result_path, "loss.csv"),
        np.column_stack([epochs, np.array(losses), np.array(val_dists)]),
        delimiter=",",
        header="epoch,train_huber,val_dist_m",
        comments="",
    )


def main():
    print(f"Using device: {DEVICE}")
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/imu/ingvio_train.json"
    conf = load_json(config_path)
    seed = int(conf.get("seed", 42))
    set_global_seed(seed)
    print(f"Using seed: {seed}")

    os.makedirs(conf["model"], exist_ok=True)
    result_tag = os.path.basename(config_path).replace(".json", "")
    result_path = os.path.join("result", "imu", result_tag)
    os.makedirs(result_path, exist_ok=True)

    use_lstm = conf.get("imu_window", 0) > 0
    lstm_win = int(conf.get("imu_window", 10))
    lr = float(conf.get("lr", 1e-4))
    batch_size = int(conf.get("batch", 64))
    num_epochs = int(conf.get("epoch", 300))
    val_every = int(conf.get("val_every", 7))
    val_mode = conf.get("val_mode", "blocked")
    val_ratio = float(conf.get("val_ratio", 0.2))
    val_gap = int(conf.get("val_gap", 5))
    early_stop_min = int(conf.get("early_stop_min_epoch", 30))
    early_stop_pat = int(conf.get("early_stop_patience", 50))
    feat_noise_std = float(conf.get("feat_noise", 0.12))
    sat_mask_prob = float(conf.get("sat_mask_prob", 0.10))
    weight_decay = float(conf.get("weight_decay", 1e-4))
    corr_clip_sigma = float(conf.get("corr_clip_sigma", 3.0))
    corr_clip_min_m = float(conf.get("corr_clip_min_m", 5.0))
    pred_reg = float(conf.get("pred_reg", 0.01))
    pred_reg_mode = conf.get("pred_reg_mode", "l2")
    pred_reg_tau = float(conf.get("pred_reg_tau", 2.0))
    model_arch = conf.get("model_arch", "small")
    small_dropout = float(conf.get("small_dropout", 0.30))
    use_structured_aug = bool(conf.get("structured_aug", True))
    sat_drop_prob = float(conf.get("sat_drop_prob", 0.25))
    residual_scale_std = float(conf.get("residual_scale_std", 0.30))

    print("=" * 60)
    print("Step 1: Loading GNSS observations")
    obs, nav, _ = util.read_obs(conf["obs"], conf["eph"], ref=conf.get("base"))
    prl.sortobs(obs)
    obss = util.split_obs(obs)

    print("Step 2: Loading IMU")
    imu_df = util.load_imu_data(conf["imu"])
    if imu_df is None:
        raise RuntimeError("failed to load imu data")
    print(f"  IMU rows: {len(imu_df)}")

    pvt_df = None
    if conf.get("ublox_pvt"):
        pvt_df = load_ublox_pvt(conf["ublox_pvt"])
        print(f"  Doppler rows: {len(pvt_df)}")

    print("Step 3: Loading ground truth")
    gt_df = load_gt(conf["gt"], conf.get("gt_leap_seconds", False))
    print(f"  GT rows: {len(gt_df)}")

    obss = [
        o
        for o in obss
        if (
            lambda t: t > conf["start_time"]
            and (conf["end_time"] == -1 or t < conf["end_time"])
        )(o.data[0].time.time + o.data[0].time.sec)
    ]
    print(f"  Filtered epochs: {len(obss)}")

    print("Step 4: Collecting satellite padding statistics")
    snr_v, el_v, res_v = [], [], []
    for o in tqdm(obss, desc="sat-stats"):
        try:
            ret = util.robust_wls_pnt_pos(o, nav)
        except Exception:
            continue
        if not ret["status"]:
            continue
        snr_v.extend(ret.get("snr", []))
        el_v.extend(ret.get("el", []))
        res_v.extend(ret.get("residuals", []))
    pad_snr = float(np.mean(snr_v)) if snr_v else 30.0
    pad_el = float(np.mean(el_v)) if el_v else 15.0
    pad_res = float(np.mean(res_v)) if res_v else 0.0
    print(f"  pad_snr={pad_snr:.2f} pad_el={pad_el:.2f} pad_res={pad_res:.2f}")

    print("Step 5: Building cached samples")
    cached_feats, cached_gnss, cached_gt = [], [], []
    ref_geo = None
    prev_t = None
    prev_enu = None
    vel_filter = MedianVelFilter()

    for o in tqdm(obss, desc="cache"):
        curr_t = o.data[0].time.time + o.data[0].time.sec
        try:
            ret = util.robust_wls_pnt_pos(o, nav)
        except Exception:
            prev_t = None
            prev_enu = None
            vel_filter.reset()
            continue
        if not ret["status"]:
            prev_t = None
            prev_enu = None
            vel_filter.reset()
            continue

        gt_geo = match_gt(gt_df, curr_t)
        if ref_geo is None:
            ref_geo = gt_geo

        gnss_geo = p3d.ecef2geodetic(*ret["pos"][:3])
        gnss_enu = np.array(p3d.geodetic2enu(*gnss_geo, *ref_geo), dtype=np.float64)
        gt_enu = np.array(p3d.geodetic2enu(*gt_geo, *ref_geo), dtype=np.float64)

        if np.linalg.norm(gnss_enu - gt_enu) > 500.0:
            prev_t = curr_t
            prev_enu = gnss_enu
            continue

        if pvt_df is not None:
            vel = get_ublox_vel(pvt_df, curr_t)
        elif prev_t is not None and prev_enu is not None:
            vel = vel_filter.update((gnss_enu - prev_enu) / max(curr_t - prev_t, 1e-3))
        else:
            vel = np.zeros(3, dtype=np.float64)

        imu_feat = extract_imu_features(get_imu_segment(imu_df, prev_t, curr_t)) if prev_t is not None else extract_imu_features(None)

        cached_feats.append(build_feature_vector(imu_feat, vel, ret, pad_snr, pad_el, pad_res))
        cached_gnss.append(gnss_enu.astype(np.float32))
        cached_gt.append(gt_enu.astype(np.float32))
        prev_t = curr_t
        prev_enu = gnss_enu

    num_samples = len(cached_feats)
    if num_samples == 0:
        raise RuntimeError("no valid samples generated")
    print(f"  Valid samples: {num_samples}")

    raw_feat = np.array(cached_feats, dtype=np.float32)
    gnss_np = np.array(cached_gnss, dtype=np.float32)
    gt_np = np.array(cached_gt, dtype=np.float32)

    up_errors_all = gt_np[:, 2] - gnss_np[:, 2]
    filter_up_bias = float(np.median(up_errors_all))
    up_resid_all = up_errors_all - filter_up_bias
    up_sigma_all = float(np.std(up_resid_all))
    if up_sigma_all > 1e-6:
        sample_weights = np.exp(-0.5 * (up_resid_all / (2.0 * up_sigma_all)) ** 2).astype(np.float32)
    else:
        sample_weights = np.ones(len(up_resid_all), dtype=np.float32)
    sample_weights = sample_weights / max(float(sample_weights.mean()), 1e-6)
    print(
        f"  Vertical soft weights: samples={num_samples} sigma={up_sigma_all:.2f}m "
        f"weight[min/mean/max]={sample_weights.min():.3f}/{sample_weights.mean():.3f}/{sample_weights.max():.3f}"
    )

    train_idx, val_idx = build_split_indices(
        num_samples,
        mode=val_mode,
        val_every=val_every,
        val_ratio=val_ratio,
        val_gap=val_gap,
    )
    print(f"  Validation split: mode={val_mode} train={len(train_idx)} val={len(val_idx)}")

    train_feat = raw_feat[train_idx]
    feat_mean = train_feat.mean(0)
    feat_std = np.where(train_feat.std(0) < 1e-6, 1.0, train_feat.std(0))

    up_train = gt_np[train_idx, 2] - gnss_np[train_idx, 2]
    up_bias = float(np.median(up_train))
    up_resid_std = float(np.std(up_train - up_bias))
    gt_debiased_np = gt_np.copy()
    gt_debiased_np[:, 2] -= up_bias

    train_corr = gt_debiased_np[train_idx] - gnss_np[train_idx]
    corr_std = np.where(train_corr.std(0) < 1e-3, 1.0, train_corr.std(0)).astype(np.float32)
    corr_clip = np.maximum(
        np.quantile(np.abs(train_corr), 0.995, axis=0).astype(np.float32),
        np.maximum(corr_std * corr_clip_sigma, np.full(3, corr_clip_min_m, dtype=np.float32)),
    )

    np.savez(
        os.path.join(conf["model"], "imu_corr_norm.npz"),
        mean=np.zeros(3, dtype=np.float32),
        std=corr_std,
        corr_clip=corr_clip,
        up_bias=np.array([up_bias], dtype=np.float32),
        up_resid_std=np.array([up_resid_std], dtype=np.float32),
        model_arch=np.array([model_arch]),
        pad_snr=np.array([pad_snr], dtype=np.float32),
        pad_el=np.array([pad_el], dtype=np.float32),
        pad_res=np.array([pad_res], dtype=np.float32),
    )
    print(f"  Up bias median: {up_bias:.3f} m")
    print(f"  Up residual std after debias: {up_resid_std:.3f} m")
    print(f"  Correction std: {corr_std.round(3)}")
    print(f"  Correction clip: {corr_clip.round(3)}")

    if use_lstm:
        train_idx, train_x_np, train_gnss_np, train_gt_np = build_lstm_dataset(raw_feat, gnss_np, gt_debiased_np, train_idx, lstm_win)
        val_idx, val_x_np, val_gnss_np, val_gt_np = build_lstm_dataset(raw_feat, gnss_np, gt_np, val_idx, lstm_win)
        if len(train_x_np) == 0 or len(val_x_np) == 0:
            raise RuntimeError("LSTM split is empty; reduce imu_window or val_gap")
        train_x = torch.tensor(train_x_np, dtype=torch.float32)
        train_gnss = torch.tensor(train_gnss_np, dtype=torch.float32)
        train_gt = torch.tensor(train_gt_np, dtype=torch.float32)
        train_w = torch.ones(len(train_x), dtype=torch.float32)
        val_x = torch.tensor(val_x_np, dtype=torch.float32)
        val_gnss = torch.tensor(val_gnss_np, dtype=torch.float32)
        val_gt = torch.tensor(val_gt_np, dtype=torch.float32)
        model = IMUFusionNetLSTM(torch.tensor(feat_mean), torch.tensor(feat_std)).to(DEVICE)
    else:
        train_x = torch.tensor(raw_feat[train_idx], dtype=torch.float32)
        train_gnss = torch.tensor(gnss_np[train_idx], dtype=torch.float32)
        train_gt = torch.tensor(gt_debiased_np[train_idx], dtype=torch.float32)
        train_w = torch.tensor(sample_weights[train_idx], dtype=torch.float32)
        val_x = torch.tensor(raw_feat[val_idx], dtype=torch.float32)
        val_gnss = torch.tensor(gnss_np[val_idx], dtype=torch.float32)
        val_gt = torch.tensor(gt_np[val_idx], dtype=torch.float32)
        if model_arch == "small":
            model = IMUFusionNetSmall(
                torch.tensor(feat_mean), torch.tensor(feat_std), dropout=small_dropout
            ).to(DEVICE)
        else:
            model = IMUFusionNet(torch.tensor(feat_mean), torch.tensor(feat_std)).to(DEVICE)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(1, num_epochs), eta_min=lr * 0.01
    )
    corr_std_t = torch.tensor(corr_std, dtype=torch.float32, device=DEVICE)
    up_bias_t = torch.tensor(up_bias, dtype=torch.float32, device=DEVICE)
    input_std_t = torch.tensor(feat_std, dtype=torch.float32, device=DEVICE)
    pad_triplet = torch.tensor([pad_snr, pad_el, pad_res], dtype=torch.float32, device=DEVICE)

    losses = []
    val_dists = []
    best_dist = float("inf")
    no_improve = 0

    print("Step 6: Training")
    print(f"  arch={model_arch} use_lstm={use_lstm} lr={lr} batch={batch_size} weight_decay={weight_decay}")
    print(f"  structured_aug={use_structured_aug} feat_noise_std={feat_noise_std} sat_drop_prob={sat_drop_prob}")

    for epoch in range(num_epochs):
        model.train()
        order = list(range(len(train_x)))
        random.shuffle(order)
        running_loss = 0.0
        steps = 0

        for start in range(0, len(order), batch_size):
            batch_ids = order[start : start + batch_size]
            x_b = train_x[batch_ids].to(DEVICE)
            gnss_b = train_gnss[batch_ids].to(DEVICE)
            gt_b = train_gt[batch_ids].to(DEVICE)
            w_b = train_w[batch_ids].to(DEVICE)

            if use_structured_aug:
                x_b = structured_augment(
                    x_b,
                    input_std_t,
                    feat_noise_std=feat_noise_std,
                    sat_drop_prob=sat_drop_prob,
                    residual_scale_std=residual_scale_std,
                )
            else:
                x_b = augment_inputs(x_b, input_std_t, sat_mask_prob, pad_triplet, feat_noise_std)
            corr_norm = model_forward(model, x_b, use_lstm)
            target_norm = (gt_b - gnss_b) / corr_std_t
            per_sample_loss = F.huber_loss(corr_norm, target_norm, delta=1.5, reduction="none").mean(dim=1)
            data_loss = (per_sample_loss * w_b).mean()
            if pred_reg_mode == "threshold":
                residual_mag = torch.norm(corr_norm, dim=1)
                reg_loss = pred_reg * F.relu(residual_mag - pred_reg_tau).mean()
            else:
                reg_loss = pred_reg * (corr_norm ** 2).mean()
            loss = data_loss + reg_loss

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            running_loss += float(loss.item())
            steps += 1

        avg_loss = running_loss / max(steps, 1)
        losses.append(avg_loss)

        model.eval()
        with torch.no_grad():
            corr_v = model_forward(model, val_x.to(DEVICE), use_lstm)
            pred_v = val_gnss.to(DEVICE) + corr_v * corr_std_t
            pred_v[:, 2] += up_bias_t
            dist_v = torch.norm(pred_v - val_gt.to(DEVICE), dim=1).mean().item()
        val_dists.append(dist_v)
        scheduler.step()

        print(
            f"[Epoch {epoch + 1:03d}/{num_epochs}] "
            f"loss={avg_loss:.4f} val3d={dist_v:.3f}m lr={optimizer.param_groups[0]['lr']:.2e}"
        )

        if dist_v < best_dist:
            best_dist = dist_v
            no_improve = 0
            torch.save(model.state_dict(), os.path.join(conf["model"], "imu_fusion_best.pth"))
        else:
            no_improve += 1

        if epoch + 1 >= early_stop_min and no_improve >= early_stop_pat:
            print(f"Early stop at epoch {epoch + 1}, best val3d={best_dist:.3f}m")
            break

    torch.save(model.state_dict(), os.path.join(conf["model"], "imu_fusion_final.pth"))
    plot_training_curves(losses, val_dists, result_path)

    print("Step 7: Final evaluation")
    model.load_state_dict(torch.load(os.path.join(conf["model"], "imu_fusion_best.pth"), map_location=DEVICE))
    model.eval()

    with torch.no_grad():
        if use_lstm:
            _, full_x_np, full_gnss_np, full_gt_np = build_lstm_dataset(raw_feat, gnss_np, gt_np, list(range(num_samples)), lstm_win)
            full_x = torch.tensor(full_x_np, dtype=torch.float32, device=DEVICE)
            corr_all = model_forward(model, full_x, True).cpu().numpy()
            pred_all = full_gnss_np + corr_all * corr_std
            pred_all[:, 2] += up_bias
            gnss_eval = full_gnss_np
            gt_eval = full_gt_np
        else:
            full_x = torch.tensor(raw_feat, dtype=torch.float32, device=DEVICE)
            corr_all = model_forward(model, full_x, False).cpu().numpy()
            pred_all = gnss_np + corr_all * corr_std
            pred_all[:, 2] += up_bias
            gnss_eval = gnss_np
            gt_eval = gt_np

    gnss_2d = np.linalg.norm(gnss_eval[:, :2] - gt_eval[:, :2], axis=1)
    gnss_3d = np.linalg.norm(gnss_eval - gt_eval, axis=1)
    fuse_2d = np.linalg.norm(pred_all[:, :2] - gt_eval[:, :2], axis=1)
    fuse_3d = np.linalg.norm(pred_all - gt_eval, axis=1)

    print("\n最终评估 (best 模型) ...")
    print()
    print(f"  {'方法':<25} {'2D Mean(m)':>12} {'2D RMS(m)':>12} {'3D Mean(m)':>12}")
    print(f"  {'-' * 65}")
    print(f"  {'GNSS Only':<25} {gnss_2d.mean():>12.4f} {np.sqrt(np.mean(gnss_2d ** 2)):>12.4f} {gnss_3d.mean():>12.4f}")
    print(f"  {'IMU+GNSS Fusion':<25} {fuse_2d.mean():>12.4f} {np.sqrt(np.mean(fuse_2d ** 2)):>12.4f} {fuse_3d.mean():>12.4f}")
    print()
    print(f"  Validation best: {best_dist:.4f} m")
    print(f"  2D improvement: {(1.0 - fuse_2d.mean() / max(gnss_2d.mean(), 1e-6)) * 100.0:+.2f}%")


if __name__ == "__main__":
    main()
