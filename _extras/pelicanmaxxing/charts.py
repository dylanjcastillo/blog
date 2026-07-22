"""Simple, single-question charts for the pelicanmaxxing post.

Each chart answers exactly one question, stated in its title. Pelican-related
marks are highlighted; everything else is context gray.

The five charts the post renders inline return their figure; the rest are
exploratory and write straight to disk.

Usage:
    uv run python _extras/pelicanmaxxing/charts.py
"""

import ast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from config import ANALYSIS_DIR

FIGURES_DIR = ANALYSIS_DIR / "figures"

# Blog palette (custom.scss): dark zinc background, white ink, orange accent.
BG = "#18181b"
INK = "#e4e4e7"
MUTED = "#a1a1aa"
GRAY = "#71717a"
GRID = "#3f3f46"
ACCENT = "#eb841b"

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "font.size": 11,
        "font.family": ["Georgia", "serif"],
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def short(model: str) -> str:
    return model.split("/")[-1]


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / name, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {FIGURES_DIR / name}")


def chart_animal_scores() -> plt.Figure:
    """Mean judge animal rating per animal, all models pooled. If labs trained
    extra on pelicans, the pelican bar should top this chart."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv").dropna(subset=["animal_rating"])
    data = df.groupby("animal")["animal_rating"].mean().sort_values()

    fig, ax = plt.subplots(figsize=(7, 3.2))
    colors = [ACCENT if a == "pelican" else GRAY for a in data.index]
    ax.barh(data.index, data.values, color=colors, height=0.6)
    for y, (a, v) in enumerate(data.items()):
        ax.annotate(
            f"{v:.2f}", (v, y), va="center", xytext=(4, 0), textcoords="offset points",
            color=ACCENT if a == "pelican" else MUTED,
            fontweight="bold" if a == "pelican" else "normal",
        )
    ax.set_xlim(0, 5.3)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title("Mean animal rating by animal (1-5)")
    fig.tight_layout()
    return fig


def chart_cell_ranking() -> plt.Figure:
    """All 48 animal-vehicle combos ranked by mean judge score, the benchmark
    combo highlighted. The reader just finds the blue dot."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv").dropna(subset=["overall"])
    cells = df.groupby(["animal", "vehicle"])["overall"].mean().sort_values()
    labels = [f"{a} + {v}" for a, v in cells.index]
    is_target = [(a, v) == ("pelican", "bicycle") for a, v in cells.index]
    rank = len(cells) - list(is_target).index(True)

    fig, ax = plt.subplots(figsize=(7, 9))
    ax.hlines(range(len(cells)), 1, cells.values, color=GRID, lw=1, zorder=1)
    ax.scatter(
        cells.values, range(len(cells)),
        color=[ACCENT if t else GRAY for t in is_target],
        s=[70 if t else 30 for t in is_target], zorder=2,
    )
    ax.set_yticks(range(len(cells)), labels, fontsize=8)
    for label, t in zip(ax.get_yticklabels(), is_target):
        if t:
            label.set_color(ACCENT)
            label.set_fontweight("bold")
    ax.set_xlim(1, 5)
    ax.set_xlabel("Mean judge score (1-5)")
    ax.set_title(f"All {len(cells)} combos ranked — pelican + bicycle is #{rank}")
    ax.margins(y=0.01)
    fig.tight_layout()
    return fig


def chart_vehicle_scores() -> plt.Figure:
    """Mean judge vehicle rating per vehicle, all models pooled."""
    df = pd.read_csv(ANALYSIS_DIR / "vehicle_scores.csv", index_col=0).iloc[:, 0].sort_values()

    fig, ax = plt.subplots(figsize=(7, 2.8))
    colors = [ACCENT if v == "bicycle" else GRAY for v in df.index]
    ax.barh(df.index, df.values, color=colors, height=0.6)
    for y, (v, val) in enumerate(df.items()):
        ax.annotate(
            f"{val:.2f}", (val, y), va="center", xytext=(4, 0), textcoords="offset points",
            color=ACCENT if v == "bicycle" else MUTED,
            fontweight="bold" if v == "bicycle" else "normal",
        )
    ax.set_xlim(0, 5.3)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title("Mean vehicle rating by vehicle (1-5)")
    fig.tight_layout()
    return fig


