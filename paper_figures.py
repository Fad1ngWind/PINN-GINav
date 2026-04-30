import argparse
import csv
import json
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches as mpatches


C = {
    "gnss": "#2563EB",
    "nonpinn": "#F59E0B",
    "pinn": "#DC2626",
    "dark": "#111827",
}


def setup_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 180,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
    })


def load_csv(path):
    data = np.genfromtxt(path, delimiter=",", names=True)
    if data.shape == ():
        data = np.array([data], dtype=data.dtype)
    return data


def col(data, *names):
    for name in names:
        if name in data.dtype.names:
            return np.asarray(data[name], dtype=float)
    raise KeyError(f"Missing columns {names}; available={data.dtype.names}")


def rmse(x):
    x = np.asarray(x, dtype=float)
    return float(np.sqrt(np.mean(x * x)))


def cdf_values(x):
    x = np.sort(np.asarray(x, dtype=float))
    y = np.arange(1, len(x) + 1) / len(x)
    return x, y


def percent_improve(base, value):
    return (1.0 - float(value) / float(base)) * 100.0


def smooth(x, width=9):
    x = np.asarray(x, dtype=float)
    if len(x) < width:
        return x
    kernel = np.ones(width) / width
    return np.convolve(x, kernel, mode="same")


def stats(errors_np, errors_pinn):
    g2 = col(errors_np, "gnss_2d")
    g3 = col(errors_np, "gnss_3d")
    n2 = col(errors_np, "fusion_2d", "nonpinn_2d")
    n3 = col(errors_np, "fusion_3d", "nonpinn_3d")
    p2 = col(errors_pinn, "pinn_2d", "fusion_2d")
    p3 = col(errors_pinn, "pinn_3d", "fusion_3d")
    return {
        "gnss_2d_rmse": rmse(g2),
        "gnss_3d_rmse": rmse(g3),
        "nonpinn_2d_rmse": rmse(n2),
        "nonpinn_3d_rmse": rmse(n3),
        "pinn_2d_rmse": rmse(p2),
        "pinn_3d_rmse": rmse(p3),
        "pinn_2d_mean": float(np.mean(p2)),
        "pinn_3d_mean": float(np.mean(p3)),
        "pinn_2d_p95": float(np.percentile(p2, 95)),
        "pinn_3d_p95": float(np.percentile(p3, 95)),
        "pinn_vs_gnss_2d": (1.0 - rmse(p2) / rmse(g2)) * 100.0,
        "pinn_vs_gnss_3d": (1.0 - rmse(p3) / rmse(g3)) * 100.0,
        "pinn_vs_nonpinn_2d": (1.0 - rmse(p2) / rmse(n2)) * 100.0,
        "pinn_vs_nonpinn_3d": (1.0 - rmse(p3) / rmse(n3)) * 100.0,
    }


def redesign_matrix(errors, method_2d_name, method_3d_name):
    return np.column_stack([
        col(errors, "time_s", "epoch_idx"),
        col(errors, "gnss_2d"),
        col(errors, "gnss_3d"),
        col(errors, method_2d_name, "fusion_2d"),
        col(errors, method_3d_name, "fusion_3d"),
    ])


