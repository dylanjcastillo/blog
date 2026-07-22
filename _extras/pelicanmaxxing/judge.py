"""Quality-judging pass: each judge model scores each render against its prompt.

Kept separate from extract.py so the inventory task can stay blind and the
quality task can see the prompt. Resumable per judge.

The rubric makes the judge name the defects *before* rating, once per aspect:
animal anatomy, vehicle mechanics, and the contact points between them. Each
rating is then capped at (5 - defects named in its own list). Without that,
scores pile up at 4-5: these are flat vector drawings that almost always read
correctly at a glance, so "is it recognizable?" barely discriminates, and
limbless animals and pedal-less bicycles were scoring 5.

A defect only counts when the pose and viewpoint should have shown the part —
otherwise the rubric punishes a cat for the legs its boat hull hides, and the
animal ranking ends up measuring pose rather than draughtsmanship.

The extra observation fields are ignored by analysis.py, which only reads keys
ending in `_rating`.

Usage:
    uv run python _extras/pelicanmaxxing/judge.py
"""

import asyncio
import json

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from config import GENERATIONS_DIR, JUDGE_MODELS, MAX_CONCURRENCY, RENDERS_DIR, SCORES_DIR, model_slug
from vision import make_client, vision_json_call

INSTRUCTIONS = """\
This image was generated (as SVG, then rendered) from the prompt:

  "{prompt}"

These are flat vector drawings produced by a language model. Almost all of \
them are recognizable at a glance, so "I can tell what it is" is not enough to \
earn a high score. Discriminate on execution: anatomy, part counts, \
attachment, proportion, and colour.

## Step 1 — name the defects before you score

Fill the three defect lists first. Each rating is capped by its own list, so \
name what is actually wrong before you think about numbers. A list is empty \
when you genuinely cannot fault that aspect.

**"animal_defects"** — look specifically for:

- **Missing limbs that this pose should show.** A body resting directly on a \
seat with no legs where legs would be visible, a bird with no wing in a side \
view. Easy to miss, because the silhouette still reads correctly.
- **Wrong counts** among the parts that are visible. Three legs, two tails.
- **Detached or floating parts.** A beak separated from the head, a limb that \
does not meet the body, a tail hovering beside the torso.
- **Blob anatomy.** An undifferentiated oval with features drawn on top and no \
articulated limbs, neck, or joints.
- **Wrong colour** for the species (see the list below).
- **Broken proportion.** A head half the size of the body, a neck thicker than \
the torso, legs that could not support the animal.

**"vehicle_defects"** — look for:

- **Missing parts that this view should show.** A part the vehicle needs in \
order to work, which nothing is hiding, and which simply is not drawn.
- **Wrong counts** among the parts that are visible.
- **Malformed parts.** Wheels that are not round, wildly unequal wheel \
diameters where they should match, a part whose shape could not do its job.
- **Disconnection.** Parts that do not meet where they must: a frame that does \
not reach an axle, a handlebar floating clear of the steering column, a seat \
attached to nothing.
- **Broken geometry.** An assembly that could not hold together or could not \
move as the vehicle is supposed to move.

**"action_defects"** — work out what touches what (which limb is on the \
handlebars, which foot is on a pedal or the deck, what the animal's weight \
rests on), then look for:

- **No contact.** A limb near a control but not on it, or the animal simply \
overlapping the vehicle.
- **Floating.** The animal not supported by anything, or hovering above the \
seat or deck.
- **Clipping.** The body passing through the frame, or the vehicle drawn on \
top of the animal.
- **Implausible posture.** A seated pose on a vehicle that has to be stood on, \
a rider facing the wrong way, a bird astride a bike with both legs on the same \
side.

## The visibility rule — read this before naming any defect

A part is a defect **only if this viewpoint and this pose should show it and \
it is not there**. Everything that something else legitimately hides is not a \
defect, and must not appear in any of the three lists.

Decide what the drawing is *trying* to show, then ask what would be visible if \
it had been drawn perfectly:

- A strict side view hides the far wing, the far legs, the far pedal, the far \
arm. Absent far-side parts are fine. Absent near-side parts are defects.
- A vehicle hides whatever is behind or inside it. A cat sitting in a boat \
hull, an animal whose legs are behind the frame, a body below the deck line — \
those limbs are not missing, they are out of sight.
- A front-facing or seated pose hides the tail, the far side of the body, and \
often the legs entirely. Do not penalise a pose for what the pose conceals.
- A cropped composition hides whatever falls outside the frame.

Do not count the same absence twice, and do not invent a canonical parts list \
to check off. Judge the drawing that was attempted, not the drawing you would \
have composed. When you cannot tell whether a part is hidden or missing, treat \
it as hidden.

## Step 2 — the three ratings

**"animal_rating"** — is this the requested species, drawn competently?

A complete set of correctly-counted limbs does not make it the right animal. \
Species identity comes first, from the signature features and colours listed \
below; anatomy completeness only decides the score once the species is right. \
A well-drawn bear scores low when the prompt asked for an otter.

- 5 — Unmistakably the species. Correct silhouette, signature features, \
correct colours, every limb present, correctly counted and properly attached. \
You cannot name a single defect.
- 4 — Clearly the species, exactly one nameable defect (one missing or \
malformed limb, one wrong colour, one off proportion).
- 3 — Two or more defects, or a generic animal body with species cues bolted \
on, or readable as the species mainly because the prompt says so.
- 2 — Another species drawn in its place, however well; or the species cue is \
present but the body is a limbless blob; or three or more defects.
- 1 — No coherent animal: scattered or floating parts, or nothing identifiable.

Signature features and colours to check:

- pelican — long straight beak with a large throat pouch, white/grey body, \
orange-yellow beak and pouch, webbed feet. A beak with no pouch is a heron or \
a gull, not a pelican.
- heron — thin dagger beak, S-curved neck, long thin legs, grey or blue-grey, \
no pouch.
- flamingo — pink, down-bent hooked beak, stilt legs, long S-neck.
- otter — brown, flat tapered tail, small round ears, short limbs, pale muzzle.
- raccoon — grey body, black eye mask, ringed tail, dexterous forepaws.
- antelope — tan or brown, horns, hooves, four slender legs, short tail.
- whale — grey or blue, fluke, flippers, blowhole, no legs (legs on a whale \
are a defect, not a bonus).
- cat — four legs, upright ears, whiskers, long tail, natural cat colouring.

**"vehicle_rating"** — is the vehicle mechanically complete?

Ask whether this machine could work. Every vehicle has parts it cannot do \
without — the thing it rolls or floats on, the thing the rider holds or sits \
on, the thing that drives it — but which parts those are depends on the \
vehicle, and some of them are legitimately hidden. Judge what the drawing \
shows against what it would take for the vehicle to function, not against a \
fixed list.

- 5 — Everything the machine needs and this view should show is present, \
correctly proportioned and properly connected. It could work.
- 4 — Complete, with exactly one defect: one part crude, misproportioned, or \
floating free of what it should attach to.
- 3 — Two defects, or one part the machine genuinely needs is absent with \
nothing hiding it, or the parts are drawn but not joined into a coherent \
machine.
- 2 — Several needed parts absent; a suggestion of the vehicle rather than the \
vehicle itself.
- 1 — The vehicle is absent, or is something else entirely.

Colour is not part of this rating — vehicles come in every colour. Judge \
completeness, connection, proportion and whether it could function.

**"action_rating"** — is the animal actually doing the requested thing?

Judge the contact points, not the general arrangement.

- 5 — The animal is on or astride the vehicle, its weight supported by it, and \
every relevant limb meets its correct contact point: feet on pedals or deck, \
forelimbs on the handlebars. Posture is plausible for motion.
- 4 — Correctly positioned and supported, exactly one defect: one contact point \
missing or approximate (feet near the pedals rather than on them).
- 3 — On the vehicle, but no limb engages any control, or two defects, or the \
body clips through the frame.
- 2 — Beside, behind, or overlapping the vehicle without riding it.
- 1 — No spatial relationship between the animal and the vehicle.

## Calibration

Each rating is capped by its own defect list: with one entry in \
"animal_defects" the animal_rating is at most 4, with two it is at most 3. \
Likewise "vehicle_defects" caps vehicle_rating and "action_defects" caps \
action_rating. A 5 means you could not name a single defect for that aspect.

The three lists are independent. A beautifully drawn pelican on a bicycle \
missing its pedals scores 5 / 3 / 4, not 5 / 5 / 5. A crude blob riding a \
perfect bicycle scores 2 / 5 / 4.

Do not soften a score because the drawing is charming, well composed, or has a \
nice background — a polished scene with a legless animal still scores low on \
the animal.

Judge only what is visible. A beautiful image of the wrong animal scores low.
"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "animal_defects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete anatomical defects, one short phrase each. [] if none.",
        },
        "vehicle_defects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Missing, miscounted, disconnected or malformed vehicle parts. [] if none.",
        },
        "action_defects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Missing contact, floating, clipping, implausible posture. [] if none.",
        },
        "reasoning": {"type": "string"},
        "animal_rating": {"type": "integer", "minimum": 1, "maximum": 5},
        "vehicle_rating": {"type": "integer", "minimum": 1, "maximum": 5},
        "action_rating": {"type": "integer", "minimum": 1, "maximum": 5},
    },
    "required": [
        "animal_defects",
        "vehicle_defects",
        "action_defects",
        "reasoning",
        "animal_rating",
        "vehicle_rating",
        "action_rating",
    ],
    "additionalProperties": False,
}

async def judge_one(client, sem: asyncio.Semaphore, judge: str, png_path) -> None:
    out_path = SCORES_DIR / model_slug(judge) / png_path.parent.name / f"{png_path.stem}.json"
    if out_path.exists():
        return
    gen_path = GENERATIONS_DIR / png_path.parent.name / f"{png_path.stem}.json"
    rec = json.loads(gen_path.read_text())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        scores = await vision_json_call(
            client,
            judge,
            INSTRUCTIONS.format(prompt=rec["prompt"]),
            png_path,
            schema=JUDGE_SCHEMA,
            metadata={
                "stage": "judge",
                "judge": judge,
                "ring": rec["ring"],
                "image": f"{png_path.parent.name}/{png_path.stem}",
            },
        )
    if scores is None:
        tqdm.write(f"FAILED  {model_slug(judge)} {png_path.parent.name}/{png_path.stem}")
        return
    out_path.write_text(json.dumps(scores, indent=2))


async def main() -> None:
    client = make_client()
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    pngs = sorted(RENDERS_DIR.glob("*/*.png"))
    tasks = [judge_one(client, sem, judge, p) for judge in JUDGE_MODELS for p in pngs]
    print(f"{len(pngs)} images x {len(JUDGE_MODELS)} judges = {len(tasks)} scoring calls")
    await tqdm_asyncio.gather(*tasks, desc="judge")


if __name__ == "__main__":
    asyncio.run(main())