def chart_top_elements() -> plt.Figure:
    """How often each scene element shows up (open-ended extraction)."""
    df = pd.read_csv(ANALYSIS_DIR / "element_counts.csv").head(15).iloc[::-1]

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.barh(df["element"], df["share"], color=GRAY, height=0.6)
    for y, v in enumerate(df["share"]):
        ax.annotate(
            f"{v:.0%}", (v, y), va="center", xytext=(4, 0), textcoords="offset points",
            color=MUTED,
        )
    ax.set_xlim(0, max(df["share"]) * 1.18)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title("Share of images containing each element")
    fig.tight_layout()
    return fig


def _element_signature_chart(kind: str, highlight: str, ncols: int) -> None:
    """Per {kind}: the scene elements most over-represented in its images
    versus every other {kind}. Sun and clouds are everywhere, so ranking by
    raw share says nothing; ranking by the gap shows what each subject
    actually drags into the scene."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv")
    df["els"] = df["feat_elements"].fillna("[]").map(ast.literal_eval)

    counts = pd.Series([e for els in df["els"] for e in els]).value_counts()
    common = set(counts[counts >= 15].index)  # drop one-off extractions

    def shares(rows):
        return pd.Series([e for els in rows["els"] for e in els]).value_counts() / len(rows)

    groups = sorted(df[kind].unique())
    nrows = -(-len(groups) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.1 * ncols, 2.1 * nrows))
    for ax, name in zip(axes.flat, groups):
        here, rest = shares(df[df[kind] == name]), shares(df[df[kind] != name])
        gap = (here - rest.reindex(here.index).fillna(0)).loc[list(common & set(here.index))]
        picked = gap.sort_values(ascending=False).head(4).index
        top = here[picked].sort_values()  # pick by gap, draw by share
        color = ACCENT if name == highlight else GRAY
        ax.barh(top.index, here[top.index], color=color, height=0.62)
        for y, e in enumerate(top.index):
            ax.annotate(
                f"{here[e]:.0%}", (here[e], y), va="center", xytext=(4, 0),
                textcoords="offset points", color=MUTED, fontsize=9,
            )
        ax.set_xlim(0, here[top.index].max() * 1.3)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
        ax.set_title(name, fontsize=11, color=ACCENT if name == highlight else INK)
        ax.tick_params(labelsize=9)
    for ax in axes.flat[len(groups):]:
        ax.set_visible(False)
    fig.suptitle(f"What each {kind} gets drawn with", fontsize=13)
    save(fig, f"{kind}_elements.png")


def _cell_element_matrix():
    """Per grid cell: the share of its 21 images containing each common
    element. Returns (matrix, ordered element list)."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv")
    df["els"] = df["feat_elements"].fillna("[]").map(ast.literal_eval)
    counts = pd.Series([e for els in df["els"] for e in els]).value_counts()
    elements = list(counts[counts >= 3].index)
    rows = {}
    for key, g in df.groupby(["animal", "vehicle"]):
        share = pd.Series([e for els in g["els"] for e in els]).value_counts() / len(g)
        rows[key] = share.reindex(elements).fillna(0)
    return pd.DataFrame(rows).T, elements


