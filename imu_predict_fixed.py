import json
import os
import sys
from collections import deque

import matplotlib
import numpy as np
import pandas as pd
import pymap3d as p3d
import pyrtklib as prl
import torch
from tqdm import tqdm

import rtk_util as util
from model import IMUFusionNet, IMUFusionNetLSTM, IMUFusionNetSmall, IMU_GNSS_INPUT_DIM

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def save_csv(rows, path, header):
    if rows:
        np.savetxt(path, np.array(rows), delimiter=",", header=header, comments="")


def mc_predict(net, x, samples=1):
    if samples <= 1:
        net.eval()
        with torch.no_grad():
            pred = net(x)
        return pred.cpu().numpy(), np.zeros_like(pred.cpu().numpy())

    was_training = net.training
    net.train()
    preds = []
    with torch.no_grad():
        for _ in range(samples):
            preds.append(net(x).cpu().numpy())
    if not was_training:
        net.eval()
    preds = np.stack(preds, axis=0)
    return preds.mean(axis=0), preds.std(axis=0)


def plot_errors(time_s, gnss_2d, fusion_2d, result_path):
    if len(time_s) == 0:
        return
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(time_s, gnss_2d, color="#3B82F6", alpha=0.7, lw=1.2, label="GNSS Only")
    ax.plot(time_s, fusion_2d, color="#EF4444", alpha=0.8, lw=1.2, label="IMU+GNSS")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("2D Error (m)")
    ax.set_title("Prediction Error Over Time")
    ax.grid(alpha=0.3, linestyle="--")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(result_path, "error_timeseries.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def main():
    print(f"Using device: {DEVICE}")
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/imu/ingvio_predict.json"
    conf = load_json(config_path)

    result_tag = os.path.basename(config_path).replace(".json", "")
    result_path = os.path.join("result", "imu", result_tag)
    os.makedirs(result_path, exist_ok=True)

    use_lstm = conf.get("imu_window", 0) > 0
    lstm_win = int(conf.get("imu_window", 10))
    mc_samples = int(conf.get("mc_dropout", 1))

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

    gt_df = None
    if conf.get("gt"):
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

    norm_path = os.path.join(conf["model"], "imu_corr_norm.npz")
    if os.path.exists(norm_path):
        norm_data = np.load(norm_path)
        corr_std = norm_data["std"].astype(np.float32)
        corr_clip = norm_data["corr_clip"].astype(np.float32) if "corr_clip" in norm_data else np.maximum(corr_std * 4.0, 5.0)
        up_bias = float(norm_data["up_bias"][0]) if "up_bias" in norm_data else 0.0
        model_arch = str(norm_data["model_arch"][0]) if "model_arch" in norm_data else conf.get("model_arch", "large")
        pad_snr = float(norm_data["pad_snr"][0]) if "pad_snr" in norm_data else 0.0
        pad_el = float(norm_data["pad_el"][0]) if "pad_el" in norm_data else 0.0
        pad_res = float(norm_data["pad_res"][0]) if "pad_res" in norm_data else 0.0
    else:
        corr_std = np.ones(3, dtype=np.float32)
        corr_clip = np.full(3, 5.0, dtype=np.float32)
        up_bias = 0.0
        model_arch = conf.get("model_arch", "large")
        pad_snr = pad_el = pad_res = 0.0
    print(f"  correction std={corr_std.round(3)} clip={corr_clip.round(3)} up_bias={up_bias:.3f}")

    ckpt = os.path.join(conf["model"], "imu_fusion_best.pth")
    if not os.path.exists(ckpt):
        ckpt = os.path.join(conf["model"], "imu_fusion_final.pth")
    if not os.path.exists(ckpt):
        raise FileNotFoundError(f"missing checkpoint: {ckpt}")

    if use_lstm:
        net = IMUFusionNetLSTM(torch.zeros(IMU_GNSS_INPUT_DIM), torch.ones(IMU_GNSS_INPUT_DIM))
    elif model_arch == "small":
        net = IMUFusionNetSmall(torch.zeros(IMU_GNSS_INPUT_DIM), torch.ones(IMU_GNSS_INPUT_DIM))
    else:
        net = IMUFusionNet(torch.zeros(IMU_GNSS_INPUT_DIM), torch.ones(IMU_GNSS_INPUT_DIM))
    net.load_state_dict(torch.load(ckpt, map_location=DEVICE))
    net = net.to(DEVICE)
    net.eval()
    print(f"Step 3: Loaded model {ckpt} (arch={model_arch}, mc_dropout={mc_samples})")

    gnss_only_pos = []
    fusion_pos = []
    gt_rows = []
    traj_rows = []
    time_axis = []
    err_gnss_2d = []
    err_gnss_3d = []
    err_fusion_2d = []
    err_fusion_3d = []

    ref_geo = None
    prev_t = None
    prev_enu = None
    t0_epoch = None
    vel_filter = MedianVelFilter()
    feat_buffer = []
    valid_epochs = 0
    failed_epochs = 0

    print("Step 4: Predicting")
    for o in tqdm(obss, desc="predict"):
        curr_t = o.data[0].time.time + o.data[0].time.sec
        try:
            ret = util.robust_wls_pnt_pos(o, nav)
        except Exception:
            prev_t = None
            prev_enu = None
            vel_filter.reset()
            failed_epochs += 1
            continue
        if not ret["status"]:
            prev_t = None
            prev_enu = None
            vel_filter.reset()
            failed_epochs += 1
            continue

        gnss_geo = p3d.ecef2geodetic(*ret["pos"][:3])
        gt_geo = match_gt(gt_df, curr_t) if gt_df is not None else None

        if ref_geo is None:
            ref_geo = gt_geo if gt_geo is not None else gnss_geo
        if t0_epoch is None:
            t0_epoch = curr_t

        gnss_enu = np.array(p3d.geodetic2enu(*gnss_geo, *ref_geo), dtype=np.float64)
        if pvt_df is not None:
            vel = get_ublox_vel(pvt_df, curr_t)
        elif prev_t is not None and prev_enu is not None:
            vel = vel_filter.update((gnss_enu - prev_enu) / max(curr_t - prev_t, 1e-3))
        else:
            vel = np.zeros(3, dtype=np.float64)

        imu_feat = extract_imu_features(get_imu_segment(imu_df, prev_t, curr_t)) if prev_t is not None else extract_imu_features(None)
        feat = build_feature_vector(imu_feat, vel, ret, pad_snr, pad_el, pad_res)

        with torch.no_grad():
            if use_lstm:
                feat_buffer.append(feat)
                if len(feat_buffer) < lstm_win:
                    corr_m = np.zeros(3, dtype=np.float32)
                else:
                    seq = torch.tensor(np.array(feat_buffer[-lstm_win:]), dtype=torch.float32).unsqueeze(0).to(DEVICE)
                    pred_norm, _ = net(seq)
                    corr_m = pred_norm[0, -1, :].cpu().numpy() * corr_std
            else:
                x = torch.tensor(feat, dtype=torch.float32).unsqueeze(0).to(DEVICE)
                pred_norm, pred_std = mc_predict(net, x, samples=mc_samples)
                pred_norm = pred_norm[0]
                corr_m = pred_norm * corr_std

        corr_m = np.clip(corr_m, -corr_clip, corr_clip)
        pred_enu = gnss_enu + corr_m
        pred_enu[2] += up_bias
        pred_geo = p3d.enu2geodetic(*pred_enu, *ref_geo)

        gnss_only_pos.append(gnss_geo)
        fusion_pos.append(pred_geo)
        time_axis.append(curr_t - t0_epoch)

        if gt_geo is not None:
            gt_rows.append(gt_geo)
            gt_enu = np.array(p3d.geodetic2enu(*gt_geo, *ref_geo), dtype=np.float64)
            gnss_err = np.array(p3d.geodetic2enu(*gnss_geo, *gt_geo), dtype=np.float64)
            fuse_err = np.array(p3d.geodetic2enu(*pred_geo, *gt_geo), dtype=np.float64)
            err_gnss_2d.append(np.linalg.norm(gnss_err[:2]))
            err_gnss_3d.append(np.linalg.norm(gnss_err))
            err_fusion_2d.append(np.linalg.norm(fuse_err[:2]))
            err_fusion_3d.append(np.linalg.norm(fuse_err))
            traj_rows.append(
                [
                    curr_t - t0_epoch,
                    *gt_enu,
                    *gnss_enu,
                    *pred_enu,
                ]
            )

        prev_t = curr_t
        prev_enu = gnss_enu
        valid_epochs += 1

    save_csv(gnss_only_pos, os.path.join(result_path, "gnss_only_pos.csv"), "lat,lon,height")
    save_csv(fusion_pos, os.path.join(result_path, "imu_gnss_fusion_pos.csv"), "lat,lon,height")
    save_csv(gt_rows, os.path.join(result_path, "gt.csv"), "lat,lon,height")
    save_csv(
        traj_rows,
        os.path.join(result_path, "trajectory_enu.csv"),
        "time_s,gt_E,gt_N,gt_U,gnss_E,gnss_N,gnss_U,nonpinn_E,nonpinn_N,nonpinn_U",
    )

    if err_gnss_2d:
        np.savetxt(
            os.path.join(result_path, "errors.csv"),
            np.column_stack(
                [
                    np.array(time_axis[: len(err_gnss_2d)]),
                    np.array(err_gnss_2d),
                    np.array(err_gnss_3d),
                    np.array(err_fusion_2d),
                    np.array(err_fusion_3d),
                ]
            ),
            delimiter=",",
            header="time_s,gnss_2d,gnss_3d,fusion_2d,fusion_3d",
            comments="",
        )
        plot_errors(
            np.array(time_axis[: len(err_gnss_2d)]),
            np.array(err_gnss_2d),
            np.array(err_fusion_2d),
            result_path,
        )

    print("=" * 60)
    print(f"  Total:{len(obss)}  Valid:{valid_epochs}  Failed:{failed_epochs}  NaN:0")
    print("=" * 60)
    if err_gnss_2d:
        g2 = np.array(err_gnss_2d)
        g3 = np.array(err_gnss_3d)
        f2 = np.array(err_fusion_2d)
        f3 = np.array(err_fusion_3d)
        print()
        print(f"  {'方法':<25} {'2D Mean':>10} {'2D RMS':>10} {'3D Mean':>10} {'95th 2D':>10}")
        print(f"  {'-' * 68}")
        print(f"  {'GNSS Only':<25} {g2.mean():>10.4f} {np.sqrt(np.mean(g2 ** 2)):>10.4f} {g3.mean():>10.4f} {np.percentile(g2, 95):>10.4f}")
        print(f"  {'IMU+GNSS Fusion':<25} {f2.mean():>10.4f} {np.sqrt(np.mean(f2 ** 2)):>10.4f} {f3.mean():>10.4f} {np.percentile(f2, 95):>10.4f}")
        print()
        print(f"  2D improvement: {(1.0 - f2.mean() / max(g2.mean(), 1e-6)) * 100.0:+.2f}%")
    else:
        print("No ground truth provided, skipped metric summary.")


if __name__ == "__main__":
    main()
