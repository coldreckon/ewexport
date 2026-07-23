#!/usr/bin/env python3
"""
Generate assets/ewexport.ico for the Windows executable.

This produces a simple, self-contained lettermark ("EW") icon so the signed
release ships with a real icon instead of PyInstaller's default. Replace
``ewexport.ico`` with your own artwork any time -- or drop a PNG next to this
script named ``ewexport_source.png`` (>=256x256) and this script will convert
that instead of drawing the lettermark.

Run:  python assets/generate_icon.py

Only dependency is Pillow, which is already a project dependency.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
OUT = HERE / "ewexport.ico"
SOURCE_PNG = HERE / "ewexport_source.png"

# Icon sizes embedded in the .ico (Windows picks the best for each context).
SIZES = [16, 24, 32, 48, 64, 128, 256]

# Brand colours for the generated lettermark.
BG_TOP = (37, 99, 235)      # blue-600
BG_BOTTOM = (109, 40, 217)  # violet-700
FG = (255, 255, 255)        # white letters


def _load_bold_font(px: int) -> ImageFont.FreeTypeFont:
    """Load a bold TrueType font, trying a few common Windows/Linux faces."""
    candidates = [
        "arialbd.ttf", "seguisb.ttf", "segoeuib.ttf",  # Windows
        "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",  # Linux CI
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def _rounded_gradient(size: int) -> Image.Image:
    """Draw a vertical-gradient rounded square with an 'EW' lettermark."""
    # Supersample for smooth edges, then downscale.
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Vertical gradient background.
    grad = Image.new("RGBA", (s, s))
    for y in range(s):
        t = y / (s - 1)
        r = round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        for x in range(s):
            grad.putpixel((x, y), (r, g, b, 255))

    # Rounded-square mask.
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=255
    )
    img.paste(grad, (0, 0), mask)

    # Lettermark.
    draw = ImageDraw.Draw(img)
    text = "EW"
    font = _load_bold_font(int(s * 0.46))
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.text(
        ((s - tw) / 2 - box[0], (s - th) / 2 - box[1]),
        text, font=font, fill=FG,
    )

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    if SOURCE_PNG.exists():
        print(f"Using source image: {SOURCE_PNG}")
        base = Image.open(SOURCE_PNG).convert("RGBA")
        frames = [base.resize((n, n), Image.LANCZOS) for n in SIZES]
    else:
        print("No source PNG found; drawing the built-in 'EW' lettermark.")
        frames = [_rounded_gradient(n) for n in SIZES]

    # Pillow writes a multi-resolution .ico from the largest frame + sizes list.
    frames[-1].save(OUT, format="ICO", sizes=[(n, n) for n in SIZES])
    print(f"Wrote {OUT} with sizes {SIZES}")


if __name__ == "__main__":
    main()
