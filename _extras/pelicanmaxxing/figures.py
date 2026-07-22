"""Interactive versions of the five charts the post renders inline.

Same questions and same data as the matplotlib charts in charts.py, built with
plotly so the published post can be hovered.

Usage (from the post):
    import figures
    figures.fig_animal_scores()
"""

import ast
from collections import Counter

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from config import ANALYSIS_DIR

# Blog palette (custom.scss): dark zinc background, white ink, orange accent.
BG = "#18181b"
INK = "#e4e4e7"
MUTED = "#a1a1aa"
GRAY = "#71717a"
GRID = "#3f3f46"
ACCENT = "#eb841b"

FONT = dict(family="Georgia, serif", size=13, color=INK)

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


def short(model: str) -> str:
    return model.split("/")[-1]


def _layout(fig: go.Figure, title: str, height: int) -> go.Figure:
    fig.update_layout(
        # Every colour here is set explicitly, so plotly's default template is
        # dead weight in the page payload.
        template="none",
        title=dict(text=title, font=dict(size=15, color=INK), x=0.5, xanchor="center"),
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=FONT,
        height=height,
        margin=dict(l=10, r=10, t=60, b=40),
        showlegend=False,
        hoverlabel=dict(bgcolor="#27272a", bordercolor=ACCENT, align="left",
                        font=dict(family="Georgia, serif", size=12, color=INK)),
        dragmode=False,
    )
    # automargin, or the explicit margin above clips the category labels.
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickcolor=GRID,
                     automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickcolor=GRID,
                     automargin=True)
    return fig


def _bars(labels, values, colors, text, hover, title, height) -> go.Figure:
    """Horizontal bars with the value written at the end of each one."""
    fig = go.Figure(
        go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=colors, width=0.6,
            text=text, textposition="outside", textfont=dict(color=MUTED, size=12),
            hovertemplate=hover,
        )
    )
    _layout(fig, title, height)
    fig.update_xaxes(showgrid=False, showticklabels=False, visible=False,
                     range=[0, max(values) * 1.15])
    fig.update_yaxes(showgrid=False)
    return fig


def fig_animal_scores() -> go.Figure:
    """Mean judge animal rating per animal, all models pooled. If labs trained
    extra on pelicans, the pelican bar should top this chart."""
    data = pd.read_csv(ANALYSIS_DIR / "animal_scores.csv", index_col=0).iloc[:, 0].sort_values()
    return _bars(
        data.index, data.values,
        [ACCENT if a == "pelican" else GRAY for a in data.index],
        [f"{v:.2f}" for v in data.values],
        "<b>%{y}</b><br>%{x:.2f} out of 5<extra></extra>",
        "Mean animal rating by animal (1-5)", 340,
    )


def fig_vehicle_scores() -> go.Figure:
    """Mean judge vehicle rating per vehicle, all models pooled."""
    data = pd.read_csv(ANALYSIS_DIR / "vehicle_scores.csv", index_col=0).iloc[:, 0].sort_values()
    return _bars(
        data.index, data.values,
        [ACCENT if v == "bicycle" else GRAY for v in data.index],
        [f"{v:.2f}" for v in data.values],
        "<b>%{y}</b><br>%{x:.2f} out of 5<extra></extra>",
        "Mean vehicle rating by vehicle (1-5)", 300,
    )


