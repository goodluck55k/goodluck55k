"""Native SVG strokes and font outlines, without fonts, CSS or external images.

Small character artwork is copied from the provided bitmap as pixel runs.
It is not traced or regenerated. Charts and typography remain real vectors.
"""
from collections import defaultdict
from functools import lru_cache
from html import escape
import math
import random
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageColor
from common import ROOT


@lru_cache(maxsize=4)
def font_source(kind):
    name = {"regular": "LibreBaskerville.ttf", "italic": "LibreBaskerville-Italic.ttf",
            "chinese": "NotoSerifSC.ttf", "handwritten": "Caveat.ttf"}[kind]
    source = TTFont(ROOT / "assets/fonts" / name)
    if kind == "handwritten":
        # Match Pillow's Medium 500 instance; no variable font is sent to GitHub.
        source = instantiateVariableFont(source, {"wght": 500}, inplace=True)
    return source.getGlyphSet(), source.getBestCmap(), source["head"].unitsPerEm


@lru_cache(maxsize=1800)
def glyph(kind, character):
    glyphs, cmap, units = font_source(kind)
    name = cmap.get(ord(character), ".notdef")
    path = SVGPathPen(glyphs)
    glyphs[name].draw(path)
    bounds = BoundsPen(glyphs)
    glyphs[name].draw(bounds)
    return path.getCommands(), bounds.bounds, units


def monotone_curve(points):
    """Fritsch–Carlson cubic: interpolate exact points, no invented peaks."""
    if len(points) < 2:
        return "", list(points)
    x, y = zip(*points)
    differences = [(y[i + 1] - y[i]) / (x[i + 1] - x[i]) for i in range(len(points) - 1)]
    slopes = [differences[0]] + [0 if differences[i - 1] * differences[i] <= 0 else (differences[i - 1] + differences[i]) / 2 for i in range(1, len(points) - 1)] + [differences[-1]]
    for i, difference in enumerate(differences):
        if difference == 0:
            slopes[i] = slopes[i + 1] = 0
        else:
            a, b = slopes[i] / difference, slopes[i + 1] / difference
            norm = math.hypot(a, b)
            if norm > 3:
                slopes[i], slopes[i + 1] = 3 * a / norm * difference, 3 * b / norm * difference
    commands = [f"M{x[0]:.3f} {y[0]:.3f}"]
    samples = []
    for i in range(len(points) - 1):
        h = x[i + 1] - x[i]
        commands.append(f"C{x[i]+h/3:.3f} {y[i]+slopes[i]*h/3:.3f} {x[i+1]-h/3:.3f} {y[i+1]-slopes[i+1]*h/3:.3f} {x[i+1]:.3f} {y[i+1]:.3f}")
        for j in range(8):
            t = j / 8
            yy = (2*t**3-3*t**2+1)*y[i]+(t**3-2*t**2+t)*h*slopes[i]+(-2*t**3+3*t**2)*y[i+1]+(t**3-t**2)*h*slopes[i+1]
            samples.append((x[i] + t * h, yy))
    samples.append(points[-1])
    return "".join(commands), samples


class SvgDocument:
    def __init__(self, width, height, theme, label):
        self.width, self.height, self.theme, self.label = width, height, theme, label
        self.definitions, self.parts = {}, []
        rng = random.Random(550)
        fibres = []
        for _ in range(24):
            x, y = rng.uniform(0, 151), rng.uniform(0, 139)
            fibres.append(f'<path d="M{x:.2f} {y:.2f}l{rng.uniform(1,4):.2f} .4"/>')
        self.paper = f'<pattern id="paper" width="151" height="139" patternUnits="userSpaceOnUse"><g fill="none" stroke="{theme["ink"]}" stroke-width=".45" opacity=".045">{"".join(fibres)}</g></pattern>'

    def text(self, x, y, text, size, color, kind, pillow_font, scale):
        values = [glyph(kind, ch) for ch in text]
        units = values[0][2] if values else 1000
        peak = max((bounds[3] for _, bounds, _ in values if bounds), default=0)
        baseline = y + peak * size / units
        uses = []
        for i, (character, (path, bounds, _)) in enumerate(zip(text, values)):
            if not path:
                continue
            identifier = f"g-{kind}-{ord(character):x}"
            self.definitions[identifier] = path
            position = x + pillow_font.getlength(text[:i]) / scale
            uses.append(f'<use href="#{identifier}" transform="translate({position:.3f} {baseline:.3f}) scale({size/units:.7f} {-size/units:.7f})"/>')
        self.parts.append(f'<g fill="{color}" aria-label="{escape(text, quote=True)}"><title>{escape(text)}</title>{"".join(uses)}</g>')

    def line(self, x1, y1, x2, y2, color, width=1, opacity=1):
        self.parts.append(f'<path d="M{x1:.3f} {y1:.3f}L{x2:.3f} {y2:.3f}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" opacity="{opacity}"/>')

    def path(self, path, color, width=1.5, opacity=1):
        self.parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"/>')

    def circle(self, x, y, radius, color):
        self.parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{radius}" fill="{color}"/>')

    def bitmap(self, bitmap, x, y, width, height, label):
        # Copy source pixels at the small decoration's native display resolution.
        bitmap = bitmap.resize((round(width*2), round(height*2)), Image.Resampling.LANCZOS).convert("RGBA")
        pixels = bitmap.load()
        background = ImageColor.getrgb(self.theme["bg"])
        paths = defaultdict(list)
        for yy in range(bitmap.height):
            xx = 0
            while xx < bitmap.width:
                red, green, blue, alpha = pixels[xx, yy]
                if alpha == 0:
                    xx += 1
                    continue
                end = xx + 1
                while end < bitmap.width and pixels[end, yy] == pixels[xx, yy]:
                    end += 1
                color = tuple(round(channel * alpha/255 + bg * (1-alpha/255)) for channel, bg in zip((red, green, blue), background))
                key = "#" + "".join(f"{value:02x}" for value in color)
                paths[key].append(f"M{xx} {yy}h{end-xx}v1h-{end-xx}z")
                xx = end
        content = "".join(f'<path fill="{color}" d="{"".join(commands)}"/>' for color, commands in sorted(paths.items()))
        self.parts.append(f'<g shape-rendering="crispEdges" transform="translate({x:.3f} {y:.3f}) scale({width/bitmap.width:.6f} {height/bitmap.height:.6f})" aria-label="{escape(label)}"><title>{escape(label)}</title>{content}</g>')

    def xml(self):
        definitions = "".join(f'<path id="{key}" d="{value}"/>' for key, value in sorted(self.definitions.items()))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" role="img" aria-label="{escape(self.label)}">'
                f'<title>{escape(self.label)}</title><desc>Native vector charts with open-font outlines. Character pixel artwork is derived from the user-provided original. No external image, font or script dependencies.</desc>'
                f'<defs>{self.paper}{definitions}</defs><rect width="100%" height="100%" fill="{self.theme["bg"]}"/><rect width="100%" height="100%" fill="url(#paper)"/>{"".join(self.parts)}</svg>\n')
