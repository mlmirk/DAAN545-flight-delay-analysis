"""Refit PCA and t-SNE after the same outlier removals used for clustering.

The published reduction keeps every scored month. Component signs are arbitrary,
so each refit is flipped to point the same way as the retained components
before loadings are compared.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, trustworthiness

from .clustering import RANDOM_STATE, prepare_cluster_frame, scale_features
from .dimred import PCA_KEEP_VARIANCE, TSNE_MAX_ITER, TSNE_PERPLEXITY, _pcs_for_variance
from .outliers import PATTERN_COLORS, PATTERN_LABELS, PATTERN_ORDER, run_outlier_detection

KEYS = ["year", "month", "carrier", "airport"]
SCENARIO_ORDER = ("retain", "drop_consensus", "drop_iqr_delay", "drop_any_method")
SCENARIO_LABELS = {
    "retain": "retain",
    "drop_consensus": "drop consensus",
    "drop_iqr_delay": "drop delay IQR",
    "drop_any_method": "drop any flag",
}
COMPARE_SCENARIOS = ("retain", "drop_consensus", "drop_any_method")
FEATURE_LABELS = {
    "pct_delayed": "delayed",
    "pct_cancelled": "cancelled",
    "share_carrier": "carrier",
    "share_weather": "weather",
    "share_nas": "NAS",
    "share_late_aircraft": "late aircraft",
}


def _keep_mask(frame: pd.DataFrame, scenario: str) -> pd.Series:
    if scenario == "retain":
        return pd.Series(True, index=frame.index)
    if scenario == "drop_consensus":
        return ~frame["flag_consensus"]
    if scenario == "drop_iqr_delay":
        return ~frame["flag_iqr_delay"]
    if scenario == "drop_any_method":
        return frame["n_methods"].eq(0)
    raise KeyError(scenario)


def _fit_reduction(scaled: np.ndarray, features: list[str]) -> dict:
    pca = PCA(random_state=RANDOM_STATE)
    scores = pca.fit_transform(scaled)
    ratios = pca.explained_variance_ratio_
    n_keep = _pcs_for_variance(ratios, PCA_KEEP_VARIANCE)
    loadings = pd.DataFrame(
        pca.components_.T,
        index=features,
        columns=[f"PC{i + 1}" for i in range(len(features))],
    )
    kept = np.zeros_like(scores)
    kept[:, :n_keep] = scores[:, :n_keep]
    recon = pca.inverse_transform(kept)
    tsne = TSNE(
        n_components=2,
        perplexity=TSNE_PERPLEXITY,
        max_iter=TSNE_MAX_ITER,
        init="pca",
        learning_rate="auto",
        random_state=RANDOM_STATE,
    )
    tsne_coords = tsne.fit_transform(scaled)
    return {
        "ratios": ratios,
        "cumulative": np.cumsum(ratios),
        "n_keep": n_keep,
        "loadings": loadings,
        "scores": scores,
        "recon_mse_kept": float(np.mean((scaled - recon) ** 2)),
        "trust_pca2": float(trustworthiness(scaled, scores[:, :2], n_neighbors=5)),
        "trust_tsne": float(trustworthiness(scaled, tsne_coords, n_neighbors=5)),
        "tsne": tsne_coords,
    }


def _align_loadings(base: pd.DataFrame, new: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flip and order new components so each one matches a retained component."""
    aligned = pd.DataFrame(index=new.index, columns=base.columns, dtype=float)
    rows = []
    used: set[int] = set()
    for i, col in enumerate(base.columns):
        reference = base.iloc[:, i].to_numpy(dtype=float)
        best_j = 0
        best_abs = -1.0
        best_sign = 1.0
        for j in range(new.shape[1]):
            if j in used:
                continue
            candidate = new.iloc[:, j].to_numpy(dtype=float)
            cosine = float(
                np.dot(reference, candidate)
                / (np.linalg.norm(reference) * np.linalg.norm(candidate))
            )
            if abs(cosine) > best_abs:
                best_abs = abs(cosine)
                best_j = j
                best_sign = 1.0 if cosine >= 0 else -1.0
        used.add(best_j)
        aligned[col] = best_sign * new.iloc[:, best_j].to_numpy(dtype=float)
        rows.append(
            {
                "retained_pc": col,
                "matched_pc": new.columns[best_j],
                "abs_cosine": round(best_abs, 3),
                "sign_flipped": best_sign < 0,
            }
        )
    return aligned, pd.DataFrame(rows)