def chart_signature_strength() -> None:
    """How far each subject bends the scene away from the grid average, as the
    mean absolute gap across common elements. Every vehicle outranks every
    animal: the vehicle decides what gets drawn, the animal barely nudges it,
    and the pelican nudges it less than most."""
    matrix, elements = _cell_element_matrix()
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv")
    df["els"] = df["feat_elements"].fillna("[]").map(ast.literal_eval)

    def share(rows):
        counts = pd.Series([e for els in rows["els"] for e in els]).value_counts()
        return counts.reindex(elements).fillna(0) / len(rows)

    base = share(df)
    rows = []
    for kind in ["vehicle", "animal"]:
        for name, g in df.groupby(kind):
            gap = share(g) - base
            rows.append({"kind": kind, "name": name, "strength": gap.abs().mean(), "top": gap.idxmax()})
    data = pd.DataFrame(rows).sort_values("strength")

    focus = {"pelican", "bicycle"}
    colors = [
        ACCENT if n in focus else (MUTED if k == "vehicle" else GRAY)
        for k, n in zip(data["kind"], data["name"])
    ]
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.barh(data["name"], 100 * data["strength"], color=colors, height=0.68)
    for y, (_, r) in enumerate(data.iterrows()):
        ax.annotate(
            f"mostly {r['top']}", (100 * r["strength"], y), va="center",
            xytext=(5, 0), textcoords="offset points", fontsize=9,
            color=ACCENT if r["name"] in focus else MUTED,
        )
    for label, name in zip(ax.get_yticklabels(), data["name"]):
        if name in focus:
            label.set_color(ACCENT)
    boundary = (data["kind"] == "animal").sum()  # every vehicle outranks every animal
    ax.axhline(boundary - 0.5, color=GRID, lw=1, ls=":")
    ax.set_xlim(0, 100 * data["strength"].max() * 1.45)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    handles = [
        plt.Line2D([], [], color=MUTED, lw=6, label="vehicles"),
        plt.Line2D([], [], color=GRAY, lw=6, label="animals"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=10)
    ax.set_title("How much each subject changes the scene around it")
    save(fig, "signature_strength.png")


def chart_cell_clusters() -> None:
    """The 48 element profiles laid out in two dimensions by t-SNE on the same
    distance matrix. Cells group by vehicle, and the famous one sits inside the
    bicycle group. The layout shows grouping, not distance — every number
    quoted in the post comes from the distance matrix itself."""
    from sklearn.manifold import TSNE

    matrix, _ = _cell_element_matrix()
    idf = np.log(len(matrix) / (matrix > 0).sum(axis=0).clip(lower=1))
    unit = (matrix * idf).pipe(lambda x: x.div(np.linalg.norm(x, axis=1), axis=0))
    dist = np.clip((1 - unit @ unit.T).values, 0, None)
    np.fill_diagonal(dist, 0)
    coords = TSNE(
        n_components=2, metric="precomputed", init="random",
        perplexity=15, early_exaggeration=4, random_state=0,
    ).fit_transform(dist)

    labels = [f"{a} + {v}" for a, v in matrix.index]
    target = "pelican + bicycle"
    is_pb = np.array(labels) == target

    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.scatter(coords[~is_pb, 0], coords[~is_pb, 1], color=GRAY, s=32, zorder=2)
    ax.scatter(coords[is_pb, 0], coords[is_pb, 1], color=ACCENT, s=110, zorder=3)

    notable = {
        target: (0, -16, "center", "top"),
        "heron + bicycle": (-11, 0, "right", "center"),  # its closest match anywhere
    }
    for name, (dx, dy, ha, va) in notable.items():
        i = labels.index(name)
        ax.annotate(
            name, coords[i], xytext=(dx, dy), textcoords="offset points",
            ha=ha, va=va, fontsize=9,
            color=ACCENT if name == target else INK,
            fontweight="bold" if name == target else "normal",
        )
    wheeled = [i for i, (a, v) in enumerate(matrix.index)
               if a == "whale" and v != "boat" and v != "plane"]
    ax.annotate(
        "the four wheeled whales", coords[wheeled].mean(axis=0),
        xytext=(0, 18), textcoords="offset points", ha="center", fontsize=9, color=MUTED,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.margins(0.13)
    ax.set_title("The 48 combinations, grouped by what gets drawn")
    save(fig, "cell_clusters.png")


def chart_cell_stability() -> None:
    """Does a combination keep producing the same scene? Mean pairwise Jaccard
    overlap between the element sets of a cell's 21 images, split into pairs
    from the same lab and pairs from different labs. A memorized scene would
    push a cell onto the diagonal: other labs' images as alike as your own."""
    import itertools

    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv")
    df["els"] = df["feat_elements"].fillna("[]").map(lambda s: set(ast.literal_eval(s)))

    def overlap(a, b):
        union = a | b
        return len(a & b) / len(union) if union else np.nan

    rows = []
    for (animal, vehicle), g in df.groupby(["animal", "vehicle"]):
        sets, labs = list(g["els"]), list(g["model"])
        pairs = list(itertools.combinations(range(len(sets)), 2))
        same = [overlap(sets[i], sets[j]) for i, j in pairs if labs[i] == labs[j]]
        diff = [overlap(sets[i], sets[j]) for i, j in pairs if labs[i] != labs[j]]
        rows.append({"cell": f"{animal} + {vehicle}",
                     "within": np.nanmean(same), "between": np.nanmean(diff)})
    data = pd.DataFrame(rows).set_index("cell")
    data["ratio"] = data["between"] / data["within"]

    target = "pelican + bicycle"
    cells = data["ratio"].sort_values()
    is_target = [c == target for c in cells.index]
    rank = len(cells) - is_target.index(True)

    fig, ax = plt.subplots(figsize=(7, 9))
    ax.hlines(range(len(cells)), 0, cells.values, color=GRID, lw=1, zorder=1)
    ax.scatter(
        cells.values, range(len(cells)),
        color=[ACCENT if t else GRAY for t in is_target],
        s=[70 if t else 30 for t in is_target], zorder=2,
    )
    ax.axvline(1.0, color=GRID, lw=1, ls=":", zorder=1)
    ax.annotate(
        "a memorized scene\nwould reach here", (1.0, 2), xytext=(-8, 0),
        textcoords="offset points", ha="right", va="center", fontsize=9, color=MUTED,
    )
    ax.set_yticks(range(len(cells)), cells.index, fontsize=8)
    for label, t in zip(ax.get_yticklabels(), is_target):
        if t:
            label.set_color(ACCENT)
            label.set_fontweight("bold")
    ax.set_xlim(0, 1.12)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Share of a lab's own consistency that rival labs reproduce")
    ax.set_title(f"All 48 combos ranked — pelican + bicycle is #{rank}")
    ax.margins(y=0.01)
    save(fig, "cell_stability.png")
    print(f"  ratio {data.loc[target, 'ratio']:.3f} vs median {data['ratio'].median():.3f}, rank {rank}/48")


def chart_cell_uniqueness() -> None:
    """Each cell becomes a vector of element shares, weighted so rare elements
    count for more than the universal sun and clouds. Two independent measures
    of uniqueness: mean cosine distance to the other 47 cells (is it unusual?)
    and distance to its nearest neighbour (does it have a close analogue?)."""
    matrix, _ = _cell_element_matrix()
    matrix.index = [f"{a} + {v}" for a, v in matrix.index]
    idf = np.log(len(matrix) / (matrix > 0).sum(axis=0).clip(lower=1))
    unit = (matrix * idf).pipe(lambda x: x.div(np.linalg.norm(x, axis=1), axis=0))
    dist = 1 - unit @ unit.T
    np.fill_diagonal(dist.values, np.nan)
    data = pd.DataFrame({"mean": dist.mean(axis=1), "nn": dist.min(axis=1), "twin": dist.idxmin(axis=1)})

    target = "pelican + bicycle"
    rank_mean = int(data["mean"].rank(ascending=False)[target])
    is_pb = data.index == target

    fig, ax = plt.subplots(figsize=(7.8, 6.2))
    ax.axvline(data["mean"].median(), color=GRID, lw=1, ls=":")
    ax.axhline(data["nn"].median(), color=GRID, lw=1, ls=":")
    ax.scatter(data.loc[~is_pb, "mean"], data.loc[~is_pb, "nn"], color=GRAY, s=32, zorder=2)
    ax.scatter(data.loc[is_pb, "mean"], data.loc[is_pb, "nn"], color=ACCENT, s=110, zorder=3)

    notable = ["otter + boat", "raccoon + plane", "antelope + plane", "heron + scooter",
               target]
    for name in notable:
        r = data.loc[name]
        ax.annotate(
            name, (r["mean"], r["nn"]), xytext=(0, 11), textcoords="offset points",
            ha="center", fontsize=9,
            color=ACCENT if name == target else INK,
            fontweight="bold" if name == target else "normal",
        )
    ax.set_xlabel("Distance from every other combination")
    ax.set_ylabel("Distance from its closest match")
    ax.set_title(f"Two ways of being unique — pelican + bicycle is #{rank_mean} of 48 on the first")
    save(fig, "cell_uniqueness.png")


def chart_cell_elements() -> None:
    """One panel per vehicle, every animal inside it. Each vehicle sets its
    own scene (boats bring water, planes bring clouds); the question is
    whether the pelican row breaks the pattern its vehicle establishes."""
    matrix, elements = _cell_element_matrix()
    cols = elements[:10]
    animals = sorted(matrix.index.get_level_values(0).unique())
    vehicles = ["bicycle"] + [
        v for v in sorted(matrix.index.get_level_values(1).unique()) if v != "bicycle"
    ]
    top = matrix[cols].values.max()
    cmap = LinearSegmentedColormap.from_list("accent", [BG, ACCENT])

    fig, axes = plt.subplots(len(vehicles), 1, figsize=(8.2, 2.6 * len(vehicles)))
    for ax, vehicle in zip(axes, vehicles):
        data = matrix.loc[[(a, vehicle) for a in animals], cols]
        ax.imshow(data.values, cmap=cmap, aspect="auto", vmin=0, vmax=top)
        for y in range(len(animals)):
            for x in range(len(cols)):
                v = data.values[y, x]
                ax.annotate(
                    f"{v:.0%}" if v else "", (x, y), ha="center", va="center",
                    fontsize=7.5, color=INK if v < 0.45 * top else BG,
                )
        ax.set_xticks(range(len(cols)), cols if ax is axes[0] else [], rotation=45,
                      ha="left", fontsize=9)
        ax.xaxis.tick_top()
        ax.set_yticks(range(len(animals)), animals, fontsize=9)
        focus = animals.index("pelican")
        ax.get_yticklabels()[focus].set_color(ACCENT if vehicle == "bicycle" else INK)
        if vehicle == "bicycle":
            ax.axhline(focus - 0.5, color=ACCENT, lw=1)
            ax.axhline(focus + 0.5, color=ACCENT, lw=1)
        ax.set_ylabel(vehicle, color=ACCENT if vehicle == "bicycle" else INK, fontsize=12)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0)
    save(fig, "cell_elements.png")


def chart_cell_similarity() -> None:
    """How closely every other cell's element profile matches the famous one
    (cosine similarity). A memorized scene would sit apart from the grid;
    instead its nearest neighbours are other bicycles and other pelicans."""
    matrix, _ = _cell_element_matrix()
    unit = matrix.div(np.linalg.norm(matrix, axis=1), axis=0)
    sim = (unit @ unit.loc[("pelican", "bicycle")]).drop(index=("pelican", "bicycle"))
    sim = sim.sort_values()

    colors = [
        ACCENT if v == "bicycle" else (INK if a == "pelican" else GRAY)
        for a, v in sim.index
    ]
    fig, ax = plt.subplots(figsize=(7.5, 8))
    ax.barh([f"{a} + {v}" for a, v in sim.index], sim.values, color=colors, height=0.72)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Element-profile similarity to pelican + bicycle")
    ax.tick_params(labelsize=8.5)
    ax.axvline(sim.median(), color=GRID, lw=1, ls=":")
    ax.annotate(
        "median", (sim.median(), len(sim) - 0.2), ha="center", fontsize=9, color=MUTED,
    )
    handles = [
        plt.Line2D([], [], color=ACCENT, lw=6, label="other bicycles"),
        plt.Line2D([], [], color=INK, lw=6, label="other pelicans"),
        plt.Line2D([], [], color=GRAY, lw=6, label="everything else"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)
    save(fig, "cell_similarity.png")


def chart_element_signatures() -> None:
    _element_signature_chart("animal", "pelican", ncols=4)
    _element_signature_chart("vehicle", "bicycle", ncols=3)


def _dumbbell_chart(kind: str, rating_col: str, target: str) -> None:
    """Per lab: mean judge rating for the benchmark {kind} (blue) vs the lab's
    other {kind}s (gray), connected by a line. Blue right of gray = the lab is
    better at the benchmark subject."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv").dropna(subset=[rating_col])
    df["model"] = df["model"].map(short)

    rows = []
    for model, g in df.groupby("model"):
        rows.append(
            {
                "model": model,
                "target": g.loc[g[kind] == target, rating_col].mean(),
                "others": g.loc[g[kind] != target, rating_col].mean(),
            }
        )
    data = pd.DataFrame(rows)
    data = data.sort_values("target")  # no gap sorting: plain scores, easy read

    fig, ax = plt.subplots(figsize=(7.5, 4))
    for y, (_, r) in enumerate(data.iterrows()):
        ax.plot([r["others"], r["target"]], [y, y], color=GRID, lw=2, zorder=1)
        ax.scatter([r["others"]], [y], color=GRAY, s=70, zorder=2)
        ax.scatter([r["target"]], [y], color=ACCENT, s=80, zorder=3)
    ax.set_yticks(range(len(data)), data["model"])
    top = len(data) - 1
    last = data.iloc[-1]
    target_is_right = last["target"] >= last["others"]
    ax.annotate(
        target, (last["target"], top),
        xytext=(10 if target_is_right else -10, 0), textcoords="offset points",
        ha="left" if target_is_right else "right", va="center",
        color=ACCENT, fontsize=10, fontweight="bold",
    )
    ax.annotate(
        f"other {kind}s", (last["others"], top),
        xytext=(-10 if target_is_right else 10, 0), textcoords="offset points",
        ha="right" if target_is_right else "left", va="center",
        color=MUTED, fontsize=10,
    )
    ax.set_xlim(3.4, 5.05)
    ax.set_xlabel(f"Mean {kind} rating (1-5)")
    ax.set_title(f"{target.capitalize()} vs. the lab's other {kind}s")
    ax.margins(y=0.12)
    save(fig, f"{target}_vs_others_by_lab.png")


def chart_score_distributions() -> None:
    _dumbbell_chart("animal", "animal_rating", "pelican")
    _dumbbell_chart("vehicle", "vehicle_rating", "bicycle")


def chart_per_lab_favoritism() -> None:
    """Quadrant chart: animal advantage vs vehicle advantage for every
    animal-vehicle combo of every lab (gray), with each lab's pelican-bicycle
    in blue. A lab that trained on the benchmark would show a blue dot deep in
    the shaded upper-right, outside the gray cloud."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv").dropna(subset=["animal_rating", "vehicle_rating"])
    df["model"] = df["model"].map(short)

    points = []
    for model, g in df.groupby("model"):
        a_gap = {
            a: g.loc[g["animal"] == a, "animal_rating"].mean()
            - g.loc[g["animal"] != a, "animal_rating"].mean()
            for a in g["animal"].unique()
        }
        v_gap = {
            v: g.loc[g["vehicle"] == v, "vehicle_rating"].mean()
            - g.loc[g["vehicle"] != v, "vehicle_rating"].mean()
            for v in g["vehicle"].unique()
        }
        points += [
            {"model": model, "animal": a, "vehicle": v, "x": ax_, "y": vy}
            for a, ax_ in a_gap.items()
            for v, vy in v_gap.items()
        ]
    pts = pd.DataFrame(points)
    is_pb = (pts["animal"] == "pelican") & (pts["vehicle"] == "bicycle")

    lim = max(pts["x"].abs().max(), pts["y"].abs().max()) * 1.12
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.axvspan(0, lim, ymin=0.5, ymax=1, color=ACCENT, alpha=0.10, zorder=0)
    ax.annotate(
        "pelicanmaxxing zone",
        (lim * 0.95, lim * 0.95), ha="right", va="top", fontsize=10, color=ACCENT,
    )
    ax.axhline(0, color=GRID, lw=1, zorder=1)
    ax.axvline(0, color=GRID, lw=1, zorder=1)
    ax.scatter(pts.loc[~is_pb, "x"], pts.loc[~is_pb, "y"], color=GRAY, s=14, alpha=0.4, zorder=2)
    ax.scatter(pts.loc[is_pb, "x"], pts.loc[is_pb, "y"], color=ACCENT, s=70, zorder=3)
    pb = pts[is_pb]
    ax.annotate(
        "pelican + bicycle\n(one dot per lab)",
        (pb["x"].mean(), pb["y"].max()), xytext=(0, 30), textcoords="offset points",
        ha="center", fontsize=10, color=ACCENT, fontweight="bold",
        arrowprops={"arrowstyle": "-", "color": ACCENT, "lw": 1},
    )
    for name in ["claude-sonnet-5", "grok-4.5"]:
        r = pb[pb["model"] == name]
        if len(r):
            ax.annotate(
                name, (r["x"].iloc[0], r["y"].iloc[0]),
                xytext=(0, -14), textcoords="offset points", ha="center", fontsize=9, color=INK,
            )
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel("Animal advantage (judge points)")
    ax.set_ylabel("Vehicle advantage (judge points)")
    ax.set_title("Does any lab favor the benchmark's subjects?")
    save(fig, "per_lab_favoritism.png")


def chart_regression_effects() -> plt.Figure:
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
        ("is_pb", "Pelican-bicycle\ncell effect"),
    ]
    order = df[df["kind"] == "is_pb"].sort_values("coef")["lab"].tolist()
    lim = max(df["ci_low"].abs().max(), df["ci_high"].abs().max()) * 1.1

    fig, axes = plt.subplots(1, 3, figsize=(9.5, 3.4), sharey=True, sharex=True)
    for ax, (kind, title) in zip(axes, panels):
        g = df[df["kind"] == kind].set_index("lab").reindex(order)
        ax.axvline(0, color=GRID, lw=1, zorder=1)
        for y, (_, r) in enumerate(g.iterrows()):
            sig = r["ci_low"] > 0 or r["ci_high"] < 0
            color = ACCENT if sig else GRAY
            ax.plot([r["ci_low"], r["ci_high"]], [y, y], color=color, lw=2, zorder=2)
            ax.scatter([r["coef"]], [y], color=color, s=42, zorder=3)
        ax.set_yticks(range(len(order)), order)
        ax.set_title(title, fontsize=10.5)
        ax.set_xlim(-lim, lim)
    axes[1].set_xlabel("Judge points (dot = estimate, line = 95% CI)")
    fig.tight_layout()
    return fig


