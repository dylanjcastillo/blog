"""Interactive plotly charts the post renders inline.

Reads the CSVs evaluate.py writes to data/analysis/.

Usage (from the post):
    import figures
    figures.fig_ndcg_by_dim()
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from config import ANALYSIS_DIR, FIT_SIZE_DATASET, FULL_DIM, REPORT_EXCLUDE

# Blog palette (custom.scss): dark zinc background, white ink, orange accent.
BG = "#18181b"
INK = "#e4e4e7"
MUTED = "#a1a1aa"
GRAY = "#71717a"
GRID = "#3f3f46"
ACCENT = "#eb841b"

FONT = dict(family="Georgia, serif", size=13, color=INK)

METHOD_STYLE = {
    "mrl": dict(name="Matryoshka (truncate + renorm)", color=ACCENT, dash="solid"),
    "pca_in": dict(name="PCA (fit in-domain)", color="#60a5fa", dash="solid"),
    "pca_ood": dict(name="PCA (fit on MS MARCO)", color="#f87171", dash="solid"),
}

# Hover is the only interaction worth keeping; the toolbar just clutters the
# post. Set on the renderers rather than passed to fig.show(), because show()
# emits a second output that Quarto lays out as an empty subfigure.
CONFIG = {"displayModeBar": False, "responsive": True}
for _renderer in ("plotly_mimetype", "notebook", "notebook_connected"):
    pio.renderers[_renderer].config.update(CONFIG)


def init() -> None:
    """Emit plotly's loader script from the post's hidden setup cell.

    On its first figure plotly displays the loader as an output of its own,
    which Quarto counts as a second figure and lays out as a subfigure. Burning
    it here, where the cell output is suppressed, keeps the first real figure
    to a single output."""
    go.Figure().show()


def _results() -> pd.DataFrame:
    df = pd.read_csv(ANALYSIS_DIR / "results.csv")
    return df[~df["dataset"].isin(REPORT_EXCLUDE)]


def _layout(fig: go.Figure, title: str, height: int, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="none",
        title=dict(text=title, font=dict(size=15, color=INK), x=0.5, xanchor="center"),
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=FONT,
        height=height,
        margin=dict(l=10, r=10, t=60, b=40),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0.5, xanchor="center",
                    font=dict(size=12, color=MUTED)),
        hoverlabel=dict(bgcolor="#27272a", bordercolor=ACCENT, align="left",
                        font=dict(family="Georgia, serif", size=12, color=INK)),
        dragmode=False,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickcolor=GRID,
                     automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickcolor=GRID,
                     automargin=True)
    return fig


def _method_trace(sub: pd.DataFrame, method: str, metric: str, showlegend: bool) -> go.Scatter:
    style = METHOD_STYLE[method]
    sub = sub.sort_values("dim")
    return go.Scatter(
        x=sub["dim"], y=sub[metric],
        mode="lines+markers",
        name=style["name"], legendgroup=method, showlegend=showlegend,
        line=dict(color=style["color"], dash=style["dash"], width=2),
        marker=dict(size=6, color=style["color"]),
        hovertemplate=f"<b>{style['name']}</b><br>d=%{{x}}<br>{metric}=%{{y:.4f}}<extra></extra>",
    )


MAIN_METHODS = ("mrl", "pca_in")  # pca_ood is reported in its own section


def fig_ndcg_by_dim(metric: str = "ndcg@10", methods=MAIN_METHODS) -> go.Figure:
    """The main chart: one panel per dataset, one line per method, the
    full-dim score as a dashed ceiling."""
    df = _results()
    datasets = sorted(df["dataset"].unique())
    n_rows = (len(datasets) + 1) // 2
    fig = make_subplots(rows=n_rows, cols=2, subplot_titles=datasets,
                        shared_xaxes=False, vertical_spacing=0.4 / n_rows)

    for i, name in enumerate(datasets):
        row, col = i // 2 + 1, i % 2 + 1
        sub = df[df["dataset"] == name]
        full = sub.loc[sub["method"] == "full", metric].iloc[0]
        for method in methods:
            fig.add_trace(_method_trace(sub[sub["method"] == method], method, metric,
                                        showlegend=(i == 0)), row=row, col=col)
        fig.add_hline(y=full, line=dict(color=MUTED, dash="dash", width=1),
                      annotation_text=f"full ({full:.3f})",
                      annotation_font=dict(size=10, color=MUTED), row=row, col=col)

    _layout(fig, f"{metric.upper()} by embedding dimension", 200 + 240 * n_rows)
    fig.update_xaxes(type="log", tickvals=[32, 64, 128, 256, 512])
    for ann in fig.layout.annotations[:len(datasets)]:
        ann.font = dict(size=13, color=INK)
    return fig


ADA_SLUG = "openai__text-embedding-ada-002"


def _retention_means(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    full = df[df["method"] == "full"].set_index("dataset")[metric]
    sub = df[df["method"] != "full"].copy()
    sub["retention"] = sub.apply(lambda r: r[metric] / full[r["dataset"]], axis=1)
    return sub.groupby(["method", "dim"])["retention"].mean().reset_index()


def fig_retention(metric: str = "ndcg@10", include_ada: bool = True,
                  methods=MAIN_METHODS) -> go.Figure:
    """Fraction of full-dim performance retained, averaged over datasets.
    Two panels when the ada-002 control results exist: ada left, the main
    (MRL) model right, mirroring the grouped table in the post."""
    df = _results()
    n_datasets = df["dataset"].nunique()

    panels = [("3-small (MRL)", _retention_means(df, metric))]
    ada_path = ANALYSIS_DIR.parent / ADA_SLUG / "results.csv"
    if include_ada and ada_path.exists() and ADA_SLUG not in str(ANALYSIS_DIR):
        ada = pd.read_csv(ada_path)
        # ada was not run on every dataset; average both panels over the
        # shared datasets so the two means have the same basis.
        shared = set(df["dataset"].unique()) & set(ada["dataset"].unique())
        n_datasets = len(shared)
        panels = [
            ("ada-002 (no MRL)", _retention_means(ada[ada["dataset"].isin(shared)], metric)),
            ("3-small (MRL)", _retention_means(df[df["dataset"].isin(shared)], metric)),
        ]

    fig = make_subplots(rows=1, cols=len(panels), subplot_titles=[t for t, _ in panels],
                        shared_yaxes=True, horizontal_spacing=0.06)
    for col, (_, mean) in enumerate(panels, start=1):
        for method in methods:
            fig.add_trace(_method_trace(mean[mean["method"] == method], method, "retention",
                                        showlegend=(col == 1)), row=1, col=col)
        fig.add_hline(y=1.0, line=dict(color=MUTED, dash="dash", width=1), row=1, col=col)

    _layout(fig, f"Share of full-dim {metric.upper()} retained (mean of {n_datasets} datasets)", 440)
    fig.update_xaxes(type="log", tickvals=[32, 64, 128, 256, 512],
                     title=dict(text="dimensions", font=dict(size=12, color=MUTED)))
    fig.update_yaxes(tickformat=".0%")
    for ann in fig.layout.annotations[:len(panels)]:
        ann.font = dict(size=13, color=INK)
    return fig


def fig_ood_gap(dim: int = 64, metric: str = "ndcg@10") -> go.Figure:
    """Per dataset at one aggressive dim: does moving PCA's fit corpus
    out of domain cost more than switching to matryoshka truncation?"""
    df = _results()
    df = df[(df["dim"] == dim) & (df["method"].isin(["mrl", "pca_in", "pca_ood"]))]

    fig = go.Figure()
    for method in ["pca_in", "mrl", "pca_ood"]:
        style = METHOD_STYLE[method]
        sub = df[df["method"] == method].sort_values("dataset")
        fig.add_trace(go.Bar(
            x=sub["dataset"], y=sub[metric], name=style["name"],
            marker_color=style["color"],
            hovertemplate=f"<b>{style['name']}</b><br>%{{x}}: %{{y:.4f}}<extra></extra>",
        ))
    _layout(fig, f"{metric.upper()} at d={dim}: in-domain PCA vs matryoshka vs transferred PCA", 400)
    fig.update_layout(barmode="group", bargap=0.25)
    return fig


def fig_index_growth() -> go.Figure:
    """Index-growth simulation: PCA fit on half the corpus, queries split by
    whether their relevant docs were in the fit half. MRL's own seen/unseen
    gap is the query-difficulty control."""
    df = pd.read_csv(ANALYSIS_DIR / "index_growth.csv")
    styles = {
        ("pca_half", "seen"): dict(color="#60a5fa", dash="solid", name="PCA, docs seen by fit"),
        ("pca_half", "unseen"): dict(color="#60a5fa", dash="dot", name="PCA, docs added after fit"),
        ("mrl", "seen"): dict(color=ACCENT, dash="solid", name="Matryoshka, same 'seen' queries"),
        ("mrl", "unseen"): dict(color=ACCENT, dash="dot", name="Matryoshka, same 'unseen' queries"),
    }
    fig = go.Figure()
    for (method, group), style in styles.items():
        sub = df[(df["method"] == method) & (df["group"] == group)].sort_values("dim")
        fig.add_trace(go.Scatter(
            x=sub["dim"], y=sub["ndcg@10"], mode="lines+markers", name=style["name"],
            line=dict(color=style["color"], dash=style["dash"], width=2),
            marker=dict(size=6, color=style["color"]),
            hovertemplate=f"<b>{style['name']}</b><br>d=%{{x}}<br>ndcg@10=%{{y:.4f}}<extra></extra>",
        ))
    _layout(fig, f"PCA fit on half of {FIT_SIZE_DATASET}: does quality drop on docs the fit never saw?", 440)
    fig.update_xaxes(type="log", tickvals=[32, 64, 128, 256, 512],
                     title=dict(text="dimensions", font=dict(size=12, color=MUTED)))
    return fig


def fig_fit_size(metric: str = "ndcg@10") -> go.Figure:
    """PCA fit-sample-size sweep on the largest corpus."""
    df = pd.read_csv(ANALYSIS_DIR / "fit_size_sweep.csv")
    sizes = sorted(df["fit_size"].unique())
    shades = ["#3f3f46", "#71717a", "#a1a1aa", ACCENT][-len(sizes):]

    fig = go.Figure()
    for size, color in zip(sizes, shades):
        sub = df[df["fit_size"] == size].sort_values("dim")
        fig.add_trace(go.Scatter(
            x=sub["dim"], y=sub[metric], mode="lines+markers",
            name=f"fit on {size:,} docs",
            line=dict(color=color, width=2), marker=dict(size=6, color=color),
            hovertemplate=f"<b>{size:,} docs</b><br>d=%{{x}}<br>{metric}=%{{y:.4f}}<extra></extra>",
        ))
    _layout(fig, f"In-domain PCA on {FIT_SIZE_DATASET}: {metric.upper()} by fit-sample size", 420)
    fig.update_xaxes(type="log", tickvals=[32, 64, 128, 256, 512],
                     title=dict(text="dimensions", font=dict(size=12, color=MUTED)))
    return fig
