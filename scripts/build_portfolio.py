#!/usr/bin/env python3
"""Génère portfolio/jour|nuit/*.webp depuis photos/jour|nuit et portfolio/manifest.json (tri par teinte)."""
from __future__ import annotations

import colorsys
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC_JOUR = ROOT / "photos" / "jour"
SRC_NUIT = ROOT / "photos" / "nuit"
OUT = ROOT / "portfolio"
MAX_EDGE = 1600
WEBP_Q = 82
EXT = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".JPG", ".JPEG", ".PNG", ".TIF", ".TIFF",
}


def rgb_to_hue(r: float, g: float, b: float) -> float:
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx == mn:
        return 0.0
    d = mx - mn
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h *= 60
    if h < 0:
        h += 360
    return h


def avg_hue_accent_sort(im_rgb: Image.Image) -> tuple[float, str, float]:
    """Retourne (teinte affichage, accent CSS, clé de tri pour dégradé)."""
    w, h = im_rgb.size
    pix = im_rgb.load()
    sr = sg = sb = n = 0
    step = max(1, max(w, h) // 48)
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = pix[x, y][:3]
            sr += r
            sg += g
            sb += b
            n += 1
    if not n:
        return 0.0, "hsl(200,35%,35%)", 500.0
    r, g, b = sr / n, sg / n, sb / n
    mx = max(r, g, b) / 255.0
    mn = min(r, g, b) / 255.0
    chroma = mx - mn
    lum = (r + g + b) / (3.0 * 255.0)
    hue = rgb_to_hue(r, g, b)
    if chroma < 0.04:
        # Peu saturé : ordre par luminance après le spectre (360–720).
        sort_key = 360.0 + lum * 360.0
        disp_hue = lum * 360.0
    else:
        sort_key = hue
        disp_hue = hue
    return disp_hue, f"hsl({disp_hue:.0f},40%,42%)", sort_key


def safe_slug(name: str) -> str:
    base = Path(name).stem
    s = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return s or "photo"


def hue_to_rgb_bg(h: float, sat: float = 0.22, light: float = 0.14) -> str:
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, sat, light)
    return f"rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})"


def process_folder(src: Path, out_sub: str, used: set[str]) -> list[dict]:
    items: list[dict] = []
    if not src.is_dir():
        return items
    out_dir = OUT / out_sub
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.webp"):
        old.unlink()

    files = sorted(f for f in src.iterdir() if f.is_file() and f.suffix in EXT)
    for f in files:
        slug_base = safe_slug(f.name)
        slug = slug_base
        i = 1
        while slug in used:
            i += 1
            slug = f"{slug_base}-{i}"
        used.add(slug)
        out_path = out_dir / f"{slug}.webp"
        try:
            im = Image.open(f)
            im = im.convert("RGB")
        except Exception as e:
            print(f"skip {f.name}: {e}", file=sys.stderr)
            continue
        small = im.copy()
        small.thumbnail((220, 220))
        hue, accent, sort_key = avg_hue_accent_sort(small)
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        try:
            im.save(out_path, "WEBP", quality=WEBP_Q, method=6)
        except Exception as e:
            print(f"webp {f.name}: {e}", file=sys.stderr)
            continue
        rel = f"portfolio/{out_sub}/{slug}.webp"
        items.append({
            "src": rel,
            "hue": round(hue, 2),
            "accent": accent,
            "_sort": sort_key,
        })

    items.sort(key=lambda x: (x["_sort"], x["src"]))
    for it in items:
        del it["_sort"]
    return items


def gradient_pair(items: list[dict]) -> tuple[str, str]:
    if len(items) < 2:
        return ("rgb(8,18,32)", "rgb(18,12,28)")
    return hue_to_rgb_bg(items[0]["hue"]), hue_to_rgb_bg(items[-1]["hue"])


def main() -> None:
    jour = process_folder(SRC_JOUR, "jour", set())
    nuit = process_folder(SRC_NUIT, "nuit", set())
    manifest = {
        "jour": {
            "items": jour,
            "gradient": gradient_pair(jour),
        },
        "nuit": {
            "items": nuit,
            "gradient": gradient_pair(nuit),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    man_path = OUT / "manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"jour: {len(jour)} webp, nuit: {len(nuit)} webp -> {man_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
