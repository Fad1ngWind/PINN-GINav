import json
import os
import sys

import matplotlib
import numpy as np
import pymap3d as p3d
import pyrtklib as prl
import torch
from tqdm import tqdm

import rtk_util as util
from imu_pinn_train_fixed import (
    EXTRA_DIM,
    MOTION_DIM,
    SAT_COUNT,
    SAT_FEATURE_DIM,
    build_feature_vector,
    extract_imu_features,
    get_imu_segment,
    get_ublox_vel,
    load_gt,
    load_json,
    load_ublox_pvt,
    match_gt,
    pinn_forward,
    valid_obs_records,
)
from model import PINNFusionNet, PINN_EXT_INPUT_DIM

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def save_csv(rows, path, header):
    if rows:
        np.savetxt(path, np.array(rows), delimiter=",", header=header, comments="")


def plot_timeseries(time_s, gnss_2d, pinn_2d, sigma_3d, result_path):
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    ax[0].plot(time_s, gnss_2d, color="#3B82F6", lw=1.2, alpha=0.75, label="GNSS Only")
    ax[0].plot(time_s, pinn_2d, color="#EF4444", lw=1.2, alpha=0.85, label="PINN-GINav")
    ax[0].set_ylabel("2D Error (m)")
    ax[0].set_title("Position Error")
    ax[0].legend()
    ax[1].plot(time_s, sigma_3d, color="#10B981", lw=1.2, label="Predicted 3D sigma")
    ax[1].set_xlabel("Time (s)")
    ax[1].set_ylabel("Uncertainty (norm)")
    ax[1].legend()
    for a in ax:
        a.grid(alpha=0.3, linestyle="--")
    fig.tight_layout()
    fig.savefig(os.path.join(result_path, "error_uncertainty_timeseries.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def smoothness_metric(pos_enu):
    if len(pos_enu) < 3:
        return 0.0
    acc_like = np.diff(pos_enu, n=2, axis=0)
    return float(np.mean(np.linalg.norm(acc_like, axis=1)))


def main():
    print(f"Using device: {DEVICE}")
    config = sys.argv[1] if len(sys.argv) > 1 else "config/imu/ingvio_pinn_predict.json"
    conf = load_json(config)
    result_path = os.path.join("result", "imu", os.path.basename(config).replace(".json", ""))
    os.makedirs(result_path, exist_ok=True)

    print("Step 1: load observations")
    obs, nav, _ = util.read_obs(conf["obs"], conf["eph"], ref=conf.get("base"))
    prl.sortobs(obs)
    obss = util.split_obs(obs)
    imu_df = util.load_imu_data(conf["imu"])
    if imu_df is None:
        raise RuntimeError("failed to load IMU")
    pvt_df = load_ublox_pvt(conf["ublox_pvt"])
    gt_df = load_gt(conf["gt"], conf.get("gt_leap_seconds", False)) if conf.get("gt") else None
    obss = [
        o
        for o in obss
        if (
            lambda t: t > conf["start_time"] and (conf["end_time"] == -1 or t < conf["end_time"])
        )(o.data[0].time.time + o.data[0].time.sec)
    ]
    print(f"  epochs={len(obss)}")

    norm_path = os.path.join(conf["model"], "pinn_corr_norm.npz")
    if not os.path.exists(norm_path):
        raise FileNotFoundError(f"missing norm file: {norm_path}; run imu_pinn_train.py first")
    norm = np.load(norm_path)
    if "input_dim" not in norm or int(norm["input_dim"][0]) != PINN_EXT_INPUT_DIM:
        raise RuntimeError(
            "The existing PINN normalization file is from the legacy 42-D model. "
            "Run imu_pinn_train.py with the fixed 78-D implementation before prediction."
        )
    corr_std = norm["std"].astype(np.float32)
    corr_clip = norm["corr_clip"].astype(np.float32) if "corr_clip" in norm else np.maximum(corr_std * 3.0, 5.0)
    up_bias = float(norm["up_bias"][0]) if "up_bias" in norm else 0.0
    vel_mean = norm["vel_mean"].astype(np.float32) if "vel_mean" in norm else np.zeros(3, dtype=np.float32)
    vel_std = norm["vel_std"].astype(np.float32) if "vel_std" in norm else np.ones(3, dtype=np.float32)
    pad = {
        "snr": float(norm["pad_snr"][0]) if "pad_snr" in norm else 30.0,
        "el": float(norm["pad_el"][0]) if "pad_el" in norm else 0.3,
        "res": float(norm["pad_res"][0]) if "pad_res" in norm else 0.0,
    }
    print(f"  corr_std={corr_std.round(3)} corr_clip={corr_clip.round(3)} up_bias={up_bias:.3f}")

    ckpt = os.path.join(conf["model"], "pinn_fusion_best.pth")
    if not os.path.exists(ckpt):
        ckpt = os.path.join(conf["model"], "pinn_fusion_final.pth")
    if not os.path.exists(ckpt):
        raise FileNotFoundError(f"missing checkpoint: {ckpt}")

    net = PINNFusionNet(
        imean=torch.zeros(PINN_EXT_INPUT_DIM),
        istd=torch.ones(PINN_EXT_INPUT_DIM),
        motion_dim=MOTION_DIM,
        sat_count=SAT_COUNT,
        sat_feature_dim=SAT_FEATURE_DIM,
        extra_dim=EXTRA_DIM,
        use_sat_attention=True,
        uncertainty=True,
    )
    net.load_state_dict(torch.load(ckpt, map_location=DEVICE))
    net = net.to(DEVICE)
    net.eval()
    print(f"Step 2: loaded {ckpt}")

    gnss_geo_rows, pinn_geo_rows, gt_rows = [], [], []
    gnss_enu_rows, pinn_enu_rows = [], []
    traj_rows = []
    errors = []
    sigma_rows = []
    attn_rows = []
    ref_geo = None
    prev_t = None
    prev_res_by_rank = {}
    t0 = None
    failed = 0

    print("Step 3: predict")
    for o in tqdm(obss, desc="predict"):
        curr_t = o.data[0].time.time + o.data[0].time.sec
        try:
            ret = util.robust_wls_pnt_pos(o, nav)
        except Exception:
            failed += 1
            prev_t = None
            prev_res_by_rank = {}
            continue
        if not ret.get("status", False):
            failed += 1
            prev_t = None
            prev_res_by_rank = {}
            continue

        gnss_geo = p3d.ecef2geodetic(*ret["pos"][:3])
        gt_geo = match_gt(gt_df, curr_t) if gt_df is not None else None
        if ref_geo is None:
            ref_geo = gt_geo if gt_geo is not None else gnss_geo
        if t0 is None:
            t0 = curr_t

        gnss_enu = np.array(p3d.geodetic2enu(*gnss_geo, *ref_geo), dtype=np.float64)
        vel = get_ublox_vel(pvt_df, curr_t)
        imu_feat = extract_imu_features(get_imu_segment(imu_df, prev_t, curr_t)) if prev_t is not None else extract_imu_features(None)
        feat = build_feature_vector(imu_feat, vel, ret, valid_obs_records(o), prev_res_by_rank, pad)

        with torch.no_grad():
            x = torch.tensor(feat, dtype=torch.float32).unsqueeze(0).to(DEVICE)
            pos_norm, vel_norm, log_var, attn = pinn_forward(net, x)
            corr_m = pos_norm[0].cpu().numpy() * corr_std
            sigma = np.exp(0.5 * log_var[0].cpu().numpy()) * corr_std if log_var is not None else corr_std
            vel_ms = vel_norm[0].cpu().numpy() * vel_std + vel_mean

        corr_m = np.clip(corr_m, -corr_clip, corr_clip)
        pinn_enu = gnss_enu + corr_m
        pinn_enu[2] += up_bias
        pinn_geo = p3d.enu2geodetic(*pinn_enu, *ref_geo)

        gnss_geo_rows.append(gnss_geo)
        pinn_geo_rows.append(pinn_geo)
        gnss_enu_rows.append(gnss_enu)
        pinn_enu_rows.append(pinn_enu)
        sigma_rows.append(sigma)
        if attn is not None:
            attn_rows.append(attn[0].cpu().numpy())

        if gt_geo is not None:
            gt_rows.append(gt_geo)
            gt_enu = np.array(p3d.geodetic2enu(*gt_geo, *ref_geo), dtype=np.float64)
            gnss_err = np.array(p3d.geodetic2enu(*gnss_geo, *gt_geo), dtype=np.float64)
            pinn_err = np.array(p3d.geodetic2enu(*pinn_geo, *gt_geo), dtype=np.float64)
            errors.append(
                [
                    curr_t - t0,
                    np.linalg.norm(gnss_err[:2]),
                    np.linalg.norm(gnss_err),
                    np.linalg.norm(pinn_err[:2]),
                    np.linalg.norm(pinn_err),
                    np.linalg.norm(vel_ms - vel),
                    np.linalg.norm(sigma),
                ]
            )
            traj_rows.append(
                [
                    curr_t - t0,
                    *gt_enu,
                    *gnss_enu,
                    *pinn_enu,
                ]
            )

        prev_t = curr_t

    save_csv(gnss_geo_rows, os.path.join(result_path, "gnss_only_pos.csv"), "lat,lon,height")
    save_csv(pinn_geo_rows, os.path.join(result_path, "pinn_ginav_pos.csv"), "lat,lon,height")
    save_csv(gt_rows, os.path.join(result_path, "gt.csv"), "lat,lon,height")
    save_csv(
        traj_rows,
        os.path.join(result_path, "trajectory_enu.csv"),
        "time_s,gt_E,gt_N,gt_U,gnss_E,gnss_N,gnss_U,pinn_E,pinn_N,pinn_U",
    )
    save_csv(sigma_rows, os.path.join(result_path, "pinn_uncertainty.csv"), "sigma_E,sigma_N,sigma_U")
    save_csv(attn_rows, os.path.join(result_path, "satellite_attention.csv"), ",".join([f"sat{i+1}" for i in range(SAT_COUNT)]))

    print("=" * 60)
    print(f"  Total:{len(obss)}  Valid:{len(pinn_geo_rows)}  Failed:{failed}  NaN:0")
    print("=" * 60)
    if errors:
        err = np.array(errors)
        np.savetxt(
            os.path.join(result_path, "errors.csv"),
            err,
            delimiter=",",
            header="time_s,gnss_2d,gnss_3d,pinn_2d,pinn_3d,vel_err,pred_sigma_3d",
            comments="",
        )
        plot_timeseries(err[:, 0], err[:, 1], err[:, 3], err[:, 6], result_path)
        g2, g3, p2, p3v = err[:, 1], err[:, 2], err[:, 3], err[:, 4]
        gnss_smooth = smoothness_metric(np.array(gnss_enu_rows))
        pinn_smooth = smoothness_metric(np.array(pinn_enu_rows))
        print()
        print(f"  {'方法':<25} {'2D Mean':>10} {'2D RMS':>10} {'3D Mean':>10} {'95th 2D':>10}")
        print(f"  {'-' * 68}")
        print(f"  {'GNSS Only':<25} {g2.mean():>10.4f} {np.sqrt(np.mean(g2**2)):>10.4f} {g3.mean():>10.4f} {np.percentile(g2,95):>10.4f}")
        print(f"  {'PINN IMU+GNSS v2':<25} {p2.mean():>10.4f} {np.sqrt(np.mean(p2**2)):>10.4f} {p3v.mean():>10.4f} {np.percentile(p2,95):>10.4f}")
        print()
        print(f"  2D improvement: {(1.0 - p2.mean() / max(g2.mean(), 1e-6)) * 100.0:+.2f}%")
        print(f"  Trajectory smoothness: GNSS={gnss_smooth:.4f}, PINN-GINav={pinn_smooth:.4f}")
        print(f"  Velocity error mean: {err[:,5].mean():.4f} m/s")
        print(f"  Predicted sigma mean: {err[:,6].mean():.4f}")


if __name__ == "__main__":
    main()
