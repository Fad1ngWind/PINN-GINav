import torch
import torch.nn as nn
import torch.nn.functional as F


class StandardizeLayer(nn.Module):
    def __init__(self, mean, std):
        super().__init__()
        if not isinstance(mean, torch.Tensor): mean = torch.tensor(mean)
        if not isinstance(std,  torch.Tensor): std  = torch.tensor(std)
        self.register_buffer('mean', mean.float())
        self.register_buffer('std',  std.float())
    def forward(self, x): return (x - self.mean) / self.std


class DeStandardizeLayer(nn.Module):
    def __init__(self, mean, std):
        super().__init__()
        if not isinstance(mean, torch.Tensor): mean = torch.tensor(mean)
        if not isinstance(std,  torch.Tensor): std  = torch.tensor(std)
        self.register_buffer('mean', mean.float())
        self.register_buffer('std',  std.float())
    def forward(self, x): return x * self.std + self.mean


class BiasNet(nn.Module):
    def __init__(self, imean=0, istd=1, omean=0, ostd=1):
        super().__init__()
        imean = torch.tensor(imean, dtype=torch.float32) if not isinstance(imean, torch.Tensor) else imean.float()
        istd  = torch.tensor(istd,  dtype=torch.float32) if not isinstance(istd,  torch.Tensor) else istd.float()
        omean = torch.tensor(omean, dtype=torch.float32) if not isinstance(omean, torch.Tensor) else omean.float()
        ostd  = torch.tensor(ostd,  dtype=torch.float32) if not isinstance(ostd,  torch.Tensor) else ostd.float()
        self.seq = nn.Sequential(
            StandardizeLayer(imean, istd),
            nn.Linear(len(imean), 64), nn.BatchNorm1d(64), nn.ReLU(),
            nn.Linear(64, 128),        nn.BatchNorm1d(128), nn.ReLU(),
            nn.Linear(128, 1),
            DeStandardizeLayer(omean, ostd))
    def forward(self, x): return self.seq(x)


class BiasNetTest(nn.Module):
    def __init__(self, imean=torch.tensor([0.0]*11), istd=torch.tensor([1.0]*11),
                 omean=torch.tensor([0.0]), ostd=torch.tensor([1.0])):
        super().__init__()
        imean = imean.float() if isinstance(imean, torch.Tensor) else torch.tensor(imean, dtype=torch.float32)
        istd  = istd.float()  if isinstance(istd,  torch.Tensor) else torch.tensor(istd,  dtype=torch.float32)
        omean = omean.float() if isinstance(omean, torch.Tensor) else torch.tensor(omean, dtype=torch.float32)
        ostd  = ostd.float()  if isinstance(ostd,  torch.Tensor) else torch.tensor(ostd,  dtype=torch.float32)
        self.seq = nn.Sequential(
            StandardizeLayer(imean, istd),
            nn.Linear(len(imean), 64), nn.BatchNorm1d(64), nn.ReLU(),
            nn.Linear(64, 128),        nn.BatchNorm1d(128), nn.ReLU(),
            nn.Linear(128, 1),
            DeStandardizeLayer(omean, ostd))
    def set_output_layer(self, omean, ostd):
        if not isinstance(omean, torch.Tensor): omean = torch.tensor(omean, dtype=torch.float32)
        if not isinstance(ostd,  torch.Tensor): ostd  = torch.tensor(ostd,  dtype=torch.float32)
        self.seq[-1] = DeStandardizeLayer(omean, ostd)
    def forward(self, x): return self.seq(x)


class WeightNet(nn.Module):
    def __init__(self, imean=torch.tensor([0.0]*11), istd=torch.tensor([1.0]*11)):
        super().__init__()
        imean = imean.float() if isinstance(imean, torch.Tensor) else torch.tensor(imean, dtype=torch.float32)
        istd  = istd.float()  if isinstance(istd,  torch.Tensor) else torch.tensor(istd,  dtype=torch.float32)
        self.seq = nn.Sequential(
            StandardizeLayer(imean, istd),
            nn.Linear(len(imean), 64), nn.Sigmoid(),
            nn.Linear(64, 128),        nn.Sigmoid(),
            nn.Linear(128, 64),        nn.Sigmoid(),
            nn.Linear(64, 1),          nn.Sigmoid())
    def forward(self, x): return torch.clamp(self.seq(x) * 10, 0, 10)