def fig_animal_gaps() -> go.Figure:
    """Per lab, how much better each animal scores than that lab's own pelican.
    One dot per lab. Animals where all seven dots sit right of zero are the ones
    every lab draws better than pelicans — the claim this chart has to carry."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv").dropna(subset=["animal_rating"])
    cell = df.groupby(["model", "animal"])["animal_rating"].mean().unstack()
    gaps = cell.drop(columns="pelican").sub(cell["pelican"], axis=0)
    order = gaps.mean().sort_values().index  # worst at the bottom of the y axis

    fig = go.Figure()
    for animal in order:
        vals = gaps[animal]
        unanimous = (vals > 0).all()
        color = ACCENT if unanimous else GRAY
        fig.add_trace(go.Scatter(
            x=vals.values, y=[animal] * len(vals), mode="markers",
            marker=dict(color=color, size=9, opacity=0.85,
                        line=dict(color=BG, width=2)),  # 2px surface ring on overlap
            hovertext=[f"<b>{short(m)}</b><br>{animal} {v:+.2f} vs its own pelican"
                       for m, v in vals.items()],
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig.add_annotation(
            x=max(gaps.values.max() * 1.08, 0.05), y=animal,
            text=f"{int((vals > 0).sum())}/7", showarrow=False,
            font=dict(size=11, color=ACCENT if unanimous else MUTED),
            xanchor="left", yanchor="middle",
        )

    _layout(fig, "How much better each animal scores than the same lab's pelican", 360)
    fig.add_vline(x=0, line=dict(color=INK, width=2))
    lim = max(abs(gaps.values.min()), gaps.values.max()) * 1.35
    fig.update_xaxes(range=[-lim, lim], showgrid=False, zeroline=False,
                     title_text="Difference in mean animal rating (judge points)",
                     title_font=dict(color=MUTED, size=11))
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12))
    return fig


def fig_top_elements() -> go.Figure:
    """How often each scene element shows up (open-ended extraction)."""
    df = pd.read_csv(ANALYSIS_DIR / "element_counts.csv").head(15).iloc[::-1]
    return _bars(
        df["element"], df["share"],
        [GRAY] * len(df),
        [f"{v:.0%}" for v in df["share"]],
        "<b>%{y}</b><br>%{x:.0%} of images<extra></extra>",
        "Share of images containing each element", 430,
    )


def fig_pelican_bicycle_elements() -> go.Figure:
    """What the extractor found in the 21 pelican-bicycle images. The sun and
    the scarf are highlighted because they're the two elements people cite as
    evidence of a memorized scene."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv")
    pb = df[(df["animal"] == "pelican") & (df["vehicle"] == "bicycle")]
    sets = [set(s.strip().lower() for s in ast.literal_eval(e))
            for e in pb["feat_elements"] if isinstance(e, str)]
    counts = Counter(x for s in sets for x in s)
    # Drop the long tail of one-offs: at n=21 a single image is already 5%.
    data = pd.Series({k: v / len(sets) for k, v in counts.items() if v > 1}).sort_values()
    return _bars(
        data.index, data.values,
        [ACCENT if e in ("sun", "scarf") else GRAY for e in data.index],
        [f"{v:.0%}" for v in data.values],
        "<b>%{y}</b><br>%{x:.0%} of the 21 images<extra></extra>",
        "What's in the pelican-bicycle images", 400,
    )


def fig_elements_by_lab(animal: str = "pelican", vehicle: str = "bicycle") -> go.Figure:
    """One cell's element shares per lab, against the whole-experiment baseline.
    Every lab has only 3 images in a cell, so a dot can only sit at 0/33/67/100%
    — the point is the spread, not any single lab's value. Labs working from a
    shared template stack their dots; labs improvising scatter them."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv")
    df["els"] = df["feat_elements"].apply(
        lambda e: set(s.strip().lower() for s in ast.literal_eval(e)) if isinstance(e, str) else set()
    )
    pb = df[(df["animal"] == animal) & (df["vehicle"] == vehicle)]
    counts = Counter(x for s in pb["els"] for x in s)
    elements = [e for e, n in counts.most_common() if n > 1][::-1]
    overall = Counter(x for s in df["els"] for x in s)

    fig = go.Figure()
    for element in elements:
        per_lab = pb.groupby("model")["els"].apply(lambda s: sum(element in x for x in s) / len(s))
        # Only 3 images per lab, so every value collapses onto 0/33/67/100% and
        # the dots sit on top of each other. Size by how many labs share a value.
        stacked = per_lab.groupby(per_lab.values).apply(
            lambda s: ", ".join(sorted(short(m) for m in s.index)))
        fig.add_trace(go.Scatter(
            x=list(stacked.index), y=[element] * len(stacked), mode="markers",
            marker=dict(color=GRAY, size=[9 + 4 * len(v.split(", ")) for v in stacked],
                        opacity=0.65, line=dict(color=BG, width=2)),
            hovertext=[f"<b>{v}</b><br>{element} in {x:.0%} of their images"
                       for x, v in stacked.items()],
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=[overall.get(element, 0) / len(df)], y=[element], mode="markers",
            marker=dict(color=ACCENT, size=11, symbol="diamond", line=dict(color=BG, width=2)),
            hovertext=[f"<b>all 1,008 images</b><br>{element} in "
                       f"{overall.get(element, 0) / len(df):.0%}"],
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    _layout(fig, f"Each lab's {animal}-{vehicle} scene vs. the whole experiment", 430)
    fig.update_xaxes(range=[-0.05, 1.08], tickformat=".0%", showgrid=False,
                     title_text="Share of images containing the element "
                                "(grey = one lab's 3 images, orange = all 1,008)",
                     title_font=dict(color=MUTED, size=11))
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12))
    return fig


def fig_cell_ranking() -> go.Figure:
    """All 48 animal-vehicle combos ranked by mean judge score, the benchmark
    combo highlighted. The reader just finds the orange dot."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv").dropna(subset=["overall"])
    cells = df.groupby(["animal", "vehicle"])["overall"].mean().sort_values()
    labels = [f"{a} + {v}" for a, v in cells.index]
    is_target = [(a, v) == ("pelican", "bicycle") for a, v in cells.index]
    rank = len(cells) - is_target.index(True)

    stems_x, stems_y = [], []
    for label, value in zip(labels, cells.values):
        stems_x += [1, value, None]
        stems_y += [label, label, None]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=stems_x, y=stems_y, mode="lines",
                             line=dict(color=GRID, width=1), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=cells.values, y=labels, mode="markers",
        marker=dict(color=[ACCENT if t else GRAY for t in is_target],
                    size=[13 if t else 8 for t in is_target]),
        hovertemplate="<b>%{y}</b><br>%{x:.2f} out of 5<extra></extra>",
    ))
    _layout(fig, f"All {len(cells)} combos ranked — pelican + bicycle is #{rank}", 950)
    fig.update_xaxes(range=[1, 5], title_text="Mean judge score (1-5)",
                     title_font=dict(color=MUTED))
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11))
    return fig