def chart_model_leaderboard() -> None:
    """Context: overall judge score per model across the whole grid."""
    df = pd.read_csv(ANALYSIS_DIR / "dataset.csv").dropna(subset=["overall"])
    data = df.groupby("model")["overall"].mean().sort_values()
    labels = [short(m) for m in data.index]

    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.barh(labels, data.values, color=GRAY, height=0.6)
    for y, v in enumerate(data.values):
        ax.annotate(
            f"{v:.2f}", (v, y), va="center", xytext=(4, 0), textcoords="offset points",
            color=MUTED,
        )
    ax.set_xlim(0, 5.3)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title("Mean judge score by model (1-5)")
    save(fig, "model_leaderboard.png")


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    save(chart_animal_scores(), "animal_scores.png")
    save(chart_cell_ranking(), "cell_ranking.png")
    save(chart_vehicle_scores(), "vehicle_scores.png")
    save(chart_top_elements(), "top_elements.png")
    save(chart_regression_effects(), "regression_effects.png")
    chart_element_signatures()
    chart_signature_strength()
    chart_cell_clusters()
    chart_cell_stability()
    chart_cell_uniqueness()
    chart_cell_elements()
    chart_cell_similarity()
    chart_score_distributions()
    chart_per_lab_favoritism()
    chart_model_leaderboard()


if __name__ == "__main__":
    main()