def run_dimred_outlier_impact(df: pd.DataFrame) -> dict:
    """
    Fit PCA and t-SNE with outliers retained, then again after each removal.

    Removals happen after the flight-count filter. Standardization is refit
    on the rows that remain. t-SNE uses the same perplexity and random seed
    as the published reduction.
    """
    frame, meta = prepare_cluster_frame(df)
    features = list(meta["features"])
    outliers = run_outlier_detection(df)
    flags = outliers["frame"][
        KEYS + ["flag_iqr_delay", "flag_consensus", "n_methods", "outlier_pattern"]
    ]
    base = frame.merge(flags, on=KEYS, how="left", validate="1:1")
    if base["flag_consensus"].isna().any():
        raise RuntimeError("Outlier flags did not match the reduced months")

    fits: dict[str, dict] = {}
    for scenario in SCENARIO_ORDER:
        kept = base.loc[_keep_mask(base, scenario)].copy()
        scaled, _scaler = scale_features(kept, features)
        fits[scenario] = _fit_reduction(scaled, features)
        fits[scenario]["n_rows"] = int(len(kept))

    base_loadings = fits["retain"]["loadings"]
    variance_rows = []
    summary_rows = []
    loading_parts = []
    match_parts = []
    for scenario in SCENARIO_ORDER:
        fit = fits[scenario]
        ratios = fit["ratios"]
        cumulative = fit["cumulative"]
        for i, (share, cum) in enumerate(zip(ratios, cumulative), start=1):
            variance_rows.append(
                {
                    "scenario": scenario,
                    "component": i,
                    "variance_share": round(float(share), 4),
                    "cumulative_share": round(float(cum), 4),
                }
            )
        if scenario == "retain":
            aligned = base_loadings.copy()
            matches = pd.DataFrame(
                {
                    "retained_pc": base_loadings.columns,
                    "matched_pc": base_loadings.columns,
                    "abs_cosine": 1.0,
                    "sign_flipped": False,
                }
            )
        else:
            aligned, matches = _align_loadings(base_loadings, fit["loadings"])
        matches.insert(0, "scenario", scenario)
        match_parts.append(matches)
        long = aligned.round(3).reset_index(names="feature")
        long["feature_label"] = long["feature"].map(FEATURE_LABELS).fillna(long["feature"])
        long.insert(0, "scenario", scenario)
        loading_parts.append(long)

        first_three = matches.iloc[:3]
        summary_rows.append(
            {
                "scenario": scenario,
                "n_rows": fit["n_rows"],
                "n_removed": int(len(base) - fit["n_rows"]),
                "removed_pct": round(100 * (len(base) - fit["n_rows"]) / len(base), 2),
                "pc1_share": round(float(ratios[0]), 4),
                "pc2_share": round(float(ratios[1]), 4),
                "pc1_pc2_share": round(float(ratios[:2].sum()), 4),
                "n_pcs_for_80pct": int(fit["n_keep"]),
                "variance_in_kept_pcs": round(float(ratios[: fit["n_keep"]].sum()), 4),
                "trustworthiness_pca2": round(fit["trust_pca2"], 3),
                "trustworthiness_tsne": round(fit["trust_tsne"], 3),
                "reconstruction_mse_kept_pcs": round(fit["recon_mse_kept"], 4),
                "cosine_pc1": float(first_three.iloc[0]["abs_cosine"]),
                "cosine_pc2": float(first_three.iloc[1]["abs_cosine"]),
                "cosine_pc3": float(first_three.iloc[2]["abs_cosine"]),
                "pc2_sign_flipped": bool(first_three.iloc[1]["sign_flipped"]),
                "pc3_sign_flipped": bool(first_three.iloc[2]["sign_flipped"]),
            }
        )

    retained_scores = fits["retain"]["scores"]
    leverage = base[KEYS + ["outlier_pattern"]].copy()
    leverage["pc1"] = retained_scores[:, 0]
    leverage["pc2"] = retained_scores[:, 1]
    leverage["pc3"] = retained_scores[:, 2]
    leverage["tsne_1"] = fits["retain"]["tsne"][:, 0]
    leverage["tsne_2"] = fits["retain"]["tsne"][:, 1]
    ss = (leverage[["pc1", "pc2", "pc3"]] ** 2).sum()
    leverage_rows = []
    for pattern, part in leverage.groupby("outlier_pattern"):
        share = (part[["pc1", "pc2", "pc3"]] ** 2).sum() / ss
        leverage_rows.append(
            {
                "outlier_pattern": pattern,
                "n_rows": int(len(part)),
                "share_of_rows": round(len(part) / len(leverage), 4),
                "pc1_ss_share": round(float(share["pc1"]), 3),
                "pc2_ss_share": round(float(share["pc2"]), 3),
                "pc3_ss_share": round(float(share["pc3"]), 3),
                "mean_pc1": round(float(part["pc1"].mean()), 2),
                "mean_pc2": round(float(part["pc2"].mean()), 2),
                "mean_pc3": round(float(part["pc3"].mean()), 2),
            }
        )

    return {
        "summary": pd.DataFrame(summary_rows),
        "variance": pd.DataFrame(variance_rows),
        "loadings_aligned": pd.concat(loading_parts, ignore_index=True),
        "loading_match": pd.concat(match_parts, ignore_index=True),
        "leverage": pd.DataFrame(leverage_rows),
        "retained_scores": leverage,
        "features": features,
        "meta": {
            "n_rows": int(len(base)),
            "tsne_perplexity": TSNE_PERPLEXITY,
            "rules": {
                "retain": "Keep every month that entered the reduction.",
                "drop_consensus": "Drop months flagged by at least two outlier methods.",
                "drop_iqr_delay": "Drop months outside the Tukey fence on pct_delayed only.",
                "drop_any_method": "Drop months flagged by IQR, k-NN, or the isolation forest.",
            },
        },
    }