class HybridNet(nn.Module):
    def __init__(self, imean=torch.tensor([0.0]*11), istd=torch.tensor([1.0]*11)):
        super().__init__()
        self.weightNet = WeightNet(imean, istd)
        self.biasNet   = BiasNet(imean, istd)
    def forward(self, x): return self.weightNet(x), self.biasNet(x)


class HybridShareNet(nn.Module):
    def __init__(self, imean=torch.tensor([0.0]*11), istd=torch.tensor([1.0]*11)):
        super().__init__()
        imean = imean.float() if isinstance(imean, torch.Tensor) else torch.tensor(imean, dtype=torch.float32)
        istd  = istd.float()  if isinstance(istd,  torch.Tensor) else torch.tensor(istd,  dtype=torch.float32)
        self.seq = nn.Sequential(
            StandardizeLayer(imean, istd),
            nn.Linear(len(imean), 64), nn.ReLU(),
            nn.Linear(64, 128),        nn.ReLU(),
            nn.Linear(128, 64),        nn.ReLU(),
            nn.Linear(64, 2))
    def forward(self, x):
        out = self.seq(x)
        return torch.clamp(torch.sigmoid(out[:, 0]), 0, 1), out[:, 1]


# ==============================================================================
# IMUFusionNet v5  —  双分支MLP，42维特征
#
# 特征向量 (42 维):
#   [0:3]   IMU mean_acc
#   [3:6]   IMU mean_gyro
#   [6:9]   IMU std_acc
#   [9:12]  Doppler 速度 ENU (m/s)
#   [12:42] 卫星特征 (10颗 × 3维: SNR, 高度角, 残差)
#
# 输出: ENU 位置修正量归一化值 (归一化后的 Δpos)
#   实际位置 = GNSS_ENU + corr * corr_std + corr_mean
#
# FIX: Dropout from 0.1 → 0.15 in fusion layer for better regularization.
# ==============================================================================

IMU_GNSS_INPUT_DIM  = 42
IMU_GNSS_OUTPUT_DIM = 3


class IMUFusionNet(nn.Module):
    """MLP 双分支 IMU/GNSS 融合网络 v5"""

    def __init__(self,
                 imean: torch.Tensor = torch.zeros(IMU_GNSS_INPUT_DIM),
                 istd:  torch.Tensor = torch.ones(IMU_GNSS_INPUT_DIM)):
        super().__init__()
        if not isinstance(imean, torch.Tensor): imean = torch.tensor(imean, dtype=torch.float32)
        if not isinstance(istd,  torch.Tensor): istd  = torch.tensor(istd,  dtype=torch.float32)
        istd = torch.where(istd < 1e-6, torch.ones_like(istd), istd)
        self.register_buffer('imean', imean.float())
        self.register_buffer('istd',  istd.float())

        # IMU 分支: [0:12]
        self.imu_branch = nn.Sequential(
            nn.Linear(12, 64),  nn.LayerNorm(64),  nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(64, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
        )
        # 卫星残差分支: [12:42]
        self.res_branch = nn.Sequential(
            nn.Linear(30, 64), nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(64, 32), nn.ReLU(),
        )
        # 融合
        # FIX: Dropout 0.1 → 0.15
        self.fusion = nn.Sequential(
            nn.Linear(64 + 32, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, IMU_GNSS_OUTPUT_DIM)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x        = (x - self.imean) / self.istd
        imu_feat = self.imu_branch(x[:, :12])
        res_feat = self.res_branch(x[:, 12:])
        return self.fusion(torch.cat([imu_feat, res_feat], dim=1))


class IMUFusionNetSmall(nn.Module):
    """Smaller IMU/GNSS fusion net for small trajectory datasets."""

    def __init__(self,
                 imean: torch.Tensor = torch.zeros(IMU_GNSS_INPUT_DIM),
                 istd:  torch.Tensor = torch.ones(IMU_GNSS_INPUT_DIM),
                 dropout: float = 0.30):
        super().__init__()
        if not isinstance(imean, torch.Tensor): imean = torch.tensor(imean, dtype=torch.float32)
        if not isinstance(istd,  torch.Tensor): istd  = torch.tensor(istd,  dtype=torch.float32)
        istd = torch.where(istd < 1e-6, torch.ones_like(istd), istd)
        self.register_buffer('imean', imean.float())
        self.register_buffer('istd',  istd.float())

        self.imu_branch = nn.Sequential(
            nn.Linear(12, 32), nn.LayerNorm(32), nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 32), nn.ReLU(),
        )
        self.res_branch = nn.Sequential(
            nn.Linear(30, 32), nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 16), nn.ReLU(),
        )
        self.fusion = nn.Sequential(
            nn.Linear(48, 64), nn.LayerNorm(64), nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, IMU_GNSS_OUTPUT_DIM),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = (x - self.imean) / self.istd
        imu_feat = self.imu_branch(x[:, :12])
        res_feat = self.res_branch(x[:, 12:])
        return self.fusion(torch.cat([imu_feat, res_feat], dim=1))


