"""Assemble a tidy dataset and compute the headline analyses:

1. Animal scores — mean judge score per animal: are pelicans drawn better?
2. Vehicle scores — mean vehicle rating per vehicle: are bicycles drawn better?
3. Interaction residual — does pelican-bicycle beat what the model's pelican
   row and bicycle column predict?
4. Facing direction — share of images facing left / right / ambiguous.
5. Scene elements — open-ended element counts (what do models put in the
   background?).
6. Cross-lab convergence — do different labs agree on composition (facing +
   element overlap) more in some grid cells than others?

Writes CSVs and figures to data/analysis/, prints summary tables.

Usage:
    uv run python _extras/pelicanmaxxing/analysis.py
"""

import json
from collections import Counter

import pandas as pd
import plotly.express as px

from config import (
    ANALYSIS_DIR,
    DATA_DIR,
    FEATURES_DIR,
    GENERATIONS_DIR,
    JUDGE_MODELS,
    MODELS,
    RENDERS_DIR,
    SCORES_DIR,
    build_prompts,
    model_slug,
)

FEATURE_KEYS = ["animal", "vehicle", "facing", "elements"]

def load_dataset() -> pd.DataFrame:
    active = {model_slug(m) for m in MODELS}
    valid_ids = {p["id"] for p in build_prompts()}
    # Failures from before retry-until-success existed: their records were
    # regenerated with a fresh attempt sequence, so add the historical failure
    # back to the count.
    log_path = DATA_DIR / "first_attempt_failures.json"
    prior_failures = (
        {e["file"] for e in json.loads(log_path.read_text())} if log_path.exists() else set()
    )
    rows = []
    for gen_path in sorted(GENERATIONS_DIR.glob("*/*.json")):
        if gen_path.parent.name not in active:
            continue
        rec = json.loads(gen_path.read_text())
        if rec["prompt_id"] not in valid_ids:  # stale files from earlier prompt sets
            continue
        mdir, stem = gen_path.parent.name, gen_path.stem
        row = {
            "model": rec["model"],
            "prompt_id": rec["prompt_id"],
            "ring": rec["ring"],
            "animal": rec["animal"],
            "vehicle": rec["vehicle"],
            "sample": rec["sample"],
            "has_svg": rec["svg"] is not None,
            "rendered": (RENDERS_DIR / mdir / f"{stem}.png").exists(),
            "attempts": rec.get("attempts", 1) + (1 if f"{mdir}/{stem}.json" in prior_failures else 0),
        }
        feat_path = FEATURES_DIR / mdir / f"{stem}.json"
        if feat_path.exists():
            feats = json.loads(feat_path.read_text())
            for k in FEATURE_KEYS:
                row[f"feat_{k}"] = feats.get(k)
        per_judge = []
        ratings: dict[str, list] = {}
        for judge in JUDGE_MODELS:
            score_path = SCORES_DIR / model_slug(judge) / mdir / f"{stem}.json"
            if score_path.exists():
                scores = json.loads(score_path.read_text())
                judge_ratings = []
                for k, v in scores.items():
                    if k.endswith("_rating") and v is not None:
                        row[f"{k}__{model_slug(judge)}"] = v
                        ratings.setdefault(k, []).append(v)
                        judge_ratings.append(v)
                if judge_ratings:
                    per_judge.append(sum(judge_ratings) / len(judge_ratings))
        for k, vals in ratings.items():
            row[k] = sum(vals) / len(vals)
        row["overall"] = sum(per_judge) / len(per_judge) if per_judge else None
        rows.append(row)
    return pd.DataFrame(rows)


def animal_scores(df: pd.DataFrame) -> pd.Series:
    return df.dropna(subset=["overall"]).groupby("animal")["overall"].mean().sort_values(ascending=False)


def vehicle_scores(df: pd.DataFrame) -> pd.Series:
    if "vehicle_rating" not in df.columns:
        return pd.Series(dtype=float)
    return df.dropna(subset=["vehicle_rating"]).groupby("vehicle")["vehicle_rating"].mean().sort_values(ascending=False)


