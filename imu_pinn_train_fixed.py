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
from model import PINNFusionNet, PINN_EXT_INPUT_DIM

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MOTION_DIM = 21
SAT_COUNT = 10
SAT_FEATURE_DIM = 5
EXTRA_DIM = 7


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
    first_data, skip_rows = "", 0
    for idx, line in enumerate(sample):
        text = line.strip()
        if text and not text.startswith("%") and not text.startswith("#"):
            first_data, skip_rows = text, idx
            break
    sep = "," if "," in first_data else r"\s+"
    first_tok = first_data.split(",")[0] if "," in first_data else first_data.split()[0]
    if any(ch.isalpha() for ch in first_tok):
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
        missing = [c for c in ("time", "lat", "lon", "alt") if c not in df.columns]
        if missing:
            raise RuntimeError(f"gt missing columns: {missing}")
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
    return pd.DataFrame(
        {
            "time": df_raw[0],
            "lat": df_raw[3] + df_raw[4] / 60.0 + df_raw[5] / 3600.0,
            "lon": df_raw[6] + df_raw[7] / 60.0 + df_raw[8] / 3600.0,
            "alt": df_raw[9],
        }
    )[["time", "lat", "lon", "alt"]].reset_index(drop=True)


def match_gt(gt_df, t):
    idx = (gt_df["time"] - t).abs().idxmin()
    row = gt_df.iloc[idx]
    return float(row["lat"]), float(row["lon"]), float(row["alt"])


def load_ublox_pvt(path):
    df = pd.read_csv(path)
    time_col = next((c for c in df.columns if c.lower().strip() in ("time", "timestamp", "t")), df.columns[0])
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


def get_imu_segment(imu_df, t0, t1):
    return imu_df[(imu_df["timestamp"] >= t0) & (imu_df["timestamp"] <= t1)].reset_index(drop=True)


def safe_moments(x):
    if len(x) < 2:
        return np.zeros(3), np.zeros(3), np.zeros(3)
    mu = x.mean(0)
    sigma = x.std(0)
    sigma = np.where(sigma < 1e-6, 1.0, sigma)
    centered = (x - mu) / sigma
    skew = np.mean(centered**3, axis=0)
    kurt = np.mean(centered**4, axis=0) - 3.0
    jerk = np.diff(x, axis=0).mean(0) if len(x) > 1 else np.zeros(3)
    return skew, kurt, jerk


def extract_imu_features(seg):
    if seg is None or len(seg) < 1:
        return np.zeros(18, dtype=np.float64)
    acc = seg[["ax", "ay", "az"]].values.astype(np.float64)
    gyro = seg[["gx", "gy", "gz"]].values.astype(np.float64)
    skew, kurt, jerk = safe_moments(acc)
    return np.concatenate(
        [
            acc.mean(0),
            gyro.mean(0),
            acc.std(0) if len(acc) > 1 else np.zeros(3),
            skew,
            kurt,
            jerk,
        ]
    ).astype(np.float64)


def carrier_wavelength(sat):
    sat_id = prl.Arr1Dchar(8)
    try:
        prl.satno2id(sat, sat_id)
        sys_char = sat_id.ptr[0]
    except Exception:
        sys_char = "G"
    freq = {
        "G": 1575.42e6,
        "J": 1575.42e6,
        "E": 1575.42e6,
        "C": 1561.098e6,
        "R": 1602.0e6,
    }.get(sys_char, 1575.42e6)
    return 299792458.0 / freq


def cmc_from_obs_data(d):
    try:
        if d.P[0] == 0.0 or d.L[0] == 0.0:
            return 0.0
        return float(np.clip(d.P[0] - d.L[0] * carrier_wavelength(d.sat), -200.0, 200.0))
    except Exception:
        return 0.0


def valid_obs_records(o):
    records = []
    for i in range(o.n):
        d = o.data[i]
        if getattr(d, "rcv", 1) != 1:
            continue
        try:
            if d.P[0] == 0.0:
                continue
            sat = int(d.sat)
            snr = float(d.SNR[0]) / 1000.0
        except Exception:
            continue
        records.append({"sat": sat, "snr": snr, "cmc": cmc_from_obs_data(d)})
    return records