class IMUFusionNetLSTM(nn.Module):
    """LSTM 序列 IMU/GNSS 融合网络"""

    def __init__(self,
                 imean:       torch.Tensor = torch.zeros(IMU_GNSS_INPUT_DIM),
                 istd:        torch.Tensor = torch.ones(IMU_GNSS_INPUT_DIM),
                 hidden_size: int = 128,
                 num_layers:  int = 2):
        super().__init__()
        if not isinstance(imean, torch.Tensor): imean = torch.tensor(imean, dtype=torch.float32)
        if not isinstance(istd,  torch.Tensor): istd  = torch.tensor(istd,  dtype=torch.float32)
        istd = torch.where(istd < 1e-6, torch.ones_like(istd), istd)
        self.register_buffer('imean', imean.float())
        self.register_buffer('istd',  istd.float())
        self.hidden_size = hidden_size
        self.num_layers  = num_layers
        self.feat = nn.Sequential(
            nn.Linear(IMU_GNSS_INPUT_DIM, 64), nn.ReLU(),
            nn.Linear(64, 64), nn.ReLU())
        self.lstm = nn.LSTM(64, hidden_size, num_layers, batch_first=True,
                            dropout=0.1 if num_layers > 1 else 0.0)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 64), nn.ReLU(),
            nn.Linear(64, IMU_GNSS_OUTPUT_DIM))

    def forward(self, x: torch.Tensor, h=None):
        x = (x - self.imean) / self.istd
        B, T, D = x.shape
        feat = self.feat(x.reshape(B*T, D)).reshape(B, T, -1)
        out, (h_n, c_n) = self.lstm(feat, h)
        return self.head(out), (h_n, c_n)


# ==============================================================================
# PINNFusionNet  —  物理信息神经网络（PINN）IMU/GNSS 融合
#
# 输出：
#   ① pos_corr_norm (3维): 归一化位置修正量
#      实际修正 = pos_corr_norm * corr_std + corr_mean
#   ② vel_pred (3维): 预测速度 ENU (m/s)，受 Doppler 监督
#
# 物理约束损失（在 imu_pinn_train.py 中计算）:
#   L_data : Huber(pos_corr_norm, (gt - gnss - corr_mean) / corr_std)
#   L_vel  : MSE(vel_pred, vel_doppler)              ← 速度直接监督
#   L_kin  : Huber(Δcorr_norm, expected_norm)        ← 运动学一致性
#
# FIX: Dropout 0.1 → 0.15 for better regularization.
# ==============================================================================

PINN_INPUT_DIM  = 42
PINN_EXT_INPUT_DIM = 78
PINN_POS_DIM    = 3
PINN_VEL_DIM    = 3


class SatelliteAttentionBranch(nn.Module):
    """Permutation-aware satellite feature pooling for the top-k satellite block."""

    def __init__(self, sat_feature_dim=3, embed_dim=32, out_dim=32):
        super().__init__()
        self.sat_feature_dim = sat_feature_dim
        self.sat_embed = nn.Sequential(
            nn.Linear(sat_feature_dim, embed_dim),
            nn.ReLU(),
            nn.LayerNorm(embed_dim),
        )
        self.attn_q = nn.Linear(embed_dim, 1)
        self.out = nn.Sequential(
            nn.Linear(embed_dim, out_dim),
            nn.ReLU(),
        )

    def forward(self, x_sat: torch.Tensor):
        emb = self.sat_embed(x_sat)
        scores = torch.softmax(self.attn_q(emb), dim=1)
        pooled = (emb * scores).sum(dim=1)
        return self.out(pooled), scores.squeeze(-1)


