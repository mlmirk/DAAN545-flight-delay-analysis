"""Refit K-Means and Ward after removing outlier flags.

The published clustering keeps every scored month. This module repeats that
fit after three removals and compares k, agreement, and the delay profiles.
Cluster ids are arbitrary, so profiles are matched back to the retained fit.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

from .clustering import (
    choose_k,
    fit_cluster_models,
    pca_summary,
    profile_clusters,
    run_clustering,
    scale_features,
)
from .clustering import _sweep_k
from .outliers import run_outlier_detection

KEYS = ["year", "month", "carrier", "airport"]
ROLE_ORDER = ("late_aircraft", "nas", "carrier", "cancellation", "weather")
SCENARIO_ORDER = ("retain", "drop_consensus", "drop_iqr_delay", "drop_any_method")
SCENARIO_LABELS = {
    "retain": "retain",
    "drop_consensus": "drop consensus",
    "drop_iqr_delay": "drop delay IQR",
    "drop_any_method": "drop any flag",
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


def _roles_from_profile(profile: pd.DataFrame) -> dict[int, str]:
    """Name clusters by the feature that sets them apart. One name each."""
    remaining = set(int(c) for c in profile["cluster"])
    roles: dict[int, str] = {}

    def take(metric: str, role: str) -> None:
        part = profile[profile["cluster"].isin(remaining)]
        cid = int(part.loc[part[metric].idxmax(), "cluster"])
        roles[cid] = role
        remaining.remove(cid)

    take("mean_pct_cancelled", "cancellation")
    take("mean_share_weather", "weather")
    take("mean_share_nas", "nas")
    take("mean_share_carrier", "carrier")
    roles[remaining.pop()] = "late_aircraft"
    return roles


def _match_to_base(base_prof: pd.DataFrame, new_prof: pd.DataFrame) -> dict[int, int]:
    """Map each new cluster id to the closest retained cluster id."""
    cols = [c for c in base_prof.columns if c.startswith("mean_")]
    base_ids = base_prof["cluster"].astype(int).to_numpy()
    new_ids = new_prof["cluster"].astype(int).to_numpy()
    base_means = base_prof[cols].to_numpy(dtype=float)
    new_means = new_prof[cols].to_numpy(dtype=float)
    # Delay rates are much larger than cause shares. Scale each column by the
    # spread of the retained profiles so a share difference can still match.
    center = base_means.mean(axis=0)
    spread = base_means.std(axis=0)
    spread[spread < 1e-9] = 1.0
    base_z = (base_means - center) / spread
    new_z = (new_means - center) / spread
    cost = np.linalg.norm(base_z[:, None, :] - new_z[None, :, :], axis=2)
    base_idx, new_idx = linear_sum_assignment(cost)
    return {int(new_ids[j]): int(base_ids[i]) for i, j in zip(base_idx, new_idx)}


def _fit_subset(frame: pd.DataFrame, features: list[str]) -> dict:
    scaled, _scaler = scale_features(frame, features)
    pca = pca_summary(scaled)
    space = pca["coords"] if pca["cluster_in_pca_space"] else scaled
    sweep = _sweep_k(space)
    k = choose_k(sweep)
    models = fit_cluster_models(space, k)
    fitted = frame.copy()
    fitted["kmeans_cluster"] = models["kmeans_labels"]
    fitted["ward_cluster"] = models["ward_labels"]
    profiles = pd.concat(
        [
            profile_clusters(fitted, "kmeans_cluster", features),
            profile_clusters(fitted, "ward_cluster", features),
        ],
        ignore_index=True,
    )
    return {
        "frame": fitted,
        "sweep": sweep,
        "k": k,
        "profiles": profiles,
        "pca_two": pca["variance_first_two"],
        "kmeans_silhouette": models["kmeans_silhouette"],
        "ward_silhouette": models["ward_silhouette"],
        "adjusted_rand": models["adjusted_rand"],
    }


def _role_table(profile: pd.DataFrame, roles: dict[int, str], scenario: str) -> pd.DataFrame:
    out = profile.copy()
    out.insert(0, "scenario", scenario)
    out.insert(2, "role", out["cluster"].map(roles))
    return out


def _stability(
    kept: pd.DataFrame,
    base_roles: dict[int, str],
    new_to_base: dict[int, int],
    label_col: str,
    new_col: str,
) -> pd.DataFrame:
    base_role = kept[label_col].map(base_roles)
    new_role = kept[new_col].map(new_to_base).map(base_roles)
    rows = []
    same = base_role.eq(new_role)
    rows.append(
        {
            "role": "all",
            "n_kept": int(len(kept)),
            "n_same_role": int(same.sum()),
            "same_role_pct": round(100 * float(same.mean()), 1),
        }
    )
    for role in ROLE_ORDER:
        part = base_role.eq(role)
        n = int(part.sum())
        n_same = int((part & same).sum())
        rows.append(
            {
                "role": role,
                "n_kept": n,
                "n_same_role": n_same,
                "same_role_pct": round(100 * n_same / n, 1) if n else np.nan,
            }
        )
    return pd.DataFrame(rows)


def run_outlier_impact(df: pd.DataFrame) -> dict:
    """
    Cluster with outliers retained, then again after each removal rule.

    Removals happen after the flight-count filter. The 10th-percentile cutoff
    is not recomputed. Each refit standardizes the rows it keeps and chooses
    k from the K-Means silhouette, same rule as the published clustering.
    """
    retained = run_clustering(df)
    outliers = run_outlier_detection(df)
    features = list(retained["features"])
    flags = outliers["frame"][
        KEYS
        + [
            "flag_iqr_delay",
            "flag_consensus",
            "n_methods",
            "outlier_pattern",
        ]
    ]
    base = retained["frame"].merge(flags, on=KEYS, how="left", validate="1:1")
    if base["flag_consensus"].isna().any():
        raise RuntimeError("Outlier flags did not match the clustered months")

    base_profiles = {
        "kmeans_cluster": retained["profiles"]
        .loc[retained["profiles"]["method"] == "kmeans_cluster"]
        .copy(),
        "ward_cluster": retained["profiles"]
        .loc[retained["profiles"]["method"] == "ward_cluster"]
        .copy(),
    }
    base_roles = {method: _roles_from_profile(prof) for method, prof in base_profiles.items()}

    fits = {"retain": None}
    for scenario in SCENARIO_ORDER:
        if scenario == "retain":
            continue
        kept = base.loc[_keep_mask(base, scenario)].copy()
        fits[scenario] = _fit_subset(kept, features)

    summary_rows = []
    profile_parts = []
    stability_parts = []
    sweeps = []
    for scenario in SCENARIO_ORDER:
        keep = _keep_mask(base, scenario)
        n_kept = int(keep.sum())
        n_removed = int((~keep).sum())
        if scenario == "retain":
            fit_profiles = retained["profiles"]
            k = int(retained["models"]["k"])
            sil_k = float(retained["models"]["kmeans_silhouette"])
            sil_w = float(retained["models"]["ward_silhouette"])
            ari_methods = float(retained["models"]["adjusted_rand"])
            pca_two = float(retained["pca"]["variance_first_two"])
            sweep = retained["sweep"].copy()
            ari_k = 1.0
            ari_w = 1.0
            role_maps = base_roles
            for method, prof in base_profiles.items():
                named = _role_table(prof, role_maps[method], scenario)
                profile_parts.append(named)
                stability_parts.append(
                    _stability(
                        base,
                        base_roles[method],
                        {cid: cid for cid in base_roles[method]},
                        method,
                        method,
                    ).assign(scenario=scenario, method=method.replace("_cluster", ""))
                )
        else:
            fit = fits[scenario]
            fit_profiles = fit["profiles"]
            k = int(fit["k"])
            sil_k = float(fit["kmeans_silhouette"])
            sil_w = float(fit["ward_silhouette"])
            ari_methods = float(fit["adjusted_rand"])
            pca_two = float(fit["pca_two"])
            sweep = fit["sweep"].copy()
            joined = fit["frame"][KEYS + ["kmeans_cluster", "ward_cluster"]].merge(
                base[KEYS + ["kmeans_cluster", "ward_cluster"]],
                on=KEYS,
                suffixes=("_new", "_base"),
            )
            ari_k = float(
                adjusted_rand_score(joined["kmeans_cluster_base"], joined["kmeans_cluster_new"])
            )
            ari_w = float(
                adjusted_rand_score(joined["ward_cluster_base"], joined["ward_cluster_new"])
            )
            for method in ("kmeans_cluster", "ward_cluster"):
                prof = fit_profiles.loc[fit_profiles["method"] == method].copy()
                mapping = _match_to_base(base_profiles[method], prof)
                # Role of a new cluster is the role of the retained cluster it matches.
                roles = {
                    new_id: base_roles[method][base_id] for new_id, base_id in mapping.items()
                }
                profile_parts.append(_role_table(prof, roles, scenario))
                kept_labels = joined.rename(
                    columns={
                        f"{method}_base": method,
                        f"{method}_new": f"{method}_new",
                    }
                )
                stability_parts.append(
                    _stability(
                        kept_labels,
                        base_roles[method],
                        mapping,
                        method,
                        f"{method}_new",
                    ).assign(scenario=scenario, method=method.replace("_cluster", ""))
                )
        sweep = sweep.copy()
        sweep.insert(0, "scenario", scenario)
        sweeps.append(sweep)

        summary_rows.append(
            {
                "scenario": scenario,
                "n_rows": n_kept,
                "n_removed": n_removed,
                "removed_pct": round(100 * n_removed / len(base), 2),
                "chosen_k": k,
                "pca_variance_first_two": round(pca_two, 4),
                "kmeans_silhouette": round(sil_k, 3),
                "ward_silhouette": round(sil_w, 3),
                "kmeans_ward_ari": round(ari_methods, 3),
                "ari_vs_retained_kmeans": round(ari_k, 3),
                "ari_vs_retained_ward": round(ari_w, 3),
            }
        )

    profiles = pd.concat(profile_parts, ignore_index=True)
    stability = pd.concat(stability_parts, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    highlight_rows = []
    for scenario in SCENARIO_ORDER:
        for method, role, column, label in (
            ("kmeans", "cancellation", "mean_pct_cancelled", "kmeans_cancel_pct"),
            ("kmeans", "weather", "mean_share_weather", "kmeans_weather_share"),
            ("ward", "cancellation", "mean_pct_cancelled", "ward_cancel_pct"),
            ("ward", "weather", "mean_share_weather", "ward_weather_share"),
        ):
            part = profiles[
                (profiles["scenario"] == scenario)
                & (profiles["method"] == f"{method}_cluster")
                & (profiles["role"] == role)
            ]
            highlight_rows.append((scenario, label, float(part[column].iloc[0])))
    highlights = pd.DataFrame(highlight_rows, columns=["scenario", "metric", "value"])
    wide = highlights.pivot(index="scenario", columns="metric", values="value")
    summary = summary.merge(wide.round(3), on="scenario", how="left")

    where = (
        base.groupby(["kmeans_cluster", "outlier_pattern"], as_index=False)
        .size()
        .rename(columns={"size": "n_rows"})
    )
    where["role"] = where["kmeans_cluster"].map(base_roles["kmeans_cluster"])

    return {
        "summary": summary,
        "profiles": profiles,
        "stability": stability,
        "sweeps": pd.concat(sweeps, ignore_index=True),
        "pattern_by_cluster": where,
        "base_roles": {method: roles for method, roles in base_roles.items()},
        "meta": {
            "n_rows": int(len(base)),
            "features": features,
            "rules": {
                "retain": "Keep every month that entered clustering.",
                "drop_consensus": "Drop months flagged by at least two outlier methods.",
                "drop_iqr_delay": "Drop months outside the Tukey fence on pct_delayed only.",
                "drop_any_method": "Drop months flagged by IQR, k-NN, or the isolation forest.",
            },
        },
    }


def save_outlier_impact_figures(result: dict, fig_dir: Path) -> list[Path]:
    """Silhouette curves and the cancel / weather profiles under each removal."""
    fig_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    written: list[Path] = []

    sweeps = result["sweeps"]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for scenario in SCENARIO_ORDER:
        part = sweeps[sweeps["scenario"] == scenario]
        ax.plot(
            part["k"],
            part["kmeans_silhouette"],
            marker="o",
            label=SCENARIO_LABELS[scenario],
        )
    chosen = int(result["summary"]["chosen_k"].mode().iloc[0])
    if result["summary"]["chosen_k"].nunique() == 1:
        ax.axvline(chosen, color="0.4", ls="--", lw=1, label=f"chosen k={chosen}")
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("K-Means silhouette")
    ax.set_title("Silhouette after removing outliers")
    ax.legend(fontsize=8)
    path = fig_dir / "21_outlier_removal_silhouette.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    focus = result["profiles"]
    focus = focus[
        focus["method"].eq("kmeans_cluster")
        & focus["scenario"].isin(["retain", "drop_consensus", "drop_any_method"])
    ].copy()
    focus["scenario"] = focus["scenario"].map(SCENARIO_LABELS)
    focus["role"] = pd.Categorical(focus["role"], categories=ROLE_ORDER, ordered=True)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    sns.barplot(
        data=focus,
        x="role",
        y="mean_pct_cancelled",
        hue="scenario",
        ax=axes[0],
    )
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Mean percent cancelled")
    axes[0].set_title("Cancellation cluster stays or softens")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].legend(fontsize=8, title="")
    sns.barplot(
        data=focus,
        x="role",
        y="mean_share_weather",
        hue="scenario",
        ax=axes[1],
    )
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Mean weather share of delay minutes")
    axes[1].set_title("Weather cluster stays or softens")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].legend(fontsize=8, title="")
    path = fig_dir / "22_outlier_removal_profiles.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)
    return written
