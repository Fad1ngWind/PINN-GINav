# TDL-GNSS

[English](README.md)

TDL-GNSS 是一个面向最终发布版本的 GNSS/INS 融合导航项目仓库，核心内容围绕已经定稿的 `*_fixed.py` 主链路和论文版 PINN-GINav 实验结果展开。

## 项目概览

这个发布目录保留的是当前可复现、可写论文、可继续维护的正式版本，而不是整个历史实验工作区。主要包含：

- 最终 non-PINN 主链路：
  - `imu_train_fixed.py`
  - `imu_predict_fixed.py`
- 最终 PINN 主链路：
  - `imu_pinn_train_fixed.py`
  - `imu_pinn_predict_fixed.py`
- 共用核心模块：
  - `model.py`
  - `rtk_util.py`
  - `evaluate.py`
  - `paper_figures.py`
- 最终配置文件：
  - `config/imu/ingvio_train.json`
  - `config/imu/ingvio_predict.json`
  - `config/imu/ingvio_pinn_train.json`
  - `config/imu/ingvio_pinn_predict.json`
- 最终发布模型：
  - `model/imu_fusion_v1/`
  - `model/pinn_fusion_v1/`
- 最终结果与论文资产：
  - `paper_data.json`
  - `ablation_seeds.csv`
  - `FINAL_RESULTS.md`
  - `figures/`
  - `result/imu/ingvio_predict/`
  - `result/imu/ingvio_pinn_predict/`

## 最终结果

- GNSS 3D RMSE：`36.031403 m`
- non-PINN 3D RMSE：`17.747945 m`
- PINN 3D RMSE：`13.093327 m`

正式发布配置：

- non-PINN：`seed=123`，`lr=0.00025`，`pred_reg=0.02`
- PINN：`seed=42`，`lambda_vel=0`，`lambda_kin=0.05`，`lambda_smth=0.05`

## 关键结论

- 最大的性能提升来自修复 `18 s` 的 GPS/UTC 闰秒错位问题。
- `up_bias` 必须在训练和预测中保持一致保留。
- `L_kin` 是正贡献项。
- 在固定多 seed 协议下，`L_vel` 是负贡献项。
- `L_reg` 对 PINN 明显有益，但对 non-PINN 有害或至少不利。

## 安装

```bash
pip install -r requirements.txt
```

## 数据说明

本仓库没有直接包含完整的 GVINS 原始数据，因为其中部分文件超过了 GitHub 普通仓库的体积限制。

期望的数据目录结构如下：

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

`config/imu/` 中的正式配置已经改成上述相对路径。

## 使用方式

训练 non-PINN：

```bash
python imu_train_fixed.py config/imu/ingvio_train.json
```

预测 non-PINN：

```bash
python imu_predict_fixed.py config/imu/ingvio_predict.json
```

训练 PINN：

```bash
python imu_pinn_train_fixed.py config/imu/ingvio_pinn_train.json
```

预测 PINN：

```bash
python imu_pinn_predict_fixed.py config/imu/ingvio_pinn_predict.json
```

生成论文 3D 图：

```bash
python paper_figures.py ^
  --errors_csv result/imu/ingvio_predict/errors.csv ^
  --pinn_csv result/imu/ingvio_pinn_predict/errors.csv ^
  --paper_data paper_data.json ^
  --ablation_csv ablation_seeds.csv ^
  --only_3d ^
  --outdir figures
```

## 备注

- 这个发布包有意排除了与当前项目无关或不应一并公开的目录，例如 `KLTDataset/`、`figures4papers-main/`、各种临时绘图测试目录以及历史模型备份。
- 当前版本中，`*_fixed.py` 文件是正式主版本。
- 如果用于论文撰写或结果核对，应以 `paper_data.json`、`ablation_seeds.csv` 和 `FINAL_RESULTS.md` 作为事实来源。