class PINNFusionNet(nn.Module):
    """
    PINN IMU/GNSS 融合网络。
    共享骨干网络，双头输出：归一化位置修正 + 速度预测。
    """

    def __init__(self,
                 imean: torch.Tensor = torch.zeros(PINN_INPUT_DIM),
                 istd:  torch.Tensor = torch.ones(PINN_INPUT_DIM),
                 motion_dim: int = 12,
                 sat_count: int = 10,
                 sat_feature_dim: int = 3,
                 extra_dim: int = 0,
                 use_sat_attention: bool = False,
                 uncertainty: bool = False):
        super().__init__()
        if not isinstance(imean, torch.Tensor): imean = torch.tensor(imean, dtype=torch.float32)
        if not isinstance(istd,  torch.Tensor): istd  = torch.tensor(istd,  dtype=torch.float32)
        istd = torch.where(istd < 1e-6, torch.ones_like(istd), istd)
        self.register_buffer('imean', imean.float())
        self.register_buffer('istd',  istd.float())
        self.motion_dim = motion_dim
        self.sat_count = sat_count
        self.sat_feature_dim = sat_feature_dim
        self.sat_dim = sat_count * sat_feature_dim
        self.extra_dim = extra_dim
        self.sat_start = motion_dim
        self.sat_end = self.sat_start + self.sat_dim
        self.use_sat_attention = use_sat_attention
        self.uncertainty = uncertainty

        # ── 共享骨干 ──────────────────────────────────────────────────────────
        # IMU 分支: [0:12]
        self.imu_branch = nn.Sequential(
            nn.Linear(motion_dim + extra_dim, 64),  nn.LayerNorm(64),  nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(64, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
        )
        # 卫星残差分支: [12:42]
        if use_sat_attention:
            self.res_branch = SatelliteAttentionBranch(
                sat_feature_dim=sat_feature_dim, embed_dim=32, out_dim=32
            )
        else:
            self.res_branch = nn.Sequential(
                nn.Linear(self.sat_dim, 64), nn.ReLU(),
                nn.Dropout(0.15),
                nn.Linear(64, 32), nn.ReLU(),
            )
        # 融合层
        # FIX: Dropout 0.1 → 0.15
        self.fusion = nn.Sequential(
            nn.Linear(64 + 32, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(128, 64), nn.ReLU(),
        )

        # ── 双头输出 ──────────────────────────────────────────────────────────
        # 头1：归一化位置修正 (3维)
        self.pos_head = nn.Linear(64, PINN_POS_DIM)
        if uncertainty:
            self.pos_log_var_head = nn.Linear(64, PINN_POS_DIM)

        # 头2：速度预测 (3维) — 受 Doppler 直接监督
        # FIX: vel_head now receives gradient via L_vel = MSE(vel_pred, vel_doppler)
        self.vel_head = nn.Linear(64, PINN_VEL_DIM)

    def forward(self, x: torch.Tensor):
        """
        Args:
            x: (B, 42) 特征向量
        Returns:
            pos_corr_norm: (B, 3) 归一化位置修正量
            vel_pred:      (B, 3) 预测速度 ENU (m/s)
        """
        x = (x - self.imean) / self.istd
        motion_x = x[:, :self.motion_dim]
        sat_x = x[:, self.sat_start:self.sat_end]
        if self.extra_dim > 0:
            extra_x = x[:, self.sat_end:self.sat_end + self.extra_dim]
            motion_x = torch.cat([motion_x, extra_x], dim=1)

        imu_feat = self.imu_branch(motion_x)
        attn = None
        if self.use_sat_attention:
            sat_x = sat_x.reshape(x.shape[0], self.sat_count, self.sat_feature_dim)
            res_feat, attn = self.res_branch(sat_x)
        else:
            res_feat = self.res_branch(sat_x)
        shared   = self.fusion(torch.cat([imu_feat, res_feat], dim=1))

        pos_corr_norm = self.pos_head(shared)   # (B, 3) 归一化修正量
        vel_pred      = self.vel_head(shared)   # (B, 3) m/s

        if self.uncertainty:
            pos_log_var = self.pos_log_var_head(shared).clamp(-6.0, 3.0)
            return pos_corr_norm, vel_pred, pos_log_var, attn
        return pos_corr_norm, vel_pred