def fig_regression_effects() -> go.Figure:
    """Forest plot of the difficulty-adjusted regression: one panel per effect
    type, one dot + 95% CI per lab, zero line for reference. CIs that exclude
    zero are highlighted."""
    df = pd.read_csv(ANALYSIS_DIR / "difficulty_adjusted_effects.csv")
    df = df[df["term"] != "pelican-bicycle cell (avg lab)"].copy()
    df[["lab", "kind"]] = df["term"].str.rsplit(":", n=1, expand=True)
    df["lab"] = df["lab"].map(short)

    panels = [
        ("is_pelican", "Pelican effect"),
        ("is_bicycle", "Bicycle effect"),
        ("is_pb", "Pelican-bicycle cell effect"),
    ]
    order = df[df["kind"] == "is_pb"].sort_values("coef")["lab"].tolist()
    lim = max(df["ci_low"].abs().max(), df["ci_high"].abs().max()) * 1.1

    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.03,
                        subplot_titles=[t for _, t in panels])
    for col, (kind, _) in enumerate(panels, start=1):
        g = df[df["kind"] == kind].set_index("lab").reindex(order)
        for lab, r in g.iterrows():
            sig = r["ci_low"] > 0 or r["ci_high"] < 0
            color = ACCENT if sig else GRAY
            fig.add_trace(go.Scatter(
                x=[r["ci_low"], r["ci_high"]], y=[lab, lab], mode="lines",
                line=dict(color=color, width=2), hoverinfo="skip",
            ), row=1, col=col)
            fig.add_trace(go.Scatter(
                x=[r["coef"]], y=[lab], mode="markers",
                marker=dict(color=color, size=9),
                hovertext=[f"<b>{lab}</b><br>{r['coef']:+.2f} judge points"
                           f"<br>95% CI {r['ci_low']:+.2f} to {r['ci_high']:+.2f}"
                           f"<br>p = {r['p']:.3f}"],
                hovertemplate="%{hovertext}<extra></extra>",
            ), row=1, col=col)
        fig.add_vline(x=0, line=dict(color=GRID, width=1), row=1, col=col)

    _layout(fig, "Difficulty-adjusted effects per lab", 420)
    fig.update_annotations(font=dict(size=12, color=INK))
    fig.update_xaxes(range=[-lim, lim], showgrid=False,
                     title_font=dict(color=MUTED, size=11))
    fig.update_xaxes(title_text="Judge points (dot = estimate, line = 95% CI)", row=1, col=2)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11))
    return fig