def save_dimred_outlier_figures(result: dict, fig_dir: Path) -> list[Path]:
    """Variance curves, sign-aligned loadings, and where outliers sit in the retained map."""
    fig_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    written: list[Path] = []

    variance = result["variance"].copy()
    variance["scenario_label"] = variance["scenario"].map(SCENARIO_LABELS)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for scenario in SCENARIO_ORDER:
        part = variance[variance["scenario"] == scenario]
        ax.plot(
            part["component"],
            100 * part["variance_share"],
            marker="o",
            label=SCENARIO_LABELS[scenario],
        )
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Share of scaled variance (%)")
    ax.set_title("PCA variance after removing outliers")
    ax.set_xticks(sorted(variance["component"].unique()))
    ax.legend(fontsize=8)
    path = fig_dir / "30_pca_variance_by_outlier_removal.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    load = result["loadings_aligned"]
    load = load[load["scenario"].isin(COMPARE_SCENARIOS)].copy()
    load["scenario_label"] = load["scenario"].map(SCENARIO_LABELS)
    melted = load.melt(
        id_vars=["scenario_label", "feature_label"],
        value_vars=["PC1", "PC2", "PC3"],
        var_name="component",
        value_name="loading",
    )
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.4), sharey=True)
    for ax, component in zip(axes, ["PC1", "PC2", "PC3"]):
        sns.barplot(
            data=melted[melted["component"] == component],
            x="feature_label",
            y="loading",
            hue="scenario_label",
            ax=ax,
        )
        ax.axhline(0, color="0.5", lw=0.8)
        ax.set_title(component)
        ax.set_xlabel("")
        ax.set_ylabel("Loading" if component == "PC1" else "")
        ax.tick_params(axis="x", rotation=30)
        if ax is not axes[-1]:
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
        else:
            ax.legend(fontsize=8, title="")
    fig.suptitle("Sign-aligned loadings (same direction as the retained fit)")
    path = fig_dir / "31_pca_loadings_by_outlier_removal.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    scores = result["retained_scores"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    for ax, x, y, title in (
        (axes[0], "pc1", "pc3", "Retained PCA: PC1 vs PC3"),
        (axes[1], "tsne_1", "tsne_2", "Retained t-SNE"),
    ):
        for pattern in PATTERN_ORDER:
            part = scores[scores["outlier_pattern"] == pattern]
            ax.scatter(
                part[x],
                part[y],
                s=8 if pattern == "inlier" else 18,
                c=PATTERN_COLORS[pattern],
                alpha=0.25 if pattern == "inlier" else 0.75,
                linewidths=0,
                label=f"{PATTERN_LABELS[pattern]} (n={len(part):,})",
                zorder=1 if pattern == "inlier" else 2,
            )
        ax.set_title(title)
        ax.set_xlabel(x.replace("_", " "))
        ax.set_ylabel(y.replace("_", " "))
    axes[1].legend(fontsize=8, loc="best")
    path = fig_dir / "32_outlier_position_pca_tsne.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)
    return written
