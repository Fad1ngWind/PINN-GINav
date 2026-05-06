# PINN-GINav

[English](README.md) | **中文**

PINN-GINav 是一个面向城市环境定位的 GNSS/INS 融合导航项目，结合了数据驱动融合模型与物理约束机制。

## 项目简介

本仓库包含：

- non-PINN GNSS/INS 融合链路
- 基于 PINN 的 GNSS/INS 融合链路
- 训练与预测脚本
- 已发布的模型权重和归一化文件
- 评估脚本与论文图表生成脚本
- 最终实验结果表与导出结果文件

## 仓库结构

- `imu_train_fixed.py`、`imu_predict_fixed.py`：non-PINN 训练与预测
- `imu_pinn_train_fixed.py`、`imu_pinn_predict_fixed.py`：PINN 训练与预测
- `model.py`：模型定义
- `rtk_util.py`：GNSS 工具函数
- `evaluate.py`：评估辅助脚本
- `paper_figures.py`：图表生成脚本
- `config/imu/`：训练与预测配置
- `model/imu_fusion_v1/`：non-PINN 模型权重
- `model/pinn_fusion_v1/`：PINN 模型权重
- `result/imu/`：预测结果导出目录
- `figures/`：论文图表输出目录

## 结果

- GNSS 3D RMSE：`36.031403 m`
- Non-PINN 3D RMSE：`17.747945 m`
- PINN 3D RMSE：`13.093327 m`

主要实验配置：

- Non-PINN：`seed=123`，`lr=0.00025`，`pred_reg=0.02`
- PINN：`seed=42`，`lambda_vel=0`，`lambda_kin=0.05`，`lambda_smth=0.05`

关键结论：

- 修复 `18 s` 的 GPS/UTC 闰秒错位带来了最大收益。
- `up_bias` 需要在训练和预测中一致保留。
- `L_kin` 是正贡献项。
- 在固定多 seed 协议下，`L_vel` 是负贡献项。
- `L_reg` 对 PINN 有益，但对 non-PINN 无益。

更详细的结果表见：

- `paper_data.json`
- `ablation_seeds.csv`
- `FINAL_RESULTS.md`

## 安装

```bash
pip install -r requirements.txt
```

## 数据

本仓库未直接包含完整 **GVINS-Dataset** 原始数据，因为其中部分文件超过了 GitHub 普通仓库的体积限制。

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

`config/imu/` 中的配置文件使用上述相对路径。本发布版本中的最终实验全部基于 **GVINS-Dataset / urban_driving**。

## 使用

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

生成 3D 图表：

```bash
python paper_figures.py ^
  --errors_csv result/imu/ingvio_predict/errors.csv ^
  --pinn_csv result/imu/ingvio_pinn_predict/errors.csv ^
  --paper_data paper_data.json ^
  --ablation_csv ablation_seeds.csv ^
  --only_3d ^
  --outdir figures
```
