# TDL-GNSS

[Chinese README](README_zh.md)

TDL-GNSS is a GNSS/INS integrated navigation project centered on the finalized `*_fixed.py` pipelines and the paper-ready PINN-GINav experiments.

## Overview

This release focuses on the final, reproducible version of the project rather than the full historical workspace. It includes:

- Final non-PINN pipeline:
  - `imu_train_fixed.py`
  - `imu_predict_fixed.py`
- Final PINN pipeline:
  - `imu_pinn_train_fixed.py`
  - `imu_pinn_predict_fixed.py`
- Shared core modules:
  - `model.py`
  - `rtk_util.py`
  - `evaluate.py`
  - `paper_figures.py`
- Final configurations:
  - `config/imu/ingvio_train.json`
  - `config/imu/ingvio_predict.json`
  - `config/imu/ingvio_pinn_train.json`
  - `config/imu/ingvio_pinn_predict.json`
- Final released checkpoints:
  - `model/imu_fusion_v1/`
  - `model/pinn_fusion_v1/`
- Final results and paper assets:
  - `paper_data.json`
  - `ablation_seeds.csv`
  - `FINAL_RESULTS.md`
  - `figures/`
  - `result/imu/ingvio_predict/`
  - `result/imu/ingvio_pinn_predict/`

## Final Results

- GNSS 3D RMSE: `36.031403 m`
- Non-PINN 3D RMSE: `17.747945 m`
- PINN 3D RMSE: `13.093327 m`

Official released settings:

- Non-PINN: `seed=123`, `lr=0.00025`, `pred_reg=0.02`
- PINN: `seed=42`, `lambda_vel=0`, `lambda_kin=0.05`, `lambda_smth=0.05`

## Main Findings

- The largest gain came from fixing the `18 s` GPS/UTC leap-second mismatch.
- `up_bias` must be preserved consistently in both training and prediction.
- `L_kin` is a positive contributor.
- `L_vel` is a negative contributor under the fixed multi-seed protocol.
- `L_reg` is clearly beneficial for PINN, but harmful or non-beneficial for non-PINN.

## Installation

```bash
pip install -r requirements.txt
```

## Data Layout

This repository does not include the full raw GVINS dataset because some source files exceed standard GitHub file-size limits.

Expected dataset layout:

```text
data/
  GVINS/
    urban_driving/
      urban.obs
      urban.nav
      ground_truth.csv
      imu0.csv
      ublox_driver-receiver_pvt.csv
```

The released configs in `config/imu/` already use these relative paths.

## Usage

Train non-PINN:

```bash
python imu_train_fixed.py config/imu/ingvio_train.json
```

Predict non-PINN:

```bash
python imu_predict_fixed.py config/imu/ingvio_predict.json
```

Train PINN:

```bash
python imu_pinn_train_fixed.py config/imu/ingvio_pinn_train.json
```

Predict PINN:

```bash
python imu_pinn_predict_fixed.py config/imu/ingvio_pinn_predict.json
```

Generate 3D paper figures:

```bash
python paper_figures.py ^
  --errors_csv result/imu/ingvio_predict/errors.csv ^
  --pinn_csv result/imu/ingvio_pinn_predict/errors.csv ^
  --paper_data paper_data.json ^
  --ablation_csv ablation_seeds.csv ^
  --only_3d ^
  --outdir figures
```

## Notes

- This release intentionally excludes unrelated folders such as `KLTDataset/`, `figures4papers-main/`, temporary figure test folders, and historical model backups.
- The `*_fixed.py` files are the authoritative mainline scripts for this released version.
- For paper writing and result verification, treat `paper_data.json`, `ablation_seeds.csv`, and `FINAL_RESULTS.md` as the authoritative sources.
