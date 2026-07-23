"""Generate social media preview cards (1200x630 PNG) for blog posts.

For every post in posts/ that has a title but no `image:` in its frontmatter,
render a branded title card to posts/images/cards/<slug>.png and add the
`image:` entry to the post's frontmatter.

Usage (from repo root):
    uv run python _extras/social_cards/generate_cards.py            # all posts
    uv run python _extras/social_cards/generate_cards.py --only pelicanmaxxing
    uv run python _extras/social_cards/generate_cards.py --force    # re-render existing cards
    uv run python _extras/social_cards/generate_cards.py --no-patch # render only, don't touch posts
"""

import argparse
import json
import re
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
POSTS_DIR = ROOT / "posts"
CARDS_DIR = POSTS_DIR / "images" / "cards"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"

WIDTH, HEIGHT = 1200, 630
MARGIN_X = 80
BG = (24, 24, 27)  # $gray-900, site background
DOT = (39, 39, 42)  # $gray-800
ORANGE = (235, 132, 27)  # $orange, site accent
WHITE = (255, 255, 255)
GRAY = (161, 161, 170)  # $gray-400

TITLE_FONT = FONTS_DIR / "Lato-Black.ttf"
FOOTER_FONT = FONTS_DIR / "Lato-Bold.ttf"


def balanced_wrap(draw, words, font, n_lines, max_width):
    """Split words into n_lines minimizing the widest line; None if impossible."""
    from itertools import combinations

    if n_lines > len(words):
        return None
    best, best_width = None, None
    for breaks in combinations(range(1, len(words)), n_lines - 1):
        bounds = [0, *breaks, len(words)]
        lines = [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]
        width = max(draw.textlength(l, font=font) for l in lines)
        if width <= max_width and (best_width is None or width < best_width):
            best, best_width = lines, width
    return best


def fit_title(draw, title, max_width):
    """Pick the layout (line count + size) that best fills the card.

    Fewer lines are preferred: each extra line costs 10%, so a title that
    fits on one line at a slightly smaller size beats an awkward wrap.
    """
    words = title.split()
    best = None
    for n_lines in (1, 2, 3):
        for size in range(96, 44, -2):
            if n_lines * size * 1.22 > 340:
                continue
            font = ImageFont.truetype(str(TITLE_FONT), size)
            lines = balanced_wrap(draw, words, font, n_lines, max_width)
            if lines:
                score = size * 0.9 ** (n_lines - 1)
                if best is None or score > best[0]:
                    best = (score, font, lines, size)
                break
    if best:
        return best[1], best[2], best[3]
    font = ImageFont.truetype(str(TITLE_FONT), 44)
    return font, balanced_wrap(draw, words, font, 3, max_width * 1.5) or [title], 44


def render_card(title, out_path):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Subtle dot grid in the top-right quadrant
    for x in range(720, WIDTH - 40, 44):
        for y in range(56, 300, 44):
            draw.ellipse((x, y, x + 5, y + 5), fill=DOT)

    font, lines, size = fit_title(draw, title, WIDTH - 2 * MARGIN_X)
    line_height = int(size * 1.22)
    block_height = len(lines) * line_height

    # Accent strip along the top edge
    draw.rectangle((0, 0, WIDTH, 8), fill=ORANGE)

    # Title, vertically centered in the space above the footer
    y = (HEIGHT - 130 - block_height) // 2 + 20
    for line in lines:
        draw.text((MARGIN_X, y), line, font=font, fill=WHITE)
        y += line_height

    # Footer: domain
    footer_y = HEIGHT - 92
    footer_font = ImageFont.truetype(str(FOOTER_FONT), 30)
    draw.text((MARGIN_X, footer_y), "dylancastillo.co", font=footer_font, fill=GRAY)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