def interaction_residual(df: pd.DataFrame) -> pd.DataFrame:
    """Pelican-bicycle score minus (row mean + column mean - grand mean), per model."""
    grid = df.dropna(subset=["overall"])
    out = []
    for model, g in grid.groupby("model"):
        cells = g.groupby(["animal", "vehicle"])["overall"].mean().unstack()
        if "bicycle" not in cells.columns or "pelican" not in cells.index:
            continue
        expected = cells.loc["pelican"].mean() + cells["bicycle"].mean() - cells.values.mean()
        out.append(
            {
                "model": model,
                "pelican_bicycle": cells.loc["pelican", "bicycle"],
                "expected": expected,
                "residual": cells.loc["pelican", "bicycle"] - expected,
            }
        )
    return pd.DataFrame(out).sort_values("residual", ascending=False)


def facing_distribution(df: pd.DataFrame) -> pd.DataFrame:
    g = df[df["feat_facing"].notna()]
    table = g.groupby("model")["feat_facing"].value_counts(normalize=True).unstack(fill_value=0)
    table.loc["ALL MODELS"] = g["feat_facing"].value_counts(normalize=True)
    return table


def element_counts(df: pd.DataFrame, top: int = 25) -> pd.DataFrame:
    """How often each scene element appears (share of images containing it)."""
    lists = [e for e in df["feat_elements"] if isinstance(e, list)]
    counts = Counter(x for e in lists for x in set(x.strip().lower() for x in e))
    table = pd.DataFrame(counts.most_common(top), columns=["element", "images"])
    table["share"] = table["images"] / len(lists)
    return table


