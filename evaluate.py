import argparse
import os
import subprocess
import sys
import time

import numpy as np


def result_dir_from_config(config_path):
    tag = os.path.basename(config_path).replace(".json", "")
    return os.path.join("result", "imu", tag)


def load_errors(errors_path):
    if not os.path.exists(errors_path):
        raise FileNotFoundError(f"missing errors.csv: {errors_path}")
    data = np.loadtxt(errors_path, delimiter=",", skiprows=1)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] < 5:
        raise RuntimeError(f"errors.csv must contain at least 5 columns, got {data.shape[1]}")
    return data


def smoothness(values):
    if len(values) < 3:
        return 0.0
    second_diff = np.diff(values, n=2)
    return float(np.sqrt(np.mean(second_diff ** 2)))


def compute_metrics(data):
    gnss_2d = data[:, 1]
    gnss_3d = data[:, 2]
    fusion_2d = data[:, 3]
    fusion_3d = data[:, 4]
    metrics = {
        "N_EPOCHS": float(len(data)),
        "RMSE_GNSS_2D": float(np.sqrt(np.mean(gnss_2d ** 2))),
        "RMSE_GNSS_3D": float(np.sqrt(np.mean(gnss_3d ** 2))),
        "RMSE_POS_2D": float(np.sqrt(np.mean(fusion_2d ** 2))),
        "RMSE_POS_3D": float(np.sqrt(np.mean(fusion_3d ** 2))),
        "MEAN_POS_2D": float(np.mean(fusion_2d)),
        "MEAN_POS_3D": float(np.mean(fusion_3d)),
        "P95_POS_2D": float(np.percentile(fusion_2d, 95)),
        "P95_POS_3D": float(np.percentile(fusion_3d, 95)),
        "IMPROVE_2D_PCT": float((1.0 - np.mean(fusion_2d) / max(np.mean(gnss_2d), 1e-9)) * 100.0),
        "SMOOTH_POS_2D": smoothness(fusion_2d),
        "SCORE": float(np.sqrt(np.mean(fusion_3d ** 2))),
    }
    return metrics


def print_metrics(metrics, elapsed_s):
    ordered = [
        ("N_EPOCHS", "{:.0f}"),
        ("RMSE_POS_2D", "{:.6f}m"),
        ("RMSE_POS_3D", "{:.6f}m"),
        ("RMSE_GNSS_2D", "{:.6f}m"),
        ("RMSE_GNSS_3D", "{:.6f}m"),
        ("MEAN_POS_2D", "{:.6f}m"),
        ("P95_POS_2D", "{:.6f}m"),
        ("IMPROVE_2D_PCT", "{:.6f}%"),
        ("SMOOTH_POS_2D", "{:.6f}m"),
        ("SCORE", "{:.6f}"),
    ]
    for key, fmt in ordered:
        print(f"{key}: {fmt.format(metrics[key])}")
    print(f"EVAL_TIME_SEC: {elapsed_s:.3f}")


def run_predict(python_exe, predict_script, config, verbose):
    cmd = [python_exe, predict_script, config]
    if verbose:
        subprocess.run(cmd, check=True)
    else:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0:
            tail = "\n".join(proc.stdout.splitlines()[-40:])
            raise RuntimeError(f"prediction failed with code {proc.returncode}\n{tail}")


def main():
    parser = argparse.ArgumentParser(description="Fast scalar evaluation entrypoint for optimization loops.")
    parser.add_argument("--config", default="config/imu/ingvio_predict_mini.json")
    parser.add_argument("--predict-script", default="imu_predict.py")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--no-run", action="store_true", help="Only parse existing result/imu/<tag>/errors.csv.")
    parser.add_argument("--verbose", action="store_true", help="Show underlying prediction output.")
    args = parser.parse_args()

    start = time.time()
    if not args.no_run:
        run_predict(args.python, args.predict_script, args.config, args.verbose)

    errors_path = os.path.join(result_dir_from_config(args.config), "errors.csv")
    metrics = compute_metrics(load_errors(errors_path))
    print_metrics(metrics, time.time() - start)


if __name__ == "__main__":
    main()
