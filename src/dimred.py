"""PCA and t-SNE on the same scaled delay-profile features as clustering.

PCA is the linear baseline (variance, loadings, optional clustering space).
t-SNE is the nonlinear 2D view (local neighborhoods). We do not cluster in
t-SNE coordinates.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, trustworthiness
from sklearn.metrics import adjusted_rand_score, silhouette_score

from .clustering import (
    RANDOM_STATE,
    choose_k,
    pca_summary,
    prepare_cluster_frame,
    scale_features,
)

# Keep enough PCs to cover this share of scaled variance when we re-cluster.
PCA_KEEP_VARIANCE = 0.80
TSNE_PERPLEXITY = 30
TSNE_MAX_ITER = 1000


def _pcs_for_variance(ratios: np.ndarray, target: float) -> int:
    cumulative = np.cumsum(ratios)
    n = int(np.searchsorted(cumulative, target) + 1)
    return max(2, min(n, len(ratios)))


def run_dimred(df: pd.DataFrame) -> dict:
    """Fit PCA and t-SNE; compare K-Means in original vs PCA-reduced space."""
    frame, meta = prepare_cluster_frame(df)
    features = meta["features"]
    scaled, scaler = scale_features(frame, features)

    pca_full = PCA(random_state=RANDOM_STATE)
    pca_scores = pca_full.fit_transform(scaled)
    ratios = pca_full.explained_variance_ratio_
    two_d = pca_summary(scaled)
    n_keep = _pcs_for_variance(ratios, PCA_KEEP_VARIANCE)
    pca_reduced = pca_scores[:, :n_keep]

    loadings = pd.DataFrame(
        pca_full.components_.T,
        index=features,
        columns=[f"PC{i + 1}" for i in range(len(features))],
    )

    tsne = TSNE(
        n_components=2,
        perplexity=TSNE_PERPLEXITY,
        max_iter=TSNE_MAX_ITER,
        init="pca",
        learning_rate="auto",
        random_state=RANDOM_STATE,
    )
    tsne_coords = tsne.fit_transform(scaled)
    trust_tsne = float(trustworthiness(scaled, tsne_coords, n_neighbors=5))
    trust_pca2 = float(trustworthiness(scaled, pca_scores[:, :2], n_neighbors=5))

    sweep_orig = []
    sweep_pca = []
    for k in range(2, 9):
        km_o = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
        lab_o = km_o.fit_predict(scaled)
        km_p = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
        lab_p = km_p.fit_predict(pca_reduced)
        sweep_orig.append(
            {
                "k": k,
                "silhouette_original": float(silhouette_score(scaled, lab_o)),
            }
        )
        sweep_pca.append(
            {
                "k": k,
                "silhouette_pca_space": float(silhouette_score(pca_reduced, lab_p)),
                "silhouette_labels_in_original": float(silhouette_score(scaled, lab_p)),
                "ari_vs_original_kmeans": float(adjusted_rand_score(lab_o, lab_p)),
            }
        )
    orig_sweep = pd.DataFrame(sweep_orig)
    pca_sweep = pd.DataFrame(sweep_pca)
    k = choose_k(
        orig_sweep.rename(columns={"silhouette_original": "kmeans_silhouette"})
    )

    km_orig = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    labels_orig = km_orig.fit_predict(scaled)
    km_pca = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    labels_pca = km_pca.fit_predict(pca_reduced)

    frame = frame.copy()
    frame["kmeans_original"] = labels_orig
    frame["kmeans_pca"] = labels_pca
    frame["pc1"] = pca_scores[:, 0]
    frame["pc2"] = pca_scores[:, 1]
    frame["pc3"] = pca_scores[:, 2] if pca_scores.shape[1] > 2 else 0.0
    frame["tsne_1"] = tsne_coords[:, 0]
    frame["tsne_2"] = tsne_coords[:, 1]

    recon = pca_full.inverse_transform(pca_scores)
    recon_err = float(np.mean((scaled - recon) ** 2))
    recon_keep = pca_full.inverse_transform(
        np.hstack(
            [
                pca_reduced,
                np.zeros((len(scaled), pca_scores.shape[1] - n_keep)),
            ]
        )
    )
    recon_err_keep = float(np.mean((scaled - recon_keep) ** 2))

    return {
        "frame": frame,
        "meta": meta,
        "features": features,
        "scaled": scaled,
        "scaler_means": scaler.mean_.tolist(),
        "scaler_scales": scaler.scale_.tolist(),
        "pca_ratios": [round(float(r), 4) for r in ratios],
        "pca_cumulative": [round(float(x), 4) for x in np.cumsum(ratios)],
        "pca_variance_first_two": two_d["variance_first_two"],
        "pca_cluster_in_2d": two_d["cluster_in_pca_space"],
        "n_pcs_for_80pct": n_keep,
        "variance_kept_for_clustering": round(float(np.sum(ratios[:n_keep])), 4),
        "loadings": loadings.round(3),
        "trustworthiness_tsne": round(trust_tsne, 4),
        "trustworthiness_pca2": round(trust_pca2, 4),
        "tsne_perplexity": TSNE_PERPLEXITY,
        "k": k,
        "silhouette_original": float(silhouette_score(scaled, labels_orig)),
        "silhouette_pca_in_pca_space": float(silhouette_score(pca_reduced, labels_pca)),
        "silhouette_pca_labels_in_original": float(silhouette_score(scaled, labels_pca)),
        "ari_original_vs_pca_kmeans": float(adjusted_rand_score(labels_orig, labels_pca)),
        "orig_sweep": orig_sweep,
        "pca_k_sweep": pca_sweep,
        "reconstruction_mse_all_pcs": recon_err,
        "reconstruction_mse_kept_pcs": recon_err_keep,
    }


def save_dimred_figures(result: dict, fig_dir: Path) -> list[Path]:
    fig_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    written: list[Path] = []
    frame = result["frame"]
    ratios = np.array(result["pca_ratios"])
    cumulative = np.array(result["pca_cumulative"])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    xs = np.arange(1, len(ratios) + 1)
    ax.bar(xs, 100 * ratios, color="steelblue", label="This component")
    ax.plot(xs, 100 * cumulative, marker="o", color="crimson", label="Cumulative")
    ax.axhline(80, color="0.4", ls="--", lw=1, label="80% cutoff")
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Share of scaled variance (%)")
    ax.set_title("PCA: how much delay-profile variance each component holds")
    ax.set_xticks(xs)
    ax.legend()
    path = fig_dir / "23_pca_variance.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sns.scatterplot(
        data=frame,
        x="pct_delayed",
        y="share_nas",
        hue="season",
        s=10,
        alpha=0.35,
        ax=axes[0],
        linewidth=0,
    )
    axes[0].set_title("Before reduction: two original features")
    axes[0].set_xlabel("Share of arrivals delayed 15+ min (%)")
    axes[0].set_ylabel("NAS share of delay minutes")
    sc = axes[1].scatter(
        frame["pc1"],
        frame["pc2"],
        c=frame["pct_delayed"],
        s=8,
        alpha=0.4,
        cmap="YlOrRd",
        linewidths=0,
    )
    axes[1].set_title(
        f"After PCA: first two components ({100 * result['pca_variance_first_two']:.0f}% of variance)"
    )
    axes[1].set_xlabel("PC1")
    axes[1].set_ylabel("PC2")
    fig.colorbar(sc, ax=axes[1], label="Delayed 15+ min (%)")
    path = fig_dir / "24_pca_before_after.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")
    p = ax.scatter(
        frame["pc1"],
        frame["pc2"],
        frame["pc3"],
        c=frame["pct_delayed"],
        s=6,
        cmap="YlOrRd",
        alpha=0.35,
    )
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_zlabel("PC3")
    ax.set_title("PCA 3D view of delay profiles")
    fig.colorbar(p, ax=ax, shrink=0.6, label="Delayed 15+ min (%)")
    path = fig_dir / "25_pca_3d.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sc0 = axes[0].scatter(
        frame["pc1"],
        frame["pc2"],
        c=frame["pct_delayed"],
        s=8,
        alpha=0.4,
        cmap="YlOrRd",
        linewidths=0,
    )
    axes[0].set_title("PCA (global structure, delay rate)")
    axes[0].set_xlabel("PC1")
    axes[0].set_ylabel("PC2")
    fig.colorbar(sc0, ax=axes[0], label="Delayed 15+ min (%)")
    sc1 = axes[1].scatter(
        frame["tsne_1"],
        frame["tsne_2"],
        c=frame["pct_delayed"],
        s=8,
        alpha=0.4,
        cmap="YlOrRd",
        linewidths=0,
    )
    axes[1].set_title(
        f"t-SNE (local neighborhoods, perplexity={result['tsne_perplexity']})"
    )
    axes[1].set_xlabel("t-SNE 1")
    axes[1].set_ylabel("t-SNE 2")
    fig.colorbar(sc1, ax=axes[1], label="Delayed 15+ min (%)")
    path = fig_dir / "26_pca_vs_tsne_delay.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    plot_a = frame.copy()
    plot_a["cluster"] = plot_a["kmeans_original"].astype(str)
    plot_b = frame.copy()
    plot_b["cluster"] = plot_b["kmeans_pca"].astype(str)
    sns.scatterplot(
        data=plot_a,
        x="pc1",
        y="pc2",
        hue="cluster",
        s=10,
        alpha=0.4,
        ax=axes[0],
        linewidth=0,
    )
    axes[0].set_title(f"K-Means on original scaled features (k={result['k']})")
    axes[0].set_xlabel("PC1 (view only)")
    axes[0].set_ylabel("PC2 (view only)")
    sns.scatterplot(
        data=plot_b,
        x="pc1",
        y="pc2",
        hue="cluster",
        s=10,
        alpha=0.4,
        ax=axes[1],
        linewidth=0,
    )
    n_keep = result["n_pcs_for_80pct"]
    axes[1].set_title(
        f"K-Means on first {n_keep} PCs ({100 * result['variance_kept_for_clustering']:.0f}% variance)"
    )
    axes[1].set_xlabel("PC1")
    axes[1].set_ylabel("PC2")
    path = fig_dir / "27_kmeans_original_vs_pca.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    plot_t = frame.copy()
    plot_t["cluster"] = plot_t["kmeans_original"].astype(str)
    sns.scatterplot(
        data=plot_t,
        x="tsne_1",
        y="tsne_2",
        hue="cluster",
        s=10,
        alpha=0.4,
        ax=ax,
        linewidth=0,
    )
    ax.set_title("Same original-space K-Means labels on the t-SNE map")
    ax.set_xlabel("t-SNE 1")
    ax.set_ylabel("t-SNE 2")
    path = fig_dir / "28_tsne_by_kmeans.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    load = result["loadings"].iloc[:, :3]
    load.plot(kind="bar", ax=ax)
    ax.set_ylabel("Loading (correlation with component)")
    ax.set_title("What each of the first three PCs is made of")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(title="")
    path = fig_dir / "29_pca_loadings.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(path)

    return written


def dimred_export_table(result: dict) -> pd.DataFrame:
    cols = [
        "year",
        "month",
        "carrier",
        "airport",
        "pct_delayed",
        "pct_cancelled",
        "kmeans_original",
        "kmeans_pca",
        "pc1",
        "pc2",
        "pc3",
        "tsne_1",
        "tsne_2",
    ]
    return result["frame"][cols].copy()