def build_feature_vector(imu_feat, vel_enu, ret, obs_records, prev_res_by_rank, pad):
    residuals = np.asarray(ret.get("residuals", []), dtype=np.float64)
    snr = np.asarray(ret.get("snr", []), dtype=np.float64)
    el = np.asarray(ret.get("el", []), dtype=np.float64)
    obs_records = obs_records[: len(residuals)]

    sats = []
    for i in range(len(residuals)):
        rec = obs_records[i] if i < len(obs_records) else {}
        cmc = float(rec.get("cmc", 0.0))
        dres = float(residuals[i] - prev_res_by_rank.get(i, residuals[i]))
        sats.append([snr[i], el[i], residuals[i], cmc, dres])
        prev_res_by_rank[i] = float(residuals[i])
    sats = sorted(sats, key=lambda item: item[1], reverse=True)

    sat_flat = []
    pad_sat = [pad["snr"], pad["el"], pad["res"], 0.0, 0.0]
    for i in range(SAT_COUNT):
        sat_flat.extend(sats[i] if i < len(sats) else pad_sat)

    vel = np.clip(vel_enu, -30.0, 30.0)
    el_safe = np.maximum(el, 1e-3)
    extra = np.array(
        [
            np.sqrt(np.mean(1.0 / np.sin(el_safe) ** 2)) if len(el_safe) else 0.0,
            float(len(residuals)),
            float(np.mean(snr)) if len(snr) else pad["snr"],
            float(np.mean(el)) if len(el) else pad["el"],
            float(np.sqrt(np.mean(residuals**2))) if len(residuals) else abs(pad["res"]),
            float(np.linalg.norm(vel[:2])),
            float(np.arctan2(vel[0], vel[1])) if np.linalg.norm(vel[:2]) > 1e-3 else 0.0,
        ],
        dtype=np.float64,
    )
    return np.concatenate([imu_feat, vel, np.array(sat_flat), extra]).astype(np.float32)


