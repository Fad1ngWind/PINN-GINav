# PINN-GINav

**English** | [中文](README_zh.md)

PINN-GINav is a GNSS/INS integrated navigation project that combines data-driven fusion with physics-informed constraints for urban positioning.

## Overview

This repository includes:

- non-PINN GNSS/INS fusion pipeline
- PINN-based GNSS/INS fusion pipeline
- training and prediction scripts
- released checkpoints and normalization files
- evaluation scripts and paper figures
- final experiment tables and result files

## Repository Structure

- `imu_train_fixed.py`, `imu_predict_fixed.py`: non-PINN training and prediction
- `imu_pinn_train_fixed.py`, `imu_pinn_predict_fixed.py`: PINN training and prediction
- `model.py`: model definitions
- `rtk_util.py`: GNSS utility functions
- `evaluate.py`: evaluation helpers
- `paper_figures.py`: figure generation
- `config/imu/`: training and prediction configs
- `model/imu_fusion_v1/`: non-PINN checkpoints
- `model/pinn_fusion_v1/`: PINN checkpoints
- `result/imu/`: exported prediction results
- `figures/`: generated paper figures

## Results

- GNSS 3D RMSE: `36.031403 m`
- Non-PINN 3D RMSE: `17.747945 m`
- PINN 3D RMSE: `13.093327 m`

Main experiment settings:

- Non-PINN: `seed=123`, `lr=0.00025`, `pred_reg=0.02`
- PINN: `seed=42`, `lambda_vel=0`, `lambda_kin=0.05`, `lambda_smth=0.05`

Key findings:

- Fixing the `18 s` GPS/UTC leap-second mismatch produced the largest gain.
- `up_bias` should be kept consistently in training and prediction.
- `L_kin` is beneficial.
- `L_vel` is harmful under the fixed multi-seed protocol.
- `L_reg` helps PINN but does not help non-PINN.

Detailed tables are available in:

- `paper_data.json`
- `ablation_seeds.csv`
- `FINAL_RESULTS.md`

## Installation

```bash
pip install -r requirements.txt
```

## Data

The full raw **GVINS-Dataset** is not included in this repository because some source files exceed standard GitHub file-size limits.

Expected data layout:

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

The configs in `config/imu/` use these relative paths. All finalized experiments in this release are based on **GVINS-Dataset / urban_driving**.

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

Generate 3D figures:

```bash
python paper_figures.py ^
  --errors_csv result/imu/ingvio_predict/errors.csv ^
  --pinn_csv result/imu/ingvio_pinn_predict/errors.csv ^
  --paper_data paper_data.json ^
  --ablation_csv ablation_seeds.csv ^
  --only_3d ^
  --outdir figures
```
