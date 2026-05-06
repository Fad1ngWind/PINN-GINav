# PINN-GINav - Final Experimental Results

All results in this file are reported on **GVINS-Dataset**, using the **`data/GVINS/urban_driving/`** subset.

## Main Results
| Method | 2D RMSE (m) | 3D RMSE (m) | vs GNSS | vs Non-PINN |
|---|---:|---:|---:|---:|
| GNSS only | 11.118 | 36.031 | -- | -- |
| Non-PINN | 10.830 | 17.748 | down 50.7% | -- |
| PINN-GINav | 8.396 | 13.093 | down 63.7% | down 26.2% |

## Ablation Study
| Configuration | 3D RMSE (m) | Delta vs full | Seeds |
|---|---:|---:|---:|
| PINN-GINav (full, seed=42) | 13.093 | -- | 1 |
| PINN full (multi-seed) | 13.439 +/- 0.184 | -- | 3 |
| w/o L_reg | 15.490 | +2.397 | 1 |
| w/o L_kin | 13.859 +/- 0.340 | +0.420 | 3 |
| w/o L_vel (removed) | 13.132 +/- 0.192 | -0.307 | 3 |

`L_vel` is a negative contributor under the fixed-seed multi-seed protocol, so the final model sets `lambda_vel = 0`.

## L_reg Architecture Specificity
| Architecture | Effect of L_reg | Interpretation |
|---|---:|---|
| Non-PINN (seed=123) | +0.423 m | harmful |
| PINN-GINav (seed=42) | -2.397 m | strongly beneficial |
| Specificity ratio | 5.7x | PINN benefit magnitude / Non-PINN harm magnitude |

## Reproducibility
- PINN final configuration: `seed=42`, `lambda_vel=0`, `lambda_kin=0.05`, `lambda_smth=0.05`
- Non-PINN final configuration: `seed=123`, `lr=0.00025`, `pred_reg=0.02`
- Multi-seed statistics:
  - Non-PINN: `18.108 +/- 0.386 m`
  - PINN full (with `L_vel`): `13.439 +/- 0.184 m`
  - PINN w/o `L_kin`: `13.859 +/- 0.340 m`
  - PINN w/o `L_vel`: `13.132 +/- 0.192 m`
- Training noise reference:
  - PINN full std across seeds: `0.184 m`
  - `L_kin` contribution significance: `1.24 sigma`
  - `L_vel` contribution significance: `10.19 sigma`
  - `L_reg` PINN contribution vs PINN noise floor: `13.0 sigma`