def build_split_indices(n, mode="blocked", val_ratio=0.2, val_every=7, val_gap=5):
    if mode == "interleaved":
        stride = max(2, int(val_every))
        val_idx = [i for i in range(n) if i % stride == 0]
        train_idx = [i for i in range(n) if i % stride != 0]
    else:
        val_size = min(max(1, int(round(n * val_ratio))), max(1, n // 3))
        gap = min(max(0, int(val_gap)), max(0, n - val_size - 1))
        train_idx = list(range(max(1, n - val_size - gap)))
        val_idx = list(range(n - val_size, n))
    return train_idx, val_idx


def pinn_forward(net, x):
    out = net(x)
    if len(out) == 4:
        return out
    pos, vel = out
    return pos, vel, None, None


def nll_or_huber(pos_norm, target_norm, log_var):
    return F.huber_loss(pos_norm, target_norm, delta=1.5, reduction="mean")


def main():
    print(f"Using device: {DEVICE}")
    config = sys.argv[1] if len(sys.argv) > 1 else "config/imu/ingvio_pinn_train.json"
    conf = load_json(config)
    seed = int(conf.get("seed", 42))
    set_global_seed(seed)
    print(f"Using seed: {seed}")
    os.makedirs(conf["model"], exist_ok=True)
    result_path = os.path.join("result", "imu", os.path.basename(config).replace(".json", ""))
    os.makedirs(result_path, exist_ok=True)

    lr = float(conf.get("lr", 5e-4))
    batch_size = int(conf.get("batch", 64))
    epochs = int(conf.get("epoch", 300))
    lambda_vel = float(conf.get("lambda_vel", 1.0))
    lambda_kin = float(conf.get("lambda_kin", 0.05))
    lambda_alt = float(conf.get("lambda_alt", 0.02))
    lambda_smth = float(conf.get("lambda_smth", 0.05))
    warmup_epochs = int(conf.get("warmup_epochs", 20))
    early_stop_min = max(int(conf.get("early_stop_min_epoch", 30)), warmup_epochs + 10)
    early_stop_pat = int(conf.get("early_stop_patience", 50))
    val_mode = conf.get("val_mode", "blocked")
    val_ratio = float(conf.get("val_ratio", 0.2))
    val_every = int(conf.get("val_every", 7))
    val_gap = int(conf.get("val_gap", 5))
    feat_noise = float(conf.get("feat_noise", 0.08))

    print("Step 1: load observations")
    obs, nav, _ = util.read_obs(conf["obs"], conf["eph"], ref=conf.get("base"))
    prl.sortobs(obs)
    obss = util.split_obs(obs)
    imu_df = util.load_imu_data(conf["imu"])
    if imu_df is None:
        raise RuntimeError("failed to load IMU")
    pvt_df = load_ublox_pvt(conf["ublox_pvt"])
    gt_df = load_gt(conf["gt"], conf.get("gt_leap_seconds", False))
    obss = [
        o
        for o in obss
        if (
            lambda t: t > conf["start_time"] and (conf["end_time"] == -1 or t < conf["end_time"])
        )(o.data[0].time.time + o.data[0].time.sec)
    ]
    print(f"  epochs={len(obss)} imu={len(imu_df)} pvt={len(pvt_df)} gt={len(gt_df)}")

    print("Step 2: satellite padding stats")
    snr_v, el_v, res_v = [], [], []
    for o in tqdm(obss, desc="sat-stats"):
        try:
            ret = util.robust_wls_pnt_pos(o, nav)
        except Exception:
            continue
        if not ret.get("status", False):
            continue
        snr_v.extend(ret.get("snr", []))
        el_v.extend(ret.get("el", []))
        res_v.extend(ret.get("residuals", []))
    pad = {
        "snr": float(np.mean(snr_v)) if snr_v else 30.0,
        "el": float(np.mean(el_v)) if el_v else 0.3,
        "res": float(np.mean(res_v)) if res_v else 0.0,
    }

    print("Step 3: build training cache")
    feats, gnss_list, gt_list, vel_list, dt_list, seq_list, gnss_disp_list = [], [], [], [], [], [], []
    ref_geo = None
    prev_t = None
    prev_enu = None
    prev_valid = False
    prev_res_by_rank = {}

    for o in tqdm(obss, desc="cache"):
        curr_t = o.data[0].time.time + o.data[0].time.sec
        try:
            ret = util.robust_wls_pnt_pos(o, nav)
        except Exception:
            prev_t, prev_enu, prev_valid = None, None, False
            prev_res_by_rank = {}
            continue
        if not ret.get("status", False):
            prev_t, prev_enu, prev_valid = None, None, False
            prev_res_by_rank = {}
            continue

        gt_geo = match_gt(gt_df, curr_t)
        if ref_geo is None:
            ref_geo = gt_geo
        gnss_geo = p3d.ecef2geodetic(*ret["pos"][:3])
        gnss_enu = np.array(p3d.geodetic2enu(*gnss_geo, *ref_geo), dtype=np.float64)
        gt_enu = np.array(p3d.geodetic2enu(*gt_geo, *ref_geo), dtype=np.float64)
        if np.linalg.norm(gnss_enu - gt_enu) > 500.0:
            prev_t, prev_enu, prev_valid = curr_t, gnss_enu, False
            continue

        vel = get_ublox_vel(pvt_df, curr_t)
        dt = curr_t - prev_t if prev_t is not None else 0.0
        is_seq = bool(prev_valid and prev_t is not None and 0.01 < dt < 2.0)
        imu_feat = extract_imu_features(get_imu_segment(imu_df, prev_t, curr_t)) if prev_t is not None else extract_imu_features(None)
        feat = build_feature_vector(imu_feat, vel, ret, valid_obs_records(o), prev_res_by_rank, pad)
        gnss_disp = np.clip(gnss_enu - prev_enu, -20.0, 20.0) if is_seq and prev_enu is not None else np.zeros(3)

        feats.append(feat)
        gnss_list.append(gnss_enu.astype(np.float32))
        gt_list.append(gt_enu.astype(np.float32))
        vel_list.append(vel.astype(np.float32))
        dt_list.append(float(dt))
        seq_list.append(is_seq)
        gnss_disp_list.append(gnss_disp.astype(np.float32))
        prev_t, prev_enu, prev_valid = curr_t, gnss_enu, True

    n = len(feats)
    if n == 0:
        raise RuntimeError("no valid samples")
    x_np = np.array(feats, dtype=np.float32)
    gnss_np = np.array(gnss_list, dtype=np.float32)
    gt_np = np.array(gt_list, dtype=np.float32)
    vel_np = np.array(vel_list, dtype=np.float32)
    dt_np = np.array(dt_list, dtype=np.float32)
    seq_np = np.array(seq_list, dtype=bool)
    gnss_disp_np = np.array(gnss_disp_list, dtype=np.float32)
    assert x_np.shape[1] == PINN_EXT_INPUT_DIM, x_np.shape

    up_errors_all = gt_np[:, 2] - gnss_np[:, 2]
    filter_up_bias = float(np.median(up_errors_all))
    up_resid_all = up_errors_all - filter_up_bias
    up_sigma_all = float(np.std(up_resid_all))
    if up_sigma_all > 1e-6:
        up_threshold = 3.0 * up_sigma_all
        keep_mask = np.abs(up_resid_all) < up_threshold
    else:
        up_threshold = 0.0
        keep_mask = np.ones(len(up_resid_all), dtype=bool)
    keep_idx = np.where(keep_mask)[0]
    keep_count = int(keep_idx.size)
    if keep_count == 0:
        raise RuntimeError("vertical outlier filter removed all samples")
    print(
        f"  Vertical outlier filter: {n} -> {keep_count} samples "
        f"(drop {n - keep_count}, sigma={up_sigma_all:.2f}m, "
        f"threshold={up_threshold:.2f}m)"
    )
    x_np = x_np[keep_idx]
    gnss_np = gnss_np[keep_idx]
    gt_np = gt_np[keep_idx]
    vel_np = vel_np[keep_idx]
    dt_np = dt_np[keep_idx]
    seq_np = seq_np[keep_idx]
    gnss_disp_np = gnss_disp_np[keep_idx]
    contiguous = np.zeros_like(seq_np, dtype=bool)
    if keep_count > 1:
        contiguous[1:] = np.diff(keep_idx) == 1
    seq_np = seq_np & contiguous
    gnss_disp_np[~seq_np] = 0.0
    n = keep_count

    train_idx, val_idx = build_split_indices(n, val_mode, val_ratio, val_every, val_gap)
    feat_mean = x_np[train_idx].mean(0).astype(np.float32)
    feat_std = x_np[train_idx].std(0).astype(np.float32)
    feat_std = np.where(feat_std < 1e-6, 1.0, feat_std)
    up_train = gt_np[train_idx, 2] - gnss_np[train_idx, 2]
    up_bias = float(np.median(up_train))
    up_resid_std = float(np.std(up_train - up_bias))
    gt_debiased_np = gt_np.copy()
    gt_debiased_np[:, 2] -= up_bias

    corr_train = gt_debiased_np[train_idx] - gnss_np[train_idx]
    corr_std = corr_train.std(0).astype(np.float32)
    corr_std = np.where(corr_std < 1e-3, 1.0, corr_std)
    corr_clip = np.maximum(np.quantile(np.abs(corr_train), 0.995, axis=0), np.maximum(corr_std * 3.0, 5.0)).astype(np.float32)
    vel_mean = vel_np[train_idx].mean(0).astype(np.float32)
    vel_std = vel_np[train_idx].std(0).astype(np.float32)
    vel_std = np.where(vel_std < 0.01, 1.0, vel_std)
    np.savez(
        os.path.join(conf["model"], "pinn_corr_norm.npz"),
        mean=np.zeros(3, dtype=np.float32),
        std=corr_std,
        corr_clip=corr_clip,
        up_bias=np.array([up_bias], dtype=np.float32),
        up_resid_std=np.array([up_resid_std], dtype=np.float32),
        vel_mean=vel_mean,
        vel_std=vel_std,
        pad_snr=np.array([pad["snr"]], dtype=np.float32),
        pad_el=np.array([pad["el"]], dtype=np.float32),
        pad_res=np.array([pad["res"]], dtype=np.float32),
        input_dim=np.array([PINN_EXT_INPUT_DIM], dtype=np.int32),
        motion_dim=np.array([MOTION_DIM], dtype=np.int32),
        sat_feature_dim=np.array([SAT_FEATURE_DIM], dtype=np.int32),
        extra_dim=np.array([EXTRA_DIM], dtype=np.int32),
    )
    print(f"  samples={n} train={len(train_idx)} val={len(val_idx)} input_dim={x_np.shape[1]}")
    print(f"  up_bias={up_bias:.3f} up_resid_std={up_resid_std:.3f}")
    print(f"  corr_std={corr_std.round(3)} corr_clip={corr_clip.round(3)}")

    x = torch.tensor(x_np, dtype=torch.float32)
    gnss = torch.tensor(gnss_np, dtype=torch.float32)
    gt = torch.tensor(gt_debiased_np, dtype=torch.float32)
    gt_true = torch.tensor(gt_np, dtype=torch.float32)
    vel = torch.tensor(vel_np, dtype=torch.float32)
    dt_t = torch.tensor(dt_np, dtype=torch.float32)
    seq_t = torch.tensor(seq_np, dtype=torch.bool)
    gnss_disp = torch.tensor(gnss_disp_np, dtype=torch.float32)
    corr_std_t = torch.tensor(corr_std, dtype=torch.float32, device=DEVICE)
    up_bias_t = torch.tensor(up_bias, dtype=torch.float32, device=DEVICE)
    vel_mean_t = torch.tensor(vel_mean, dtype=torch.float32, device=DEVICE)
    vel_std_t = torch.tensor(vel_std, dtype=torch.float32, device=DEVICE)
    feat_std_t = torch.tensor(feat_std, dtype=torch.float32, device=DEVICE)

    net = PINNFusionNet(
        imean=torch.tensor(feat_mean),
        istd=torch.tensor(feat_std),
        motion_dim=MOTION_DIM,
        sat_count=SAT_COUNT,
        sat_feature_dim=SAT_FEATURE_DIM,
        extra_dim=EXTRA_DIM,
        use_sat_attention=True,
        uncertainty=True,
    ).to(DEVICE)

    pretrain = conf.get("pretrain", "")
    if pretrain and os.path.exists(pretrain):
        old = torch.load(pretrain, map_location="cpu")
        cur = net.state_dict()
        copied = 0
        for k, v in old.items():
            if k in cur and cur[k].shape == v.shape:
                cur[k] = v
                copied += 1
        net.load_state_dict(cur)
        print(f"  warm-start copied tensors: {copied}")

    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=float(conf.get("weight_decay", 1e-4)))
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="min", patience=12, factor=0.5)
    losses, val_dists = [], []
    best, no_improve = float("inf"), 0

    print("Step 4: train")
    for epoch in range(epochs):
        net.train()
        order = train_idx.copy()
        random.shuffle(order)
        ramp = min(1.0, max(0.0, (epoch + 1 - warmup_epochs) / 20.0))
        total = 0.0
        residual_mag_sum = 0.0
        residual_mag_count = 0
        residual_mag_max = 0.0
        reg_active_steps = 0
        steps = 0
        for start in range(0, len(order), batch_size):
            ids = order[start:start + batch_size]
            ids_t = torch.tensor(ids, dtype=torch.long)
            xb = x[ids_t].to(DEVICE)
            if feat_noise > 0:
                noise = torch.randn_like(xb) * feat_std_t.view(1, -1) * feat_noise
                noise[:, 18:21] = 0.0
                xb = xb + noise
            gnss_b = gnss[ids_t].to(DEVICE)
            gt_b = gt[ids_t].to(DEVICE)
            vel_b = vel[ids_t].to(DEVICE)

            pos_norm, vel_norm, log_var, _ = pinn_forward(net, xb)
            target_norm = (gt_b - gnss_b) / corr_std_t
            l_data = nll_or_huber(pos_norm, target_norm, log_var)
            l_vel = F.mse_loss(vel_norm, (vel_b - vel_mean_t) / vel_std_t)
            l_kin = torch.tensor(0.0, device=DEVICE)
            l_alt = torch.tensor(0.0, device=DEVICE)
            residual_mag = torch.norm(pos_norm, dim=1)
            l_res_reg = F.relu(residual_mag - 2.0).mean()

            seq_mask = seq_t[ids_t]
            if seq_mask.any():
                curr = ids_t[seq_mask]
                prev = curr - 1
                prev_x = x[prev].to(DEVICE)
                with torch.no_grad():
                    prev_pos, _, _, _ = pinn_forward(net, prev_x)
                corr_change = pos_norm[seq_mask] - prev_pos
                dt_b = dt_t[curr].to(DEVICE).unsqueeze(1).clamp(0.01, 2.0)
                vel_avg = (vel[curr].to(DEVICE) + vel[prev].to(DEVICE)) * 0.5
                expected_disp = vel_avg * dt_b - gnss_disp[curr].to(DEVICE)
                l_kin = F.huber_loss(corr_change, expected_disp / corr_std_t, delta=2.0)

                alt_curr = gnss[curr, 2].to(DEVICE) + pos_norm[seq_mask, 2] * corr_std_t[2]
                alt_prev = gnss[prev, 2].to(DEVICE) + prev_pos[:, 2] * corr_std_t[2]
                vertical_rate = (alt_curr - alt_prev) / dt_t[curr].to(DEVICE).clamp(0.01, 2.0)
                l_alt = F.huber_loss(vertical_rate, torch.zeros_like(vertical_rate), delta=0.5)

            loss = l_data + ramp * (lambda_vel * l_vel + lambda_kin * l_kin + lambda_alt * l_alt) + lambda_smth * l_res_reg
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            total += float(loss.item())
            residual_mag_sum += float(residual_mag.detach().sum().item())
            residual_mag_count += int(residual_mag.numel())
            residual_mag_max = max(residual_mag_max, float(residual_mag.detach().max().item()))
            if float(l_res_reg.detach().item()) > 1e-8:
                reg_active_steps += 1
            steps += 1

        net.eval()
        with torch.no_grad():
            val_t = torch.tensor(val_idx, dtype=torch.long)
            pv, _, _, _ = pinn_forward(net, x[val_t].to(DEVICE))
            pred = gnss[val_t].to(DEVICE) + pv * corr_std_t
            pred[:, 2] += up_bias_t
            val_dist = torch.norm(pred - gt_true[val_t].to(DEVICE), dim=1).mean().item()
        sched.step(val_dist)
        losses.append(total / max(steps, 1))
        val_dists.append(val_dist)
        print(
            f"[Epoch {epoch + 1:03d}/{epochs}] loss={losses[-1]:.4f} "
            f"val3d={val_dist:.3f}m ramp={ramp:.2f} lr={opt.param_groups[0]['lr']:.2e} "
            f"res_mag_mean={residual_mag_sum / max(residual_mag_count, 1):.3f} "
            f"res_mag_max={residual_mag_max:.3f} reg_steps={reg_active_steps}/{steps}"
        )
        if val_dist < best:
            best, no_improve = val_dist, 0
            torch.save(net.state_dict(), os.path.join(conf["model"], "pinn_fusion_best.pth"))
        else:
            if epoch >= warmup_epochs:
                no_improve += 1
        if epoch >= warmup_epochs and epoch + 1 >= early_stop_min and no_improve >= early_stop_pat:
            print(f"Early stop at epoch {epoch + 1}; best={best:.3f}m")
            break

    torch.save(net.state_dict(), os.path.join(conf["model"], "pinn_fusion_final.pth"))
    if not os.path.exists(os.path.join(conf["model"], "pinn_fusion_best.pth")):
        torch.save(net.state_dict(), os.path.join(conf["model"], "pinn_fusion_best.pth"))

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    ax[0].plot(np.arange(1, len(losses) + 1), losses)
    ax[0].set_title("Train Loss")
    ax[1].plot(np.arange(1, len(val_dists) + 1), val_dists)
    ax[1].set_title("Validation 3D Error")
    for a in ax:
        a.grid(alpha=0.3, linestyle="--")
        a.set_xlabel("Epoch")
    fig.tight_layout()
    fig.savefig(os.path.join(result_path, "loss_curves_fixed.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)

    net.load_state_dict(torch.load(os.path.join(conf["model"], "pinn_fusion_best.pth"), map_location=DEVICE))
    net.eval()
    with torch.no_grad():
        pos_norm, _, _, _ = pinn_forward(net, x.to(DEVICE))
        pred_all = gnss.to(DEVICE) + pos_norm * corr_std_t
        pred_all[:, 2] += up_bias_t
        pred_all = pred_all.cpu().numpy()

    gnss_2d = np.linalg.norm(gnss_np[:, :2] - gt_np[:, :2], axis=1)
    gnss_3d = np.linalg.norm(gnss_np - gt_np, axis=1)
    pinn_2d = np.linalg.norm(pred_all[:, :2] - gt_np[:, :2], axis=1)
    pinn_3d = np.linalg.norm(pred_all - gt_np, axis=1)

    print("\n最终评估 (best 模型) ...")
    print()
    print(f"  {'方法':<25} {'2D Mean(m)':>12} {'3D Mean(m)':>12} {'RMS 2D':>12}")
    print(f"  {'-' * 65}")
    print(f"  {'GNSS Only':<25} {gnss_2d.mean():>12.4f} {gnss_3d.mean():>12.4f} {np.sqrt(np.mean(gnss_2d ** 2)):>12.4f}")
    print(f"  {'PINN IMU+GNSS':<25} {pinn_2d.mean():>12.4f} {pinn_3d.mean():>12.4f} {np.sqrt(np.mean(pinn_2d ** 2)):>12.4f}")
    print()
    print(f"  Best validation 3D error: {best:.4f} m")
    print(f"  2D improvement: {(1.0 - pinn_2d.mean() / max(gnss_2d.mean(), 1e-6)) * 100.0:+.2f}%")


if __name__ == "__main__":
    main()
