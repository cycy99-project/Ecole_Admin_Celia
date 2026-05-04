"""
Génère icon-192.png et icon-512.png à partir d'un dessin programmatique
similaire à icon.svg (calendrier bleu). À lancer une seule fois :

    python _make_icons.py

Les PNG produits sont commitables et utilisés par Android/iOS pour les icônes
de l'app installée.
"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).parent

PRIMARY = (37, 99, 235)        # #2563eb
PRIMARY_DARK = (29, 78, 216)   # #1d4ed8
WHITE = (255, 255, 255)
SOFT = (219, 234, 254)         # #dbeafe
DARK = (15, 23, 42)            # #0f172a


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Fond carré arrondi
    radius = int(size * 0.20)
    d.rounded_rectangle([(0, 0), (size, size)], radius=radius, fill=PRIMARY)

    # Calendrier (carte blanche)
    cal_x0 = int(size * 0.18)
    cal_y0 = int(size * 0.28)
    cal_x1 = size - cal_x0
    cal_y1 = int(size * 0.86)
    cal_radius = int(size * 0.05)
    d.rounded_rectangle([(cal_x0, cal_y0), (cal_x1, cal_y1)], radius=cal_radius, fill=WHITE)

    # Bandeau supérieur (mois)
    band_h = int(size * 0.12)
    d.rounded_rectangle([(cal_x0, cal_y0), (cal_x1, cal_y0 + band_h)], radius=cal_radius, fill=PRIMARY_DARK)

    # Anneaux du calendrier
    ring_w = int(size * 0.045)
    ring_h = int(size * 0.13)
    ring_y = cal_y0 - int(size * 0.06)
    for ring_x in [cal_x0 + int(size * 0.12), cal_x1 - int(size * 0.12) - ring_w]:
        d.rounded_rectangle(
            [(ring_x, ring_y), (ring_x + ring_w, ring_y + ring_h)],
            radius=int(size * 0.015),
            fill=DARK,
        )

    # Grille de cases (4 cols x 3 lignes)
    grid_x0 = cal_x0 + int(size * 0.06)
    grid_x1 = cal_x1 - int(size * 0.06)
    grid_y0 = cal_y0 + band_h + int(size * 0.05)
    grid_y1 = cal_y1 - int(size * 0.04)
    cols = 4
    rows = 3
    cell_pad = int(size * 0.012)
    cell_w = (grid_x1 - grid_x0 - cell_pad * (cols - 1)) / cols
    cell_h = (grid_y1 - grid_y0 - cell_pad * (rows - 1)) / rows
    cell_radius = int(size * 0.014)
    highlights = {(1, 1), (2, 2)}  # cases mises en avant

    for r in range(rows):
        for c in range(cols):
            x0 = int(grid_x0 + c * (cell_w + cell_pad))
            y0 = int(grid_y0 + r * (cell_h + cell_pad))
            x1 = int(x0 + cell_w)
            y1 = int(y0 + cell_h)
            color = PRIMARY if (r, c) in highlights else SOFT
            d.rounded_rectangle([(x0, y0), (x1, y1)], radius=cell_radius, fill=color)

    return img


for sz in (192, 512):
    out = OUT_DIR / f"icon-{sz}.png"
    make_icon(sz).save(out)
    print(f"wrote {out}")