def pelican_bicycle_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Fingerprint check: does the pelican-bicycle cell look different from
    everything else — per model (to catch a single lab) and pooled?"""
    is_pb = (df["animal"] == "pelican") & (df["vehicle"] == "bicycle")

    print("\n--- Facing: pelican-bicycle samples vs the model's other images ---")
    rows = []
    for model, g in df.groupby("model"):
        pb_facings = g.loc[is_pb.reindex(g.index, fill_value=False), "feat_facing"].dropna().tolist()
        others = g.loc[~is_pb.reindex(g.index, fill_value=False), "feat_facing"].dropna()
        rows.append(
            {
                "model": model,
                "pelican_bicycle_facing": ", ".join(pb_facings) or "-",
                "right_share_elsewhere": round((others == "right").mean(), 2),
            }
        )
    print(pd.DataFrame(rows).to_string(index=False))

    def element_shares(sub: pd.DataFrame) -> tuple[dict, int]:
        sets = [set(e) for e in sub["feat_elements"] if isinstance(e, list)]
        counts = Counter(x for s in sets for x in s)
        return {k: v / len(sets) for k, v in counts.items()}, len(sets)

    pb_shares, n_pb = element_shares(df[is_pb])
    rest_shares, _ = element_shares(df[~is_pb])
    lift = pd.DataFrame(
        [
            {
                "element": k,
                "pelican_bicycle": v,
                "other_cells": rest_shares.get(k, 0.0),
                "diff": v - rest_shares.get(k, 0.0),
            }
            for k, v in pb_shares.items()
        ]
    ).sort_values("diff", ascending=False)
    print(f"\n--- Elements over/under-represented in pelican-bicycle (n={n_pb} images) ---")
    with_baseline = lift[(lift["pelican_bicycle"] >= 0.2) | (lift["other_cells"] >= 0.2)]
    print((with_baseline.set_index("element") * 100).round(0).astype(int).to_string())

    print("\n--- Per model: elements in >=2 of its pelican-bicycle samples ---")
    for model, g in df[is_pb].groupby("model"):
        sets = [set(e) for e in g["feat_elements"] if isinstance(e, list)]
        counts = Counter(x for s in sets for x in s)
        common = sorted(k for k, c in counts.items() if c >= 2)
        print(f"{model}: {', '.join(common) or '-'}")
    return lift


def per_lab_favoritism(df: pd.DataFrame) -> pd.DataFrame:
    """Per model: pelican vs other animals (animal_rating) and bicycle vs
    other vehicles (vehicle_rating). A single lab training on the benchmark
    would show a positive gap on both."""
    rows = []
    for model, g in df.groupby("model"):
        ar = g.dropna(subset=["animal_rating"]) if "animal_rating" in g else g.iloc[0:0]
        vr = g.dropna(subset=["vehicle_rating"]) if "vehicle_rating" in g else g.iloc[0:0]
        pelican = ar.loc[ar["animal"] == "pelican", "animal_rating"].mean()
        other_animals = ar.loc[ar["animal"] != "pelican", "animal_rating"].mean()
        bicycle = vr.loc[vr["vehicle"] == "bicycle", "vehicle_rating"].mean()
        other_vehicles = vr.loc[vr["vehicle"] != "bicycle", "vehicle_rating"].mean()
        rows.append(
            {
                "model": model,
                "pelican": pelican,
                "other_animals": other_animals,
                "pelican_gap": pelican - other_animals,
                "bicycle": bicycle,
                "other_vehicles": other_vehicles,
                "bicycle_gap": bicycle - other_vehicles,
            }
        )
    return pd.DataFrame(rows).sort_values("pelican_gap", ascending=False)


def difficulty_adjusted_effects(df: pd.DataFrame) -> pd.DataFrame:
    """Two-way fixed-effects regressions: rating ~ lab + animal + vehicle,
    plus per-lab interactions for pelican, bicycle, and the pelican-bicycle
    cell. Animal/vehicle terms absorb intrinsic complexity; the interactions
    are each lab's benchmark-specific boost relative to the average lab, with
    95% CIs. Sum coding so deviations are vs the panel mean, not one lab.

    Fit on the raw images, one row per generation: the samples within a cell
    are independent draws at temperature 1.0 from the same prompt, and each
    per-lab pelican-bicycle term needs more than the single observation that
    cell means would leave it. HC3 robust SEs because the 1-5 judge scale has
    a hard ceiling, so within-cell spread shrinks as cells approach 5."""
    import statsmodels.formula.api as smf

    data = df.dropna(subset=["overall"]).copy()
    data["is_pelican"] = (data["animal"] == "pelican").astype(int)
    data["is_bicycle"] = (data["vehicle"] == "bicycle").astype(int)
    data["is_pb"] = data["is_pelican"] * data["is_bicycle"]
    fit = smf.ols(
        "overall ~ C(model, Sum) + C(animal) + C(vehicle) + is_pb"
        " + C(model, Sum):is_pelican + C(model, Sum):is_bicycle + C(model, Sum):is_pb",
        data=data,
    ).fit(cov_type="HC3")

    rows = []
    ci = fit.conf_int()
    for term in fit.params.index:
        if ":is_" not in term and term != "is_pb":
            continue
        if "[mean" in term:  # collinear with the animal/vehicle difficulty terms
            continue
        label = term.replace("C(model, Sum)[S.", "").replace("]", "")
        rows.append(
            {
                "term": label if term != "is_pb" else "pelican-bicycle cell (avg lab)",
                "coef": fit.params[term],
                "ci_low": ci.loc[term, 0],
                "ci_high": ci.loc[term, 1],
                "p": fit.pvalues[term],
            }
        )

    # Sum coding omits one model; derive its effects (= -sum of the others)
    # with covariance-based CIs so the table covers every lab.
    import numpy as np
    from scipy import stats

    all_models = sorted(data["model"].unique())
    for kind in ["is_pelican", "is_bicycle", "is_pb"]:
        idx = [t for t in fit.params.index if t.endswith(":" + kind) and "[mean" not in t]
        labeled = {t.split("[S.")[1].split("]")[0] for t in idx}
        omitted = [m for m in all_models if m not in labeled]
        if len(omitted) != 1:
            continue
        coef = -fit.params[idx].sum()
        cov = fit.cov_params().loc[idx, idx].values
        se = float(np.sqrt(np.ones(len(idx)) @ cov @ np.ones(len(idx))))
        rows.append(
            {
                "term": f"{omitted[0]}:{kind}",
                "coef": coef,
                "ci_low": coef - 1.96 * se,
                "ci_high": coef + 1.96 * se,
                "p": 2 * stats.norm.sf(abs(coef / se)),
            }
        )
    return pd.DataFrame(rows)


def modal_share(values: list) -> float | None:
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return None
    return Counter(values).most_common(1)[0][1] / len(values)


def cross_lab_convergence(df: pd.DataFrame) -> pd.DataFrame:
    """Per grid cell: do different labs draw the same picture? Combines facing
    agreement with element-set overlap (mean pairwise Jaccard). High values in
    exactly the pelican-bicycle cell = labs drawing from the same well."""
    out = []
    for (animal, vehicle), g in df.groupby(["animal", "vehicle"]):
        modal_facings, elem_sets = [], []
        for _, mg in g.groupby("model"):
            facings = [f for f in mg["feat_facing"] if f in ("left", "right")]
            if facings:
                modal_facings.append(Counter(facings).most_common(1)[0][0])
            sets = [set(e) for e in mg["feat_elements"] if isinstance(e, list)]
            if sets:
                counts = Counter(x for s in sets for x in s)
                elem_sets.append({x for x, c in counts.items() if c >= len(sets) / 2})
        parts = []
        facing_share = modal_share(modal_facings)
        if facing_share is not None:
            parts.append(facing_share)
        jaccards = [
            len(a & b) / len(a | b)
            for i, a in enumerate(elem_sets)
            for b in elem_sets[i + 1 :]
            if a | b
        ]
        if jaccards:
            parts.append(sum(jaccards) / len(jaccards))
        if parts:
            out.append({"animal": animal, "vehicle": vehicle, "convergence": sum(parts) / len(parts)})
    return pd.DataFrame(out)


def export_widget_scores(df: pd.DataFrame) -> None:
    """Compact per-image scores for the blog's image-browser widget, written
    next to the renders so the same S3 sync uploads it."""
    out: dict = {}
    for _, r in df.iterrows():
        if pd.isna(r.get("overall")):
            continue
        slug = model_slug(r["model"])
        samples = out.setdefault(slug, {}).setdefault(r["prompt_id"], {})
        samples[str(r["sample"])] = {
            "o": round(r["overall"], 1),
            "a": r.get("animal_rating"),
            "v": r.get("vehicle_rating"),
            "c": r.get("action_rating"),
        }
    (RENDERS_DIR / "scores.json").write_text(json.dumps(out))


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_dataset()
    df.to_csv(ANALYSIS_DIR / "dataset.csv", index=False)
    export_widget_scores(df)

    print("=== Generation reliability (attempts to get a renderable SVG) ===")
    reliability = df.groupby("model").agg(
        images=("attempts", "size"),
        total_retries=("attempts", lambda s: int((s - 1).sum())),
        max_attempts=("attempts", "max"),
        rendered=("rendered", "mean"),
    )
    print(reliability.round(3).to_string())
    reliability.to_csv(ANALYSIS_DIR / "reliability.csv")

    print("\n=== Mean judge score by animal ===")
    a_scores = animal_scores(df)
    print(a_scores.round(2).to_string())
    a_scores.to_csv(ANALYSIS_DIR / "animal_scores.csv")

    print("\n=== Mean vehicle rating by vehicle ===")
    v_scores = vehicle_scores(df)
    print(v_scores.round(2).to_string())
    v_scores.to_csv(ANALYSIS_DIR / "vehicle_scores.csv")

    print("\n=== Pelican-bicycle interaction residual ===")
    res = interaction_residual(df)
    print(res.round(3).to_string(index=False))
    res.to_csv(ANALYSIS_DIR / "interaction_residual.csv", index=False)

    print("\n=== Facing direction (share of images) ===")
    facing = facing_distribution(df)
    print((facing * 100).round(1).to_string())
    facing.to_csv(ANALYSIS_DIR / "facing_distribution.csv")

    print("\n=== Most common scene elements ===")
    elements = element_counts(df)
    print(elements.assign(share=(elements["share"] * 100).round(1)).to_string(index=False))
    elements.to_csv(ANALYSIS_DIR / "element_counts.csv", index=False)

    print("\n=== Per-lab favoritism: pelican vs other animals, bicycle vs other vehicles ===")
    fav = per_lab_favoritism(df)
    print(fav.round(2).to_string(index=False))
    fav.to_csv(ANALYSIS_DIR / "per_lab_favoritism.csv", index=False)

    print("\n=== Difficulty-adjusted per-lab effects (fixed-effects OLS, 95% CI) ===")
    adj = difficulty_adjusted_effects(df)
    print(adj.round(3).to_string(index=False))
    adj.to_csv(ANALYSIS_DIR / "difficulty_adjusted_effects.csv", index=False)

    print("\n=== Pelican-bicycle fingerprint vs everything else ===")
    lift = pelican_bicycle_profile(df)
    lift.to_csv(ANALYSIS_DIR / "pelican_bicycle_elements.csv", index=False)

    print("\n=== Cross-lab convergence by cell ===")
    conv = cross_lab_convergence(df)
    print(conv.pivot(index="animal", columns="vehicle", values="convergence").round(2).to_string())
    conv.to_csv(ANALYSIS_DIR / "convergence.csv", index=False)
    fig = px.imshow(
        conv.pivot(index="animal", columns="vehicle", values="convergence"),
        text_auto=".2f",
        title="Cross-lab compositional convergence (facing + shared elements)",
    )
    fig.write_html(ANALYSIS_DIR / "convergence_heatmap.html")

    print(f"\nCSVs and figures written to {ANALYSIS_DIR}")


if __name__ == "__main__":
    main()