def render_site_card(out_path):
    """Render the site-wide fallback card (used by homepage, about, TIL, etc.)."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    for x in range(720, WIDTH - 40, 44):
        for y in range(56, 300, 44):
            draw.ellipse((x, y, x + 5, y + 5), fill=DOT)
    draw.rectangle((0, 0, WIDTH, 8), fill=ORANGE)

    name_font = ImageFont.truetype(str(TITLE_FONT), 84)
    sub_font = ImageFont.truetype(str(FONTS_DIR / "Lato-Regular.ttf"), 36)
    top = (HEIGHT - 130 - 84 - 24 - 36) // 2 + 20
    draw.text((MARGIN_X, top), "Dylan Castillo", font=name_font, fill=WHITE)
    draw.text(
        (MARGIN_X, top + 84 + 24),
        "AI Consultant | Serial tinkerer",
        font=sub_font,
        fill=GRAY,
    )

    footer_font = ImageFont.truetype(str(FOOTER_FONT), 30)
    draw.text((MARGIN_X, HEIGHT - 92), "dylancastillo.co", font=footer_font, fill=GRAY)
    img.save(out_path, "PNG", optimize=True)


def read_frontmatter(path):
    """Return (frontmatter_dict, raw_yaml_text) or (None, None)."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text())
        for cell in nb.get("cells", []):
            if cell.get("cell_type") in ("raw", "markdown"):
                src = "".join(cell.get("source", []))
                m = re.match(r"\s*---\n(.*?)\n---", src, re.DOTALL)
                if m:
                    return yaml.safe_load(m.group(1)), m.group(1)
        return None, None
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None, None
    return yaml.safe_load(m.group(1)), m.group(1)


def patch_frontmatter(path, image_rel):
    """Insert `image: <image_rel>` after the title line in the frontmatter."""
    line = f'image: "{image_rel}"'

    def insert(yaml_text):
        out, done = [], False
        for ln in yaml_text.split("\n"):
            out.append(ln)
            if not done and re.match(r"title\s*:", ln):
                out.append(line)
                done = True
        return "\n".join(out), done

    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text())
        for cell in nb.get("cells", []):
            if cell.get("cell_type") in ("raw", "markdown"):
                src = "".join(cell.get("source", []))
                m = re.match(r"(\s*---\n)(.*?)(\n---)", src, re.DOTALL)
                if m:
                    patched, done = insert(m.group(2))
                    if not done:
                        return False
                    new_src = src[: m.start(2)] + patched + src[m.end(2) :]
                    cell["source"] = new_src.splitlines(keepends=True)
                    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
                    return True
        return False

    text = path.read_text()
    m = re.match(r"(---\n)(.*?)(\n---)", text, re.DOTALL)
    patched, done = insert(m.group(2))
    if not done:
        return False
    path.write_text(text[: m.start(2)] + patched + text[m.end(2) :])
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="only process the post with this filename stem")
    parser.add_argument("--force", action="store_true", help="re-render existing cards")
    parser.add_argument("--no-patch", action="store_true", help="don't edit frontmatter")
    parser.add_argument(
        "--site-card", action="store_true", help="render the site-wide fallback card"
    )
    args = parser.parse_args()

    if args.site_card:
        out = ROOT / "images" / "social_media_card.png"
        render_site_card(out)
        print(f"rendered:            {out.relative_to(ROOT)}")
        return

    posts = sorted(
        p
        for p in POSTS_DIR.iterdir()
        if p.suffix in {".qmd", ".md", ".ipynb"} and not p.name.startswith("_")
    )
    for post in posts:
        if args.only and post.stem != args.only:
            continue
        meta, _ = read_frontmatter(post)
        if not meta or not meta.get("title"):
            print(f"skip (no title):     {post.name}")
            continue
        image = meta.get("image")
        if image and "images/cards/" not in str(image):
            print(f"skip (custom image): {post.name}")
            continue

        card = CARDS_DIR / f"{post.stem}.png"
        if not card.exists() or args.force:
            render_card(str(meta["title"]), card)
            print(f"rendered:            {card.relative_to(ROOT)}")
        if not image and not args.no_patch:
            if patch_frontmatter(post, f"images/cards/{post.stem}.png"):
                print(f"patched frontmatter: {post.name}")
            else:
                print(f"PATCH FAILED:        {post.name}")


if __name__ == "__main__":
    main()