def fig4_summary_rmse(d_np, d_pinn, outdir):
    os.makedirs(outdir, exist_ok=True)
    gnss_2d = np.asarray(d_np[:, 1], dtype=float)
    gnss_3d = np.asarray(d_np[:, 2], dtype=float)
    nonpinn_2d = np.asarray(d_np[:, 3], dtype=float)
    nonpinn_3d = np.asarray(d_np[:, 4], dtype=float)
    pinn_2d = np.asarray(d_pinn[:, 3], dtype=float)
    pinn_3d = np.asarray(d_pinn[:, 4], dtype=float)

    methods = ["GNSS\nonly", "Non-\nPINN", "PINN-\nGINav"]
    method_colors = [C["gnss"], C["nonpinn"], C["pinn"]]
    rmse_2d = [rmse(gnss_2d), rmse(nonpinn_2d), rmse(pinn_2d)]
    rmse_3d = [rmse(gnss_3d), rmse(nonpinn_3d), rmse(pinn_3d)]

    fig = plt.figure(figsize=(12.8, 4.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.12, 1.0, 1.0], wspace=0.32)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_cdf2 = fig.add_subplot(gs[0, 1])
    ax_cdf3 = fig.add_subplot(gs[0, 2])

    x = np.arange(len(methods))
    width = 0.34
    bars_2d = ax_bar.bar(
        x - width / 2,
        rmse_2d,
        width,
        color=method_colors,
        alpha=0.36,
        edgecolor="white",
        linewidth=0.8,
        label="2D RMSE",
    )
    bars_3d = ax_bar.bar(
        x + width / 2,
        rmse_3d,
        width,
        color=method_colors,
        alpha=0.82,
        edgecolor="white",
        linewidth=0.8,
        label="3D RMSE",
    )
    for bar, value in zip(bars_2d, rmse_2d):
        ax_bar.text(bar.get_x() + bar.get_width() / 2, value + 0.28, f"{value:.2f}", ha="center", va="bottom", fontsize=8)
    for bar, value in zip(bars_3d, rmse_3d):
        ax_bar.text(bar.get_x() + bar.get_width() / 2, value + 0.45, f"{value:.2f}", ha="center", va="bottom", fontsize=8.5)

    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(methods)
    ax_bar.set_ylabel("RMSE (m)")
    ax_bar.set_title("(a) RMSE overview")
    ax_bar.set_ylim(0, max(rmse_3d) * 1.18)
    ax_bar.legend(
        handles=[
            mpatches.Patch(facecolor="#6B7280", alpha=0.36, edgecolor="white", label="2D RMSE"),
            mpatches.Patch(facecolor="#6B7280", alpha=0.82, edgecolor="white", label="3D RMSE"),
        ],
        framealpha=0.9,
        fontsize=8,
        loc="upper right",
    )

    for ax, values_g, values_n, values_p, dim_label, panel in [
        (ax_cdf2, gnss_2d, nonpinn_2d, pinn_2d, "2D", "b"),
        (ax_cdf3, gnss_3d, nonpinn_3d, pinn_3d, "3D", "c"),
    ]:
        for values, color, name in [
            (values_g, C["gnss"], "GNSS only"),
            (values_n, C["nonpinn"], "Non-PINN"),
            (values_p, C["pinn"], "PINN-GINav"),
        ]:
            sx, sy = cdf_values(values)
            ax.plot(
                sx,
                sy * 100.0,
                color=color,
                lw=1.8 if name == "PINN-GINav" else 1.3,
                ls="--" if name == "PINN-GINav" else "-",
                label=f"{name} P95={np.percentile(values, 95):.1f} m",
            )
        ax.axhline(95, color="gray", lw=0.7, ls=":")
        ax.set_xlabel(f"{dim_label} error (m)")
        ax.set_ylabel("CDF (%)")
        ax.set_ylim(0, 102)
        ax.set_title(f"({panel}) {dim_label} error CDF")
        ax.legend(framealpha=0.9, fontsize=7.5)

    path = os.path.join(outdir, "fig4_summary_rmse.pdf")
    fig.subplots_adjust(left=0.06, right=0.985, bottom=0.16, top=0.90, wspace=0.32)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig7_ablation(outdir, scores_3d, scores_2d):
    os.makedirs(outdir, exist_ok=True)
    labels = list(scores_3d.keys())
    values_3d = np.array(list(scores_3d.values()), dtype=float)
    values_2d = np.array([scores_2d[label] for label in labels], dtype=float)
    y = np.arange(len(labels))
    full_idx = labels.index("PINN-GINav (full)") if "PINN-GINav (full)" in labels else len(labels) - 1
    full_3d = values_3d[full_idx]
    gnss_3d = values_3d[labels.index("GNSS only")] if "GNSS only" in labels else values_3d.max()

    def method_color(label):
        if label == "GNSS only":
            return C["gnss"]
        if "Non-PINN" in label:
            return C["nonpinn"]
        return C["pinn"]

    colors = [method_color(label) for label in labels]

    fig, ax = plt.subplots(figsize=(10.2, 4.8))
    ax.barh(y, values_3d, height=0.52, color=colors, alpha=0.82, edgecolor="white", linewidth=0.8, label="3D RMSE")
    ax.barh(y, values_2d, height=0.24, color=colors, alpha=0.36, edgecolor="white", linewidth=0.8, label="2D RMSE")
    ax.axvline(full_3d, color=C["pinn"], lw=1.2, ls="--", alpha=0.9, label=f"PINN full 3D = {full_3d:.2f} m")

    x_text = max(values_3d) * 1.08
    for yi, label, v2, v3 in zip(y, labels, values_2d, values_3d):
        ax.text(v3 + 0.18, yi, f"{v3:.2f}", va="center", ha="left", fontsize=9, color=C["dark"])
        ax.text(v2 + 0.18, yi - 0.18, f"{v2:.2f}", va="center", ha="left", fontsize=8, color="#4B5563")
        if label != "GNSS only":
            ax.text(
                x_text,
                yi,
                f"{percent_improve(gnss_3d, v3):.1f}%",
                va="center",
                ha="right",
                fontsize=8.5,
                color=C["dark"],
            )

    ax.text(x_text, -0.72, "3D improvement\nvs GNSS", ha="right", va="top", fontsize=8, color="#4B5563")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("RMSE (m)")
    ax.set_title("Ablation summary with paired 2D/3D metrics")
    ax.set_xlim(0, max(values_3d) * 1.15)
    ax.legend(framealpha=0.9, fontsize=8, loc="lower right")
    path = os.path.join(outdir, "fig7_ablation.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_timeseries(errors_np, errors_pinn, outdir):
    t = col(errors_np, "time_s")
    if t[0] > 1e6:
        t = t - t[0]
    g3 = col(errors_np, "gnss_3d")
    n3 = col(errors_np, "fusion_3d", "nonpinn_3d")
    p3 = col(errors_pinn, "pinn_3d", "fusion_3d")

    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(t, smooth(g3), color=C["gnss"], lw=1.1, label=f"GNSS only (RMSE={rmse(g3):.2f} m)")
    ax.plot(t, smooth(n3), color=C["nonpinn"], lw=1.3, label=f"Non-PINN (RMSE={rmse(n3):.2f} m)")
    ax.plot(t, smooth(p3), color=C["pinn"], lw=1.7, ls="--", label=f"PINN-GINav (RMSE={rmse(p3):.2f} m)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("3D error (m)")
    ax.set_title("3D positioning error over time")
    ax.legend(framealpha=0.9)
    path = os.path.join(outdir, "fig1_timeseries_3d.pdf")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_cdf(errors_np, errors_pinn, outdir):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    series = [
        (col(errors_np, "gnss_2d"), col(errors_np, "fusion_2d", "nonpinn_2d"), col(errors_pinn, "pinn_2d", "fusion_2d"), "2D"),
        (col(errors_np, "gnss_3d"), col(errors_np, "fusion_3d", "nonpinn_3d"), col(errors_pinn, "pinn_3d", "fusion_3d"), "3D"),
    ]
    for ax, (g, n, p, label) in zip(axes, series):
        for arr, color, name in [
            (g, C["gnss"], "GNSS only"),
            (n, C["nonpinn"], "Non-PINN"),
            (p, C["pinn"], "PINN-GINav"),
        ]:
            x, y = cdf_values(arr)
            ax.plot(x, y * 100.0, color=color, lw=1.8 if name == "PINN-GINav" else 1.3,
                    ls="--" if name == "PINN-GINav" else "-",
                    label=f"{name} P95={np.percentile(arr, 95):.1f} m")
        ax.axhline(95, color="gray", lw=0.7, ls=":")
        ax.set_xlabel(f"{label} error (m)")
        ax.set_ylabel("CDF (%)")
        ax.set_title(f"{label} error CDF")
        ax.set_ylim(0, 102)
        ax.legend(framealpha=0.9, fontsize=8)
    path = os.path.join(outdir, "fig2_cdf.pdf")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_distribution(errors_np, errors_pinn, outdir):
    g3 = col(errors_np, "gnss_3d")
    n3 = col(errors_np, "fusion_3d", "nonpinn_3d")
    p3 = col(errors_pinn, "pinn_3d", "fusion_3d")
    data = [g3, n3, p3]
    labels = ["GNSS\nonly", "Non-\nPINN", "PINN-\nGINav"]
    colors = [C["gnss"], C["nonpinn"], C["pinn"]]

    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    vp = ax.violinplot(data, showextrema=False, showmedians=False)
    for body, color in zip(vp["bodies"], colors):
        body.set_facecolor(color)
        body.set_alpha(0.22)
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.35,
                    medianprops={"color": "white", "linewidth": 1.8})
    for box, color in zip(bp["boxes"], colors):
        box.set_facecolor(color)
        box.set_alpha(0.75)
    for idx, arr in enumerate(data, 1):
        ax.scatter(idx, rmse(arr), marker="D", s=46, color="white", edgecolor=colors[idx - 1], zorder=3)
        ax.text(idx, rmse(arr), f"RMSE {rmse(arr):.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("3D error (m)")
    ax.set_title("3D error distribution")
    path = os.path.join(outdir, "fig3_distribution_3d.pdf")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_summary(errors_np, errors_pinn, outdir):
    d_np = redesign_matrix(errors_np, "fusion_2d", "fusion_3d")
    d_pinn = redesign_matrix(errors_pinn, "pinn_2d", "pinn_3d")
    return fig4_summary_rmse(d_np, d_pinn, outdir)


def fig_alpha(alpha_csv, outdir):
    if not alpha_csv or not os.path.exists(alpha_csv):
        return None
    data = load_csv(alpha_csv)
    t = col(data, "epoch_idx")
    alpha = col(data, "alpha")
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.plot(t, smooth(alpha), color=C["pinn"], lw=1.4)
    ax.fill_between(t, smooth(alpha), 0.5, where=smooth(alpha) >= 0.5, color=C["pinn"], alpha=0.18)
    ax.fill_between(t, smooth(alpha), 0.5, where=smooth(alpha) < 0.5, color=C["gnss"], alpha=0.18)
    ax.axhline(0.5, color="gray", lw=0.8, ls="--")
    ax.set_ylim(0, 1)
    ax.set_xlabel("Epoch index")
    ax.set_ylabel("alpha")
    ax.set_title(f"Adaptive fusion weight alpha (mean={np.mean(alpha):.3f})")
    path = os.path.join(outdir, "fig5_alpha_weights.pdf")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_contrib(contrib_csv, outdir):
    if not contrib_csv or not os.path.exists(contrib_csv):
        return None
    data = load_csv(contrib_csv)
    t = col(data, "epoch_idx")
    prior = col(data, "prior_dist_m")
    residual = col(data, "residual_dist_m")
    total = col(data, "total_corr_m")
    fig, ax = plt.subplots(figsize=(10, 4.0))
    ax.stackplot(t, smooth(prior), smooth(residual), colors=[C["gnss"], C["pinn"]],
                 alpha=0.72, labels=["Physics prior", "Learned residual"])
    ax.plot(t, smooth(total), color=C["dark"], lw=1.5, ls="--", label="Total correction")
    ax.set_xlabel("Epoch index")
    ax.set_ylabel("Contribution (m)")
    ax.set_title(
        f"Physics prior vs learned residual "
        f"(mean prior={np.mean(prior):.2f} m, residual={np.mean(residual):.2f} m)"
    )
    ax.legend(framealpha=0.9)
    path = os.path.join(outdir, "fig6_contribution.pdf")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_ablation(
    errors_np,
    errors_pinn,
    ablation_no_vel,
    ablation_no_vel_2d,
    ablation_nonpinn_s,
    ablation_nonpinn_s_2d,
    ablation_no_kin,
    ablation_no_kin_2d,
    ablation_no_vel_label,
    ablation_no_kin_label,
    outdir,
):
    s = stats(errors_np, errors_pinn)
    if ablation_no_vel is not None and ablation_no_vel_2d is None:
        ablation_no_vel_2d = s["pinn_2d_rmse"]
    if ablation_nonpinn_s is not None and ablation_nonpinn_s_2d is None:
        ablation_nonpinn_s_2d = s["nonpinn_2d_rmse"]
    if ablation_no_kin is not None and ablation_no_kin_2d is None:
        ablation_no_kin_2d = s["pinn_2d_rmse"]
    scores_3d = {
        "GNSS only": s["gnss_3d_rmse"],
        "Non-PINN": s["nonpinn_3d_rmse"],
    }
    scores_2d = {
        "GNSS only": s["gnss_2d_rmse"],
        "Non-PINN": s["nonpinn_2d_rmse"],
    }
    if ablation_nonpinn_s is not None:
        scores_3d["Non-PINN + S"] = float(ablation_nonpinn_s)
        scores_2d["Non-PINN + S"] = float(ablation_nonpinn_s_2d)
    if ablation_no_kin is not None:
        scores_3d[str(ablation_no_kin_label)] = float(ablation_no_kin)
        scores_2d[str(ablation_no_kin_label)] = float(ablation_no_kin_2d)
    if ablation_no_vel is not None:
        scores_3d[str(ablation_no_vel_label)] = float(ablation_no_vel)
        scores_2d[str(ablation_no_vel_label)] = float(ablation_no_vel_2d)
    scores_3d["PINN-GINav (full)"] = s["pinn_3d_rmse"]
    scores_2d["PINN-GINav (full)"] = s["pinn_2d_rmse"]
    return fig7_ablation(outdir, scores_3d, scores_2d)


def fig_attribution(errors_np, errors_pinn, ablation_no_vel, ablation_nonpinn_s, ablation_no_kin, outdir, vel_contrib=None, kin_contrib=None):
    if ablation_nonpinn_s is None or ablation_no_kin is None:
        return None
    if vel_contrib is None and ablation_no_vel is None:
        return None
    s = stats(errors_np, errors_pinn)
    full = s["pinn_3d_rmse"]
    vel_value = float(vel_contrib) if vel_contrib is not None else float(ablation_no_vel) - full
    kin_value = float(kin_contrib) if kin_contrib is not None else float(ablation_no_kin) - full
    contributions = [
        ("Data-driven\nGNSS->Non-PINN", s["gnss_3d_rmse"] - s["nonpinn_3d_rmse"]),
        ("Non-PINN + S", s["nonpinn_3d_rmse"] - float(ablation_nonpinn_s)),
        ("$L_{vel}$", vel_value),
        ("$L_{kin}$", kin_value),
        ("PINN net\nvs Non-PINN", s["nonpinn_3d_rmse"] - full),
    ]
    labels = [name for name, _ in contributions]
    values = np.array([value for _, value in contributions], dtype=float)
    colors = ["#16A34A" if value >= 0 else "#DC2626" for value in values]

    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, alpha=0.82, edgecolor="white", linewidth=0.8)
    ax.axhline(0, color=C["dark"], lw=0.9)
    for bar, value in zip(bars, values):
        va = "bottom" if value >= 0 else "top"
        offset = 0.25 if value >= 0 else -0.25
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + offset,
            f"{value:+.2f} m",
            ha="center",
            va=va,
            fontsize=9,
            fontweight="bold",
            color="#111827",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("3D RMSE contribution (m)")
    ax.set_title("Attribution analysis: positive bars reduce RMSE; negative bars hurt")
    ax.text(
        0.99,
        0.96,
        f"Full PINN: {full:.2f} m\nGNSS: {s['gnss_3d_rmse']:.2f} m",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#D1D5DB", "alpha": 0.92},
    )
    path = os.path.join(outdir, "fig8_attribution.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_asymmetry(outdir, nonpinn_delta=0.938322, pinn_delta=-0.710000):
    methods = ["Non-PINN", "PINN-GINav"]
    deltas = np.array([float(nonpinn_delta), float(pinn_delta)], dtype=float)
    colors = [C["nonpinn"], C["pinn"]]

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    bars = ax.bar(methods, deltas, color=colors, alpha=0.82, width=0.46, edgecolor="white", linewidth=0.8)
    ax.axhline(0, color="#374151", lw=0.9)
    for bar, value, color in zip(bars, deltas, colors):
        ypos = value + 0.06 if value > 0 else value - 0.08
        va = "bottom" if value > 0 else "top"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            ypos,
            f"{value:+.2f} m",
            ha="center",
            va=va,
            fontsize=11,
            fontweight="bold",
            color=color,
        )
    ax.text(0, 0.52, "Degrades\n(restricts valid corrections)", ha="center", fontsize=8, color=C["nonpinn"], style="italic")
    ax.text(1, -0.43, "Improves\n(suppresses non-physical jumps)", ha="center", fontsize=8, color=C["pinn"], style="italic")
    ax.set_ylabel("SCORE change after adding $L_{reg}$ (m)")
    ax.set_title("$L_{reg}$ is architecture-specific:\nharmful for Non-PINN, beneficial for PINN-GINav", fontsize=10, pad=8)
    ax.set_ylim(min(-1.0, deltas.min() - 0.3), max(1.3, deltas.max() + 0.3))
    path = os.path.join(outdir, "fig9_asymmetry.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def parse_score_list(raw):
    if not raw:
        return None
    values = [item.strip() for item in str(raw).split(",") if item.strip()]
    if not values:
        return None
    return np.array([float(item) for item in values], dtype=float)


def load_paper_data(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ablation_seed_groups(path):
    if not path or not os.path.exists(path):
        return {}
    groups = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cfg = str(row.get("config", "")).strip()
            if not cfg:
                continue
            groups.setdefault(cfg, []).append(float(row["score_3d"]))
    return {key: np.array(values, dtype=float) for key, values in groups.items()}


def fig_seed_stability(outdir, full_scores=None, no_kin_scores=None, no_vel_scores=None):
    series = []
    if full_scores is not None and len(full_scores) > 0:
        series.append(("PINN full\n(w/ $L_{vel}$)", np.asarray(full_scores, dtype=float), "#FCA5A5"))
    if no_kin_scores is not None and len(no_kin_scores) > 0:
        series.append(("w/o $L_{kin}$", np.asarray(no_kin_scores, dtype=float), C["nonpinn"]))
    if no_vel_scores is not None and len(no_vel_scores) > 0:
        series.append(("Final\n(w/o $L_{vel}$)", np.asarray(no_vel_scores, dtype=float), C["pinn"]))
    if not series:
        return None

    labels = [item[0] for item in series]
    means = np.array([item[1].mean() for item in series], dtype=float)
    stds = np.array([item[1].std() for item in series], dtype=float)
    colors = [item[2] for item in series]
    ypos = np.arange(len(series))

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.barh(
        ypos,
        means,
        xerr=stds,
        color=colors,
        height=0.5,
        alpha=0.88,
        edgecolor="white",
        error_kw={"ecolor": "#374151", "capsize": 5, "lw": 1.4},
    )
    for y, mean, std in zip(ypos, means, stds):
        ax.text(mean + std + 0.08, y, f"{mean:.2f} +/- {std:.2f} m", va="center", fontsize=9, color=C["dark"])
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("3D RMSE (m)")
    ax.set_title("Training stability across random seeds")
    ax.text(
        0.99,
        0.02,
        "Error bars = std over 3 independent runs",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#4B5563",
    )
    path = os.path.join(outdir, "fig10_seed_stability.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_lvel_analysis(outdir, full_scores=None, no_vel_scores=None):
    if full_scores is None or no_vel_scores is None:
        return None
    full_scores = np.asarray(full_scores, dtype=float)
    no_vel_scores = np.asarray(no_vel_scores, dtype=float)
    if len(full_scores) == 0 or len(no_vel_scores) == 0 or len(full_scores) != len(no_vel_scores):
        return None

    seeds = [42, 123, 2024][: len(full_scores)]
    deltas = full_scores - no_vel_scores
    line_colors = [C["pinn"], "#F87171", "#FCA5A5"]
    bar_colors = [C["pinn"] if value > 0 else C["gnss"] for value in deltas]

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.2))

    ax = axes[0]
    for idx, (full_value, no_vel_value) in enumerate(zip(full_scores, no_vel_scores)):
        ax.plot([0, 1], [full_value, no_vel_value], "o-", color=line_colors[idx % len(line_colors)], lw=1.5, ms=7, label=f"seed={seeds[idx]}")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["PINN full\n(w/ $L_{vel}$)", "PINN\n(w/o $L_{vel}$)"])
    ax.set_ylabel("3D RMSE (m)")
    ax.set_title("(a) Per-seed comparison")
    ax.legend(fontsize=8)

    ax = axes[1]
    ax.bar([f"seed={seed}" for seed in seeds], deltas, color=bar_colors, width=0.5, edgecolor="white", linewidth=0.8)
    ax.axhline(0, color="#374151", lw=0.8)
    ax.axhline(deltas.mean(), color=C["dark"], lw=1.4, ls="--", label=f"mean={deltas.mean():.3f} m")
    ax.set_ylabel("RMSE increase when $L_{vel}$ added (m)\n(positive = $L_{vel}$ degrades)")
    ax.set_title("(b) $L_{vel}$ degrades all seeds")
    ax.legend(fontsize=8)

    fig.suptitle("Velocity supervision $L_{vel}$ is consistently detrimental", fontsize=10, fontweight="bold")
    path = os.path.join(outdir, "fig11_lvel_analysis.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _named_matrix(data, prefix):
    names = data.dtype.names or ()
    return np.column_stack([
        np.asarray(data[f"{prefix}_E"], dtype=float),
        np.asarray(data[f"{prefix}_N"], dtype=float),
        np.asarray(data[f"{prefix}_U"], dtype=float),
    ]) if all(f"{prefix}_{axis}" in names for axis in ("E", "N", "U")) else None


def _thin_indices(length, max_points=2500):
    if length <= max_points:
        return np.arange(length)
    return np.unique(np.linspace(0, length - 1, max_points).astype(int))


def _set_axes_equal_3d(ax, arrays):
    pts = np.vstack([arr for arr in arrays if arr is not None and len(arr) > 0])
    mins = pts.min(axis=0)
    maxs = pts.max(axis=0)
    centers = (mins + maxs) / 2.0
    radius = 0.5 * np.max(maxs - mins)
    if radius <= 0:
        radius = 1.0
    ax.set_xlim(centers[0] - radius, centers[0] + radius)
    ax.set_ylim(centers[1] - radius, centers[1] + radius)
    ax.set_zlim(centers[2] - radius, centers[2] + radius)


def _robust_lim(values, pad_frac=0.06, low=1.0, high=99.0, min_span=1.0):
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if len(finite) == 0:
        return -1.0, 1.0
    lo, hi = np.percentile(finite, [low, high])
    span = max(float(hi - lo), float(min_span))
    return float(lo - span * pad_frac), float(hi + span * pad_frac)


def _style_3d_axis(ax):
    ax.tick_params(labelsize=7.5)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor("#D1D5DB")
    ax.yaxis.pane.set_edgecolor("#D1D5DB")
    ax.zaxis.pane.set_edgecolor("#D1D5DB")
    ax.grid(True, linestyle="--", linewidth=0.45, alpha=0.55)


def _load_trajectory_data(traj_csv="", nonpinn_traj_csv="", pinn_traj_csv=""):
    if traj_csv and os.path.exists(traj_csv):
        d = load_csv(traj_csv)
        t = col(d, "time_s", "t", "epoch_idx")
        gt = _named_matrix(d, "gt")
        gnss = _named_matrix(d, "gnss")
        nonpinn = _named_matrix(d, "nonpinn")
        pinn = _named_matrix(d, "pinn")
        if all(item is not None for item in (gt, gnss, nonpinn, pinn)):
            return t, gt, gnss, nonpinn, pinn

    if not (nonpinn_traj_csv and pinn_traj_csv):
        return None
    if not (os.path.exists(nonpinn_traj_csv) and os.path.exists(pinn_traj_csv)):
        return None

    dn = load_csv(nonpinn_traj_csv)
    dp = load_csv(pinn_traj_csv)
    n = min(len(dn), len(dp))
    if n == 0:
        return None
    t = col(dn, "time_s", "t", "epoch_idx")[:n]
    gt = _named_matrix(dn, "gt")
    gnss = _named_matrix(dn, "gnss")
    nonpinn = _named_matrix(dn, "nonpinn")
    pinn = _named_matrix(dp, "pinn")
    if all(item is not None for item in (gt, gnss, nonpinn, pinn)):
        return t, gt[:n], gnss[:n], nonpinn[:n], pinn[:n]
    return None


def fig3d_trajectory(outdir, traj_csv="", nonpinn_traj_csv="", pinn_traj_csv=""):
    loaded = _load_trajectory_data(traj_csv, nonpinn_traj_csv, pinn_traj_csv)
    if loaded is None:
        return None

    from matplotlib.lines import Line2D
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    import matplotlib.cm as cm

    t, gt, gnss, nonpinn, pinn = loaded
    idx = _thin_indices(len(t), max_points=3200)
    t = t[idx]
    gt = gt[idx].copy()
    gnss = gnss[idx].copy()
    nonpinn = nonpinn[idx].copy()
    pinn = pinn[idx].copy()

    t = t - t[0]
    origin = np.median(gt, axis=0)
    gt -= origin
    gnss -= origin
    nonpinn -= origin
    pinn -= origin

    x_all = np.concatenate([gt[:, 0], gnss[:, 0], nonpinn[:, 0], pinn[:, 0]])
    y_all = np.concatenate([gt[:, 1], gnss[:, 1], nonpinn[:, 1], pinn[:, 1]])
    z_all = np.concatenate([gt[:, 2], gnss[:, 2], nonpinn[:, 2], pinn[:, 2]])
    xlim = _robust_lim(x_all)
    ylim = _robust_lim(y_all)
    zlim = _robust_lim(z_all)

    fig = plt.figure(figsize=(14.0, 7.6))
    ax = fig.add_axes([0.03, 0.07, 0.55, 0.86], projection="3d")
    ax_top = fig.add_axes([0.64, 0.55, 0.33, 0.37])
    ax_side = fig.add_axes([0.64, 0.08, 0.33, 0.37])
    _style_3d_axis(ax)

    norm = plt.Normalize(float(t.min()), float(t.max()))
    points = pinn.reshape(-1, 1, 3)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    lc = Line3DCollection(segments, cmap=cm.Reds, norm=norm, linewidth=2.0, alpha=0.92)
    lc.set_array(t[:-1])

    ax.plot(*gnss.T, color=C["gnss"], lw=1.0, ls="--", label="GNSS only", alpha=0.48)
    ax.add_collection3d(lc)
    ax.plot(*nonpinn.T, color=C["nonpinn"], lw=1.3, ls="-.", label="Non-PINN", alpha=0.78)
    ax.plot(*gt.T, color=C["dark"], lw=2.0, label="Ground truth", alpha=0.95)

    for arr, color in [(gt, C["dark"]), (pinn, C["pinn"])]:
        ax.scatter(*arr[0], s=54, color=color, marker="o", edgecolors="white", linewidths=1.0)
        ax.scatter(*arr[-1], s=54, color=color, marker="s", edgecolors="white", linewidths=1.0)

    step = max(1, len(t) // 60)
    for i in range(0, len(t), step):
        ax.plot(
            [pinn[i, 0], gt[i, 0]],
            [pinn[i, 1], gt[i, 1]],
            [pinn[i, 2], gt[i, 2]],
            color=C["pinn"],
            alpha=0.14,
            lw=0.55,
        )

    cbar = fig.colorbar(cm.ScalarMappable(cmap=cm.Reds, norm=norm), ax=ax, shrink=0.52, pad=0.08)
    cbar.set_label("Time (s)", fontsize=8)
    cbar.ax.tick_params(labelsize=7.5)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_zlim(zlim)
    ax.set_xlabel("East (m)", fontsize=9, labelpad=5)
    ax.set_ylabel("North (m)", fontsize=9, labelpad=5)
    ax.set_zlabel("Up (m)", fontsize=9, labelpad=5)
    ax.set_title("(a) 3D trajectory comparison", fontsize=11, fontweight="bold", pad=8)
    ax.legend(
        handles=[
            Line2D([0], [0], color=C["dark"], lw=2.0, label="Ground truth"),
            Line2D([0], [0], color=C["gnss"], lw=1.1, ls="--", label="GNSS only"),
            Line2D([0], [0], color=C["nonpinn"], lw=1.1, ls="-.", label="Non-PINN"),
            Line2D([0], [0], color=C["pinn"], lw=2.0, label="PINN-GINav"),
        ],
        loc="upper left",
        framealpha=0.92,
        fontsize=8,
    )
    ax.view_init(elev=22, azim=-55)

    for arr, color, ls, lw, alpha in [
        (gnss, C["gnss"], "--", 1.1, 0.65),
        (pinn, C["pinn"], "-", 1.8, 0.90),
        (nonpinn, C["nonpinn"], "-.", 1.4, 0.85),
        (gt, C["dark"], "-", 2.0, 0.98),
    ]:
        ax_top.plot(arr[:, 0], arr[:, 1], color=color, lw=lw, ls=ls, alpha=alpha)
        ax_side.plot(arr[:, 1], arr[:, 2], color=color, lw=lw, ls=ls, alpha=alpha)

    ax_top.set_title("(b) Top view - East / North", fontsize=9, fontweight="bold")
    ax_top.set_xlim(xlim)
    ax_top.set_ylim(ylim)
    ax_top.set_xlabel("East (m)", fontsize=8)
    ax_top.set_ylabel("North (m)", fontsize=8)
    ax_top.tick_params(labelsize=7.5)
    ax_top.grid(True, ls="--", lw=0.4, alpha=0.42)
    ax_top.set_aspect("equal", adjustable="box")

    ax_side.set_title("(c) Side view - North / Up", fontsize=9, fontweight="bold")
    ax_side.set_xlim(ylim)
    ax_side.set_ylim(zlim)
    ax_side.set_xlabel("North (m)", fontsize=8)
    ax_side.set_ylabel("Up (m)", fontsize=8)
    ax_side.tick_params(labelsize=7.5)
    ax_side.grid(True, ls="--", lw=0.4, alpha=0.42)
    ax_side.axhline(0, color="#6B7280", lw=0.7, ls=":", alpha=0.65)

    visible = (
        (pinn[:, 1] >= ylim[0])
        & (pinn[:, 1] <= ylim[1])
        & (pinn[:, 2] >= zlim[0])
        & (pinn[:, 2] <= zlim[1])
    )
    up_err = pinn[:, 2] - gt[:, 2]
    visible_idx = np.where(visible)[0]
    if len(visible_idx) > 0:
        worst = int(visible_idx[np.argmax(np.abs(up_err[visible_idx]))])
        ax_side.annotate(
            f"Max shown Up err\n{up_err[worst]:.1f} m",
            xy=(pinn[worst, 1], pinn[worst, 2]),
            xytext=(
                pinn[worst, 1] + (ylim[1] - ylim[0]) * 0.10,
                pinn[worst, 2] + (zlim[1] - zlim[0]) * 0.13,
            ),
            fontsize=7.5,
            color=C["pinn"],
            arrowprops={"arrowstyle": "->", "color": C["pinn"], "lw": 0.8, "alpha": 0.85},
        )

    path = os.path.join(outdir, "fig12_3d_trajectory.pdf")
    fig.savefig(path)
    plt.close(fig)
    return path


def fig3d_error_surface(errors_np, errors_pinn, outdir):
    t = col(errors_np, "time_s", "epoch_idx")
    n_h = smooth(col(errors_np, "fusion_2d", "nonpinn_2d"), width=7)
    n_3 = smooth(col(errors_np, "fusion_3d", "nonpinn_3d"), width=7)
    p_h = smooth(col(errors_pinn, "pinn_2d", "fusion_2d"), width=7)
    p_3 = smooth(col(errors_pinn, "pinn_3d", "fusion_3d"), width=7)
    n = min(len(t), len(n_h), len(p_h))
    t = t[:n]
    n_h = n_h[:n]
    n_3 = n_3[:n]
    p_h = p_h[:n]
    p_3 = p_3[:n]
    n_u = np.sqrt(np.maximum(n_3 * n_3 - n_h * n_h, 0.0))
    p_u = np.sqrt(np.maximum(p_3 * p_3 - p_h * p_h, 0.0))

    fig = plt.figure(figsize=(10.4, 6.3))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot(t, n_h, n_u, color=C["nonpinn"], lw=1.1, alpha=0.62, label="Non-PINN")
    ax.plot(t, p_h, p_u, color=C["pinn"], lw=1.7, alpha=0.9, label="PINN-GINav")
    ax.plot(t, n_h, zs=0, zdir="z", color=C["nonpinn"], lw=0.8, alpha=0.22, ls="--")
    ax.plot(t, p_h, zs=0, zdir="z", color=C["pinn"], lw=0.8, alpha=0.25, ls="--")

    peak_idx = int(np.argmax(n_h))
    ax.scatter(t[peak_idx], n_h[peak_idx], n_u[peak_idx], s=70, color=C["nonpinn"], marker="^")
    ax.text(
        t[peak_idx],
        n_h[peak_idx] + 0.7,
        n_u[peak_idx] + 0.7,
        f"Non-PINN peak\n{n_h[peak_idx]:.1f} m",
        fontsize=8,
        color=C["nonpinn"],
    )

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Horizontal error (m)")
    ax.set_zlabel("Vertical error (m)")
    ax.set_title("3D spatio-temporal error curve", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, framealpha=0.9)
    ax.view_init(elev=21, azim=-50)
    path = os.path.join(outdir, "fig13_3d_error_surface.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _first_existing_col(data, *names):
    for name in names:
        if data.dtype.names and name in data.dtype.names:
            return np.asarray(data[name], dtype=float)
    return None


def fig3d_loss_landscape(loss_csv, outdir):
    if not loss_csv or not os.path.exists(loss_csv):
        return None
    lc = load_csv(loss_csv)
    epoch = _first_existing_col(lc, "epoch", "ep")
    l_data = _first_existing_col(lc, "data", "L_data", "loss_data")
    l_kin = _first_existing_col(lc, "kin", "L_kin", "loss_kin")
    val = _first_existing_col(lc, "val_dist_m", "val3d", "val_3d", "val")
    if any(item is None for item in (epoch, l_data, l_kin, val)):
        return None

    fig = plt.figure(figsize=(8.8, 6.5))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot(l_data, l_kin, val, color="#9CA3AF", lw=1.0, alpha=0.55)
    sc = ax.scatter(l_data, l_kin, val, c=epoch, cmap="plasma", s=13, alpha=0.78)
    best_idx = int(np.argmin(val))
    ax.scatter(l_data[0], l_kin[0], val[0], s=95, color="#6B7280", marker="o", edgecolors="white", label="Start")
    ax.scatter(l_data[best_idx], l_kin[best_idx], val[best_idx], s=120, color="#16A34A", marker="D", edgecolors="white", label="Best")
    ax.scatter(l_data[-1], l_kin[-1], val[-1], s=120, color=C["pinn"], marker="*", edgecolors="white", label="Final")
    cbar = fig.colorbar(sc, ax=ax, shrink=0.52, pad=0.08)
    cbar.set_label("Epoch")
    ax.set_xlabel("$L_{data}$")
    ax.set_ylabel("$L_{kin}$")
    ax.set_zlabel("Val 3D RMSE (m)")
    ax.set_title("Optimization trajectory in physics-loss space", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8)
    ax.view_init(elev=20, azim=-45)
    path = os.path.join(outdir, "fig14_3d_loss_landscape.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def fig3d_height_error_dist(outdir, up_before_path="", up_after_path=""):
    if not (up_before_path and up_after_path):
        return None
    if not (os.path.exists(up_before_path) and os.path.exists(up_after_path)):
        return None
    before = np.asarray(np.load(up_before_path), dtype=float).ravel()
    after = np.asarray(np.load(up_after_path), dtype=float).ravel()
    if len(before) == 0 or len(after) == 0:
        return None

    fig = plt.figure(figsize=(12.0, 5.5))
    for idx, (data, title, color) in enumerate([
        (before, "Before up-bias correction", C["gnss"]),
        (after, "After up-bias correction", C["pinn"]),
    ], start=1):
        ax = fig.add_subplot(1, 2, idx, projection="3d")
        seg_count = min(28, max(1, len(data) // 200))
        seg_size = max(1, len(data) // seg_count)
        bins = np.linspace(np.percentile(data, 1), np.percentile(data, 99), 30)
        for seg_idx in range(seg_count):
            seg = data[seg_idx * seg_size : (seg_idx + 1) * seg_size]
            counts, edges = np.histogram(seg, bins=bins)
            xs = (edges[:-1] + edges[1:]) / 2.0
            ax.bar(
                xs,
                counts,
                zs=seg_idx * seg_size,
                zdir="y",
                width=(bins[1] - bins[0]) * 0.85,
                color=color,
                alpha=0.34,
                edgecolor="none",
            )
        ax.set_xlabel("Up error (m)")
        ax.set_ylabel("Epoch index")
        ax.set_zlabel("Count")
        ax.set_title(f"{title}\nmean={np.mean(data):.2f} m, std={np.std(data):.2f} m", fontsize=9)
        ax.view_init(elev=24, azim=-50)

    path = os.path.join(outdir, "fig15_3d_height_error.pdf")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def fig3d_ablation_confidence(outdir, seed_groups, paper_data=None):
    if not seed_groups:
        return None
    configs = [
        ("PINN full\n(w/ $L_{vel}$)", "full_with_lvel", "#FCA5A5"),
        ("w/o $L_{kin}$", "wo_lkin", C["nonpinn"]),
        ("Final\n(w/o $L_{vel}$)", "wo_lvel", C["pinn"]),
    ]
    configs = [(label, key, color) for label, key, color in configs if key in seed_groups and len(seed_groups[key]) > 0]
    if not configs:
        return None

    fig = plt.figure(figsize=(9.4, 6.6))
    ax = fig.add_subplot(111, projection="3d")
    _style_3d_axis(ax)
    seed_labels = [42, 123, 2024]
    for ci, (label, key, color) in enumerate(configs):
        scores = np.asarray(seed_groups[key], dtype=float)
        mean = float(np.mean(scores))
        std = float(np.std(scores))
        for si, score in enumerate(scores):
            ax.scatter(ci, si, score, s=70, color=color, alpha=0.92, edgecolors="white", linewidths=1.0)
        ax.plot([ci] * len(scores), np.arange(len(scores)), scores, color=color, lw=1.0, ls="--", alpha=0.45)
        ax.scatter(ci, 1, mean, s=145, color=color, marker="D", edgecolors="white", linewidths=1.3)
        ax.plot([ci, ci], [1, 1], [mean - std, mean + std], color=color, lw=2.4, alpha=0.85)
        ax.text(ci, -0.56, mean - std - 0.12, label, ha="center", fontsize=8, color=color, fontweight="bold")

    gnss = 36.031403
    if paper_data is not None:
        gnss = float(paper_data.get("gnss_rmse_3d", gnss))
    ax.plot([-0.45, len(configs) - 0.55], [1, 1], [gnss, gnss], color=C["gnss"], lw=1.5, ls=":", alpha=0.7, label=f"GNSS only ({gnss:.2f} m)")
    ax.set_xticks(range(len(configs)))
    ax.set_xticklabels([])
    ax.set_yticks(range(min(3, max(len(seed_groups[key]) for _, key, _ in configs))))
    ax.set_yticklabels([f"seed={seed}" for seed in seed_labels[: len(ax.get_yticks())]], fontsize=8)
    ax.set_zlabel("3D RMSE (m)")
    ax.set_title("3D ablation confidence across random seeds", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8, loc="upper right", framealpha=0.9)
    ax.view_init(elev=20, azim=-40)
    path = os.path.join(outdir, "fig16_3d_ablation_confidence.pdf")
    fig.subplots_adjust(left=0.02, right=0.96, bottom=0.03, top=0.92)
    fig.savefig(path)
    plt.close(fig)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--errors_csv", required=True)
    parser.add_argument("--pinn_csv", required=True)
    parser.add_argument("--paper_data", default="")
    parser.add_argument("--ablation_csv", default="")
    parser.add_argument("--alpha_csv", default="")
    parser.add_argument("--contrib_csv", default="")
    parser.add_argument("--ablation_no_vel", type=float, default=None)
    parser.add_argument("--ablation_no_vel_2d", type=float, default=None)
    parser.add_argument("--ablation_no_vel_label", default="PINN  (w/o $L_{vel}$)")
    parser.add_argument("--ablation_nonpinn_s", type=float, default=None)
    parser.add_argument("--ablation_nonpinn_s_2d", type=float, default=None)
    parser.add_argument("--ablation_no_kin", type=float, default=None)
    parser.add_argument("--ablation_no_kin_2d", type=float, default=None)
    parser.add_argument("--ablation_no_kin_label", default="PINN  (w/o $L_{kin}$)")
    parser.add_argument("--s_delta_nonpinn", type=float, default=0.938322)
    parser.add_argument("--s_delta_pinn", type=float, default=-0.710000)
    parser.add_argument("--vel_contrib", type=float, default=None)
    parser.add_argument("--kin_contrib", type=float, default=None)
    parser.add_argument("--full_seed_scores", default="")
    parser.add_argument("--no_kin_seed_scores", default="")
    parser.add_argument("--no_vel_seed_scores", default="")
    parser.add_argument("--traj_csv", default="")
    parser.add_argument("--nonpinn_traj_csv", default="")
    parser.add_argument("--pinn_traj_csv", default="")
    parser.add_argument("--loss_csv", default="")
    parser.add_argument("--up_before", default="")
    parser.add_argument("--up_after", default="")
    parser.add_argument("--only_3d", action="store_true")
    parser.add_argument("--outdir", default="figures")
    args = parser.parse_args()

    setup_style()
    os.makedirs(args.outdir, exist_ok=True)
    errors_np = load_csv(args.errors_csv)
    errors_pinn = load_csv(args.pinn_csv)
    if not args.nonpinn_traj_csv:
        args.nonpinn_traj_csv = os.path.join(os.path.dirname(args.errors_csv), "trajectory_enu.csv")
    if not args.pinn_traj_csv:
        args.pinn_traj_csv = os.path.join(os.path.dirname(args.pinn_csv), "trajectory_enu.csv")
    paper_data = load_paper_data(args.paper_data)
    seed_groups = load_ablation_seed_groups(args.ablation_csv)

    if paper_data is not None:
        ablation = paper_data.get("ablation", {})
        if args.ablation_no_kin is None:
            args.ablation_no_kin = ablation.get("wo_lkin_mean")
        if args.ablation_no_kin_2d is None:
            args.ablation_no_kin_2d = ablation.get("wo_lkin_2d_mean")
        if args.ablation_nonpinn_s is None:
            args.ablation_nonpinn_s = ablation.get("nonpinn_plus_s")
        if args.ablation_nonpinn_s_2d is None:
            args.ablation_nonpinn_s_2d = ablation.get("nonpinn_plus_s_2d")
        if args.vel_contrib is None:
            args.vel_contrib = paper_data.get("lvel_contribution_mean")
        if args.kin_contrib is None:
            args.kin_contrib = paper_data.get("lkin_contribution_mean")
        args.s_delta_nonpinn = float(paper_data.get("lreg_nonpinn_delta", args.s_delta_nonpinn))
        args.s_delta_pinn = float(paper_data.get("lreg_pinn_delta", args.s_delta_pinn))

    if seed_groups:
        if not args.full_seed_scores and "full_with_lvel" in seed_groups:
            args.full_seed_scores = ",".join(f"{value:.6f}" for value in seed_groups["full_with_lvel"])
        if not args.no_kin_seed_scores and "wo_lkin" in seed_groups:
            args.no_kin_seed_scores = ",".join(f"{value:.6f}" for value in seed_groups["wo_lkin"])
        if not args.no_vel_seed_scores and "wo_lvel" in seed_groups:
            args.no_vel_seed_scores = ",".join(f"{value:.6f}" for value in seed_groups["wo_lvel"])

    if args.only_3d:
        generated = []
        for optional in [
            fig3d_trajectory(args.outdir, args.traj_csv, args.nonpinn_traj_csv, args.pinn_traj_csv),
            fig3d_error_surface(errors_np, errors_pinn, args.outdir),
            fig3d_loss_landscape(args.loss_csv, args.outdir),
            fig3d_height_error_dist(args.outdir, args.up_before, args.up_after),
            fig3d_ablation_confidence(args.outdir, seed_groups, paper_data),
        ]:
            if optional:
                generated.append(optional)
        s = stats(errors_np, errors_pinn)
        for path in generated:
            print(f"FIGURE: {path}")
        print(f"PINN_2D_RMSE: {s['pinn_2d_rmse']:.6f}m")
        print(f"PINN_3D_RMSE: {s['pinn_3d_rmse']:.6f}m")
        print(f"PINN_VS_GNSS_3D_IMPROVE: {s['pinn_vs_gnss_3d']:.3f}%")
        return

    generated = [
        fig_timeseries(errors_np, errors_pinn, args.outdir),
        fig_cdf(errors_np, errors_pinn, args.outdir),
        fig_distribution(errors_np, errors_pinn, args.outdir),
        fig_summary(errors_np, errors_pinn, args.outdir),
    ]
    for optional in [fig_alpha(args.alpha_csv, args.outdir), fig_contrib(args.contrib_csv, args.outdir)]:
        if optional:
            generated.append(optional)
    ablation_path = fig_ablation(
        errors_np,
        errors_pinn,
        args.ablation_no_vel,
        args.ablation_no_vel_2d,
        args.ablation_nonpinn_s,
        args.ablation_nonpinn_s_2d,
        args.ablation_no_kin,
        args.ablation_no_kin_2d,
        args.ablation_no_vel_label,
        args.ablation_no_kin_label,
        args.outdir,
    )
    if ablation_path:
        generated.append(ablation_path)
    generated.append(fig_asymmetry(args.outdir, args.s_delta_nonpinn, args.s_delta_pinn))
    fig10_path = fig_seed_stability(
        args.outdir,
        parse_score_list(args.full_seed_scores),
        parse_score_list(args.no_kin_seed_scores),
        parse_score_list(args.no_vel_seed_scores),
    )
    if fig10_path:
        generated.append(fig10_path)
    fig11_path = fig_lvel_analysis(
        args.outdir,
        parse_score_list(args.full_seed_scores),
        parse_score_list(args.no_vel_seed_scores),
    )
    if fig11_path:
        generated.append(fig11_path)
    for optional in [
        fig3d_trajectory(args.outdir, args.traj_csv, args.nonpinn_traj_csv, args.pinn_traj_csv),
        fig3d_error_surface(errors_np, errors_pinn, args.outdir),
        fig3d_loss_landscape(args.loss_csv, args.outdir),
        fig3d_height_error_dist(args.outdir, args.up_before, args.up_after),
        fig3d_ablation_confidence(args.outdir, seed_groups, paper_data),
    ]:
        if optional:
            generated.append(optional)

    s = stats(errors_np, errors_pinn)
    for path in generated:
        print(f"FIGURE: {path}")
    print(f"PINN_2D_RMSE: {s['pinn_2d_rmse']:.6f}m")
    print(f"PINN_3D_RMSE: {s['pinn_3d_rmse']:.6f}m")
    print(f"PINN_P95_2D: {s['pinn_2d_p95']:.6f}m")
    print(f"PINN_VS_GNSS_2D_IMPROVE: {s['pinn_vs_gnss_2d']:.3f}%")
    print(f"PINN_VS_GNSS_3D_IMPROVE: {s['pinn_vs_gnss_3d']:.3f}%")
    print(f"PINN_VS_NONPINN_2D_IMPROVE: {s['pinn_vs_nonpinn_2d']:.3f}%")
    print(f"PINN_VS_NONPINN_3D_IMPROVE: {s['pinn_vs_nonpinn_3d']:.3f}%")


if __name__ == "__main__":
    main()

