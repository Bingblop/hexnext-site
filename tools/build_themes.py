#!/usr/bin/env python3
"""Builds the theme gallery of the website from Hex Next pack files.

For every pack listed in tools/themes.json it reads the pack's pictures and writes a few small
WebP files to assets/themes/<id>/:

    wallpaper.webp                     the pack wallpaper
    card.webp, card-night.webp         the notification card art
    look-<key>.webp                    one sprite sheet per icon look (Multicolour, Signature
                                       colour, Accent tint): Settings, My Files, Quick panel,
                                       power menu and navigation bar art, one square tile each,
                                       drawn on the pack's card colour (no alpha: a third the size)
    parts.webp                         switches (composed from track and thumb), checkboxes,
                                       radios and the dialer buttons, light and dark mode
    dialpad.webp, dialpad-night.webp   the picture behind the Phone keypad

It then rewrites the block between "<!-- themes:begin -->" and "<!-- themes:end -->" in
index.html: the tab strip and the JSON manifest that assets/themes.js draws the panels from.

    python3 tools/build_themes.py --packs <folder with <id>.zip> --work <scratch folder>

Only pictures and display names leave a pack: no pack file, code or key is copied to the site.
The pack files are read as data. Needs Pillow (with WebP) and numpy.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import math
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

SITE = Path(__file__).resolve().parents[1]
CONFIG = SITE / "tools" / "themes.json"
OUT = SITE / "assets" / "themes"
INDEX = SITE / "index.html"
BEGIN, END = "<!-- themes:begin -->", "<!-- themes:end -->"

TILE = 96            # tile of the controls sheet, px
ATLAS_W = 720        # width of a look's sprite sheet, px
ICON_SHARE = 0.9     # how much of its tile an icon fills; the rest is the card colour around it
PARTS_COLS = 8
OWNED = re.compile(r"(wallpaper|card|card-night|keyboard|keyboard-night|dialpad|dialpad-night|parts|look-[a-z0-9]+)\.webp")
SWITCH_SPAN = 2      # a switch takes two tiles
MAX_ENTRY = 16 * 1024 * 1024
IMAGE = re.compile(r".*\.(png|jpg|jpeg|webp)$", re.I)
STAGES = {"base": 0, "first": 1, "second": 2, "third": 3}

# The parts of One UI the gallery shows as icon grids, in page order: category, label, layout.
# "list" shows the first rows with their names the way Settings and My Files do, "round" draws
# Quick panel tiles. A category a pack has beyond these is shown as a plain grid.
ICON_PARTS = [
    ("settingsicon", "Settings icons", "list", 72),
    ("myfilesicon", "My Files icons", "list", 72),
    ("qsglyph", "Quick panel glyphs", "round", 60),
    ("powermenu", "Power menu", "grid", 90),
    ("navbar", "Navigation bar", "grid", 60),
    ("appinfo", "App info buttons", "grid", 72),
]
OTHER_TILE = 72
CONTROL, DIALPAD = "control", "dialpad"
PANEL_PIECES = {"keypad_background"}
SKIP_BASES = {"icons", "mms", "msgbubble", "wabuble"}

# One UI 9 builds a switch from these drawables: (label, track, thumb) by day and by night.
SWITCHES = {
    False: [("On", "switch_track_on", "switch_thumb_on"),
            ("Off", "switch_track_off", "switch_thumb_off"),
            ("Disabled", "switch_track_disabled_on", "switch_thumb_disabled_on")],
    True: [("On", "switch_track_on", "switch_thumb_on"),
           ("Off", "switch_track_dark_off", "switch_thumb_off"),
           ("Disabled", "switch_track_disabled_on", "switch_thumb_dark_disabled_on")],
}
TRACK_W, TRACK_H, THUMB = 96, 60, 60   # One UI's own switch at 3 px per dp
WIDE_THUMB = 0.625

# Plain words for the picture names shown as captions and tooltips.
WORDS = {
    "adobe": "PDF", "excel": "spreadsheet", "word": "document", "ppt": "presentation", "etc": "other",
    "apk": "APK", "html": "HTML", "txt": "text", "zip": "ZIP", "usb": "USB", "sd": "SD", "nfc": "NFC",
    "qr": "QR", "sos": "SOS", "wifi": "Wi-Fi", "ai": "AI", "devicecare": "device care",
    "digitalwellbeing": "digital wellbeing", "homescreen": "home screen", "lockscreen": "lock screen",
    "donotdisturb": "do not disturb", "donot": "do not", "autorotate": "auto rotate", "land": "landscape",
    "port": "portrait", "colorcorrection": "colour correction", "extradim": "extra dim",
    "eyecomfortshield": "eye comfort shield", "mobilehotspot": "mobile hotspot",
    "privacydisplay": "privacy display", "soundmode": "sound mode", "cameraaccess": "camera access",
    "microphoneaccess": "microphone access", "nearbydevices": "nearby devices", "sharesos": "share SOS",
    "multicontrol": "multi control", "emergencymode": "emergency mode", "emergencysos": "emergency SOS",
    "medicalinfo": "medical info", "mobiledata": "mobile data", "poweroff": "power off",
    "safemode": "safe mode", "sysbar": "", "samsung": "", "videocall": "video call", "wificall": "Wi-Fi call",
    "bluetoothcasttile": "Bluetooth cast", "fab": "call button", "bg": "", "image": "",
}
NAMES = {
    "google": "services", "galaxy_ai": "AI features", "home_google_drive": "cloud drive",
    "home_one_drive": "cloud storage", "quick_panel_icon_ms_windows_link": "link to PC",
    "ic_quick_panel_icon_dex_mode": "desktop mode", "sec_ic_auracast_tile": "audio broadcast",
    "ic_quick_panel_icon_quick_share": "share nearby", "ic_quick_panel_icon_smart_view": "screen cast",
    "ic_qp_oho": "one-handed mode", "wfc_qp_icon": "Wi-Fi calling", "wfc_qp_icon_zvv": "Wi-Fi calling 2",
    "ic_quick_panel_icon_cmc": "calls on other devices", "quick_panel_icon_s_finder": "search",
    "dialpad_fab_bg_image": "call button", "file_type_image": "image", "home_category_image": "images",
    "quick_panel_icon": "tile", "ic_quick_panel": "quick panel",
}
PREFIXES = ("sec_ic_settings_", "sec_st_ic_", "sec_ic_", "ic_samsung_", "ic_quick_panel_icon_", "ic_quick_panel_",
            "quick_panel_icon_", "tile_icon_", "tw_ic_do_", "phone_keypad_ic_", "phone_keypad_", "file_type_",
            "home_category_", "home_", "ic_", "sec_")


def caption(resource: str) -> str:
    """A readable name for a pack picture: "sec_ic_settings_devicecare" is "Device care"."""
    name = NAMES.get(resource)
    if name is None:
        stem = resource
        for prefix in PREFIXES:
            if stem.startswith(prefix) and len(stem) > len(prefix):
                stem = stem[len(prefix):]
                break
        name = NAMES.get(stem)
    if name is None:
        words = [w for w in stem.split("_") if not w.isdigit()]
        name = " ".join(filter(None, (WORDS.get(w, w) for w in words)))
    name = name.strip() or "picture"
    return name[0].upper() + name[1:]


# --- reading a pack ---------------------------------------------------------------------------

def extract(zip_path: Path, work: Path) -> Path:
    """Copies pack.json and the pictures of [zip_path] into work/<id>/ and returns that folder."""
    target = work / zip_path.stem
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if info.is_dir() or info.file_size > MAX_ENTRY:
                continue
            if name != "pack.json" and not IMAGE.match(name):
                continue
            dest = (target / name).resolve()
            if root not in dest.parents:
                continue  # a name that points outside the folder
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(info))
    return target


class Category:
    """A layer category name split into its part, its look options and day or night."""

    def __init__(self, raw: str):
        self.raw = raw
        head, *tokens = raw.split("-")
        self.night = False
        if head.endswith("_night"):
            head, self.night = head[:-6], True
        self.options = []
        for token in tokens:
            if token.endswith("_night"):
                token, self.night = token[:-6], True
            if token == "night":
                self.night = True
            elif token:
                self.options.append(token)
        self.base = head


class Pack:
    def __init__(self, folder: Path):
        self.folder = folder
        self.json = json.loads((folder / "pack.json").read_text("utf-8"))
        self.id = str(self.json["id"])
        self.name = str(self.json.get("name") or self.id)
        self.palette = {k: v for k, v in (self.json.get("palette") or {}).items() if isinstance(v, str)}
        self.files = {}
        for path in sorted(folder.rglob("*")):
            if path.is_file() and IMAGE.match(path.name):
                rel = path.relative_to(folder).as_posix()
                self.files.setdefault(rel.rsplit(".", 1)[0], path)   # "dir/resource" (a nine-patch keeps ".9")
        self.by_category: dict[str, list[dict]] = {}
        for layer in self.json.get("layers", []):
            self.by_category.setdefault(layer["category"], []).append(layer)

    def colour(self, slot: str | None, fallback: str) -> str:
        value = self.palette.get(slot or "", "")
        m = re.fullmatch(r"#(?:[0-9a-fA-F]{2})?([0-9a-fA-F]{6})", value)
        return "#" + m.group(1).upper() if m else fallback

    def looks(self) -> list[tuple[str, str]]:
        """The icon looks a person can pick, (option key, label); one plain look when none."""
        for option in self.json.get("options", []):
            keys = option.get("keys") or []
            if option.get("type") == "select" and keys:
                choices = option.get("choices") or []
                return [(k, re.sub(r"\s*\([^)]*\)\s*$", "", choices[i]).strip() if i < len(choices) else k.title())
                        for i, k in enumerate(keys)]
        return [("standard", "Standard")]

    def stack(self, category: str, resource: str) -> list[tuple[Path, str | None]]:
        """The picture files of one drawable, bottom first, each with the slot that tints it."""
        out = []
        for layer in sorted(self.by_category.get(category, []), key=lambda l: STAGES.get(l.get("stage"), 4)):
            if resource not in layer.get("resources", []):
                continue
            base = layer["path"].strip("/") + "/" + resource
            path = self.files.get(base) or self.files.get(base + ".9")
            if path is None:
                continue
            tint = layer.get("tint") or {}
            out.append((path, tint.get("slot") if tint.get("kind") == "slot" else None))
        return out

    def resources(self, category: str) -> list[str]:
        seen = []
        for layer in self.by_category.get(category, []):
            for resource in layer.get("resources", []):
                if resource not in seen:
                    seen.append(resource)
        return sorted(seen)


# --- drawing ----------------------------------------------------------------------------------

def rgb(colour: str) -> tuple[int, int, int]:
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def compose(pack: Pack, stack: list[tuple[Path, str | None]], night_slots: bool = False) -> Image.Image | None:
    """The layers of [stack] over each other at the size of the first, each multiplied by its tint."""
    out = None
    for path, slot in stack:
        layer = Image.open(path).convert("RGBA")
        if out is not None and layer.size != out.size:
            layer = layer.resize(out.size, Image.LANCZOS)
        if slot:
            if night_slots and slot.startswith("l"):
                slot = slot[1:]
            tint = np.array(rgb(pack.colour(slot, "#FFFFFF")) + (255,), dtype=np.float32) / 255.0
            layer = Image.fromarray((np.asarray(layer, dtype=np.float32) * tint).round().astype(np.uint8), "RGBA")
        out = layer if out is None else Image.alpha_composite(out, layer)
    return out


def fit(picture: Image.Image, width: int, height: int) -> Image.Image:
    """[picture] scaled to fit a transparent width x height tile, centred, never enlarged."""
    scale = min(width / picture.width, height / picture.height, 1.0)
    size = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
    if size != picture.size:
        picture = picture.resize(size, Image.LANCZOS)
    tile = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    tile.alpha_composite(picture, ((width - size[0]) // 2, (height - size[1]) // 2))
    return tile


def on(colour: str, picture: Image.Image, width: int, height: int, share: float = 1.0) -> Image.Image:
    """[picture] centred on an opaque width x height tile of [colour], filling [share] of it at most."""
    tile = Image.new("RGBA", (width, height), rgb(colour) + (255,))
    inner = fit(picture, max(1, round(width * share)), max(1, round(height * share)))
    tile.alpha_composite(inner, ((width - inner.width) // 2, (height - inner.height) // 2))
    return tile


def backdrop(picture: Image.Image, dark: str, light: str) -> str:
    """The tile colour a picture reads on: [light] under dark art (a dark call icon), else [dark]."""
    a = np.asarray(picture.convert("RGBA"), dtype=np.float32)
    weight = a[..., 3]
    if weight.sum() <= 0:
        return dark
    lum = (a[..., :3] @ np.array([0.299, 0.587, 0.114], dtype=np.float32) * weight).sum() / weight.sum()
    return light if lum < 80 else dark


class Patch:
    """A composed nine-patch: the picture inside its marker border, where it stretches, its padding."""

    def __init__(self, picture: Image.Image, guide: Image.Image | None):
        if guide is None or picture.width < 3 or picture.height < 3:
            self.image, self.xs, self.ys, self.pad = picture, [(0, picture.width)], [(0, picture.height)], (0, 0)
            return
        g = np.asarray(guide.convert("RGBA"))
        marked = lambda px: (px[:, 3] > 127) & (px[:, :3].sum(axis=1) < 96)
        self.image = picture.crop((1, 1, picture.width - 1, picture.height - 1))
        w, h = self.image.size
        self.xs = self._runs(marked(g[0, 1:-1])) or [(0, w)]
        self.ys = self._runs(marked(g[1:-1, 0])) or [(0, h)]
        bottom = self._runs(marked(g[-1, 1:-1]))
        self.pad = (bottom[0][0], w - bottom[-1][1]) if bottom else (0, 0)

    @staticmethod
    def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
        runs, start = [], None
        for i, on in enumerate(list(flags) + [False]):
            if on and start is None:
                start = i
            elif not on and start is not None:
                runs.append((start, i))
                start = None
        return runs

    @staticmethod
    def _segments(size: int, runs: list[tuple[int, int]], target: int) -> list[tuple[int, int, int]]:
        """(source start, source length, drawn length) along one axis for a picture drawn [target] long."""
        cuts, at = [], 0
        for a, b in runs:
            if a > at:
                cuts.append((at, a - at, False))
            cuts.append((a, b - a, True))
            at = b
        if at < size:
            cuts.append((at, size - at, False))
        fixed = sum(n for _, n, s in cuts if not s)
        stretch = sum(n for _, n, s in cuts if s)
        if stretch == 0 or target <= fixed:
            return [(a, n, n * target / size) for a, n, _ in cuts]
        return [(a, n, n * (target - fixed) / stretch if s else n) for a, n, s in cuts]

    def draw(self, width: int, height: int) -> Image.Image:
        out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        y = 0.0
        for sy, sh, dh in self._segments(self.image.height, self.ys, height):
            x = 0.0
            for sx, sw, dw in self._segments(self.image.width, self.xs, width):
                box = (round(x), round(y), round(x + dw), round(y + dh))
                if box[2] > box[0] and box[3] > box[1]:
                    piece = self.image.crop((sx, sy, sx + sw, sy + sh)).resize((box[2] - box[0], box[3] - box[1]), Image.BILINEAR)
                    out.paste(piece, box[:2])
                x += dw
            y += dh
        return out


def patch(pack: Pack, categories: list[str], names: list[str]) -> Patch | None:
    """The art of a switch part from the first of [categories] that draws one of [names]."""
    for category in categories:
        for name in names:
            stack = pack.stack(category, name)
            if not stack:
                continue
            picture = compose(pack, stack, night_slots=False)
            guide = next((Image.open(p) for p, _ in stack if p.name.lower().endswith(".9.png")), None)
            if guide is not None and guide.size != picture.size:
                guide = None
            return Patch(picture, guide)
    return None


def switch(track: Patch | None, thumb: Patch | None, on: bool, ink: tuple[int, int, int]) -> Image.Image:
    """A switch the way One UI 9 lays it out: the track 32 dp wide, the thumb at its own width at one end."""
    from PIL import ImageDraw

    track_h = track.image.height if track else TRACK_H
    thumb_w = thumb.image.width if thumb else THUMB
    thumb_h = thumb.image.height if thumb else THUMB
    t_pad = track.pad if track else (0, 0)
    k_pad = thumb.pad if thumb else (0, 0)
    body = max(thumb_w - k_pad[0] - k_pad[1], 0)
    extra = math.ceil(body - TRACK_W * WIDE_THUMB) if body / TRACK_W > WIDE_THUMB else 0
    width, height = TRACK_W + extra, max(track_h, thumb_h)
    slide = max(width - body - t_pad[0] - t_pad[1], 0)
    off = t_pad[0] - k_pad[0]
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    left = extra // 2
    if track:
        out.alpha_composite(track.draw(width - 2 * left, height), (left, 0))
    else:
        ImageDraw.Draw(out).rounded_rectangle((left, 0, width - left - 1, height - 1), 30, fill=ink + (115 if on else 64,))
    x = off + (slide if on else 0)
    if thumb:
        layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
        layer.paste(thumb.draw(thumb_w, height), (x, 0))
        out = Image.alpha_composite(out, layer)
    else:
        inset = thumb_w * 0.1
        ImageDraw.Draw(out).ellipse((x + inset, height * 0.1, x + thumb_w - inset, height * 0.9), fill=(255, 255, 255, 255))
    return out



KEYBOARD_ROWS = ["qwertyuiop", "asdfghjkl", "^zxcvbnm<", "!,_.>"]   # ^ shift, < delete, _ space, ! symbols, > enter
KEYBOARD_SIZE = (720, 504)   # the keys and, above them, room for the toolbar row


def keyboard(pack: Pack, category: str) -> Image.Image | None:
    """The Samsung Keyboard as a pack draws it: its backdrop and its key art, four rows of keys.

    Letter keys use textinput_qwerty_btn, the shift, delete, symbols and enter keys the lighter
    textinput_qwerty_btn_light, as the keyboard does; each is a nine-patch stretched to the key.
    The letters take white or near black, whichever reads on the key's centre."""
    from PIL import ImageDraw, ImageFont
    back = patch(pack, [category], ["0bg", "keyboard_background_image"])
    key = patch(pack, [category], ["textinput_qwerty_btn"])
    if back is None and key is None:
        return None
    width, height = KEYBOARD_SIZE
    out = Image.new("RGBA", (width, height), rgb(pack.colour("xx0", "#101418")) + (255,))
    if back is not None:
        out.alpha_composite(back.draw(width, height))
    light = patch(pack, [category], ["textinput_qwerty_btn_light"]) or key
    gap, top = 8, 62
    row_h = (height - top - gap * (len(KEYBOARD_ROWS) + 1)) // len(KEYBOARD_ROWS)
    unit = (width - gap * 11) / 10
    size = int(row_h * 0.36)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:   # Pillow before 10.1
            font = ImageFont.load_default()
    labels = {"^": "\u21e7", "<": "\u232b", "!": "!#1", ">": "\u21b5", "_": "", ",": ","}
    for r, row in enumerate(KEYBOARD_ROWS):
        spans = [4.6 if c == "_" else 1.5 if c in "^<!>" else 1.0 for c in row]
        total = sum(spans) * unit + gap * (len(row) - 1)
        x = (width - total) / 2
        y = top + gap + r * (row_h + gap)
        for c, span in zip(row, spans):
            w = int(span * unit)
            art = light if c in "^<!>" else key
            if art is not None:
                piece = art.draw(w, row_h)
                out.alpha_composite(piece, (int(x), y))
                centre = np.asarray(piece.convert("RGBA"))[row_h // 2, w // 2]
                level = centre[:3].mean() if centre[3] > 96 else np.asarray(out)[y + row_h // 2, int(x) + w // 2][:3].mean()
            else:
                level = 0
            text = labels.get(c, c)
            if text:
                ink = (20, 20, 24, 255) if level > 150 else (255, 255, 255, 255)
                ImageDraw.Draw(out).text((x + w / 2, y + row_h / 2), text, fill=ink, font=font, anchor="mm")
            x += w + gap
    return out


def save(picture: Image.Image, path: Path, quality: int = 80) -> None:
    """[picture] as WebP: lossy, or lossless when that is smaller (flat vector art often is)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lossy = io.BytesIO()
    picture.save(lossy, "WEBP", quality=quality, method=6, alpha_quality=90, exact=False)
    best = lossy.getvalue()
    if picture.mode == "RGBA" and len(best) < 400_000:
        exact = io.BytesIO()
        picture.save(exact, "WEBP", lossless=True, quality=100, method=6, exact=False)
        if exact.tell() < len(best):
            best = exact.getvalue()
    path.write_bytes(best)


def photo(source: Path, path: Path, width: int, quality: int) -> None:
    picture = Image.open(source)
    picture = picture.convert("RGBA" if "A" in picture.getbands() or picture.mode == "P" else "RGB")
    if picture.mode == "RGBA" and picture.getextrema()[3][0] == 255:
        picture = picture.convert("RGB")
    if picture.width > width:
        picture = picture.resize((width, round(picture.height * width / picture.width)), Image.LANCZOS)
    save(picture, path, quality)


# --- one theme --------------------------------------------------------------------------------

def build(pack: Pack, out: Path) -> tuple[dict, dict]:
    """Writes the pictures of [pack] to [out]; returns its manifest entry and its layout."""
    for old in out.glob("*.webp") if out.is_dir() else []:
        if OWNED.fullmatch(old.name):
            old.unlink()
    layout: dict = {"pics": [], "looks": [], "parts": [], "modes": []}
    card_colour = pack.colour("xx5", "#1B2230")
    page_colour = pack.colour("lxx0", "#F2F4F8")

    # Wallpaper and notification cards.
    wallpaper = pack.json.get("wallpaper")
    wall = pack.folder / wallpaper if isinstance(wallpaper, str) and (pack.folder / wallpaper).is_file() else None
    if wall is None:
        wall = next((p for stem, p in pack.files.items() if stem == "wallpaper"), None)
    if wall is not None:
        photo(wall, out / "wallpaper.webp", 540, 76)
        layout["pics"].append(["wallpaper.webp", "Wallpaper", "wall"])
    cards = sorted((p for stem, p in pack.files.items() if stem.startswith("notification/")), key=lambda p: ("night" in p.name, p.name))
    for i, card in enumerate(cards[:2]):
        name = "card-night.webp" if "night" in card.name else "card.webp"
        photo(card, out / name, 720, 74)
        layout["pics"].append([name, "Notification card, dark mode" if "night" in card.name else "Notification card", "card"])
    for category, name, label in (("keyboard", "keyboard.webp", "Samsung Keyboard"), ("keyboard_night", "keyboard-night.webp", "Samsung Keyboard, dark mode")):
        picture = keyboard(pack, category) if category in pack.by_category else None
        if picture is not None:
            save(picture.convert("RGB"), out / name, 76)
            layout["pics"].append([name, label, "keys"])

    # Icon looks: one sprite sheet per look, every part in the same tile order.
    categories = {raw: Category(raw) for raw in pack.by_category}
    bases = [c.base for c in categories.values() if not c.night and not c.options]
    known = [p for p in ICON_PARTS if p[0] in bases]
    labels = pack.json.get("categories") or {}
    for base in bases:
        if base in SKIP_BASES or base in (CONTROL, DIALPAD) or any(base == p[0] for p in known):
            continue
        label = re.sub(r"\s*\([^)]*\)\s*$", "", str(labels.get(base, ""))).strip() or base.replace("_", " ").capitalize()
        known.append((base, label, "grid", OTHER_TILE))
    y = 0
    for base, label, kind, tile in known:
        names = [r for r in pack.resources(base) if pack.stack(base, r) and not pack.stack(base, r)[0][0].name.endswith(".9.png")]
        if not names:
            continue
        layout["parts"].append({"k": base, "label": label, "kind": kind, "t": tile, "y": y, "names": [caption(n) for n in names], "_res": names})
        y += math.ceil(len(names) / (ATLAS_W // tile)) * tile
    looks = pack.looks()
    for index, (key, label) in enumerate(looks):
        if not y:
            break
        sheet = Image.new("RGBA", (ATLAS_W, y), rgb(card_colour) + (255,))
        for part in layout["parts"]:
            own = part["k"] if index == 0 else f"{part['k']}-{key}"
            if index == 0 and not pack.stack(own, part["_res"][0]) and f"{part['k']}-{key}" in pack.by_category:
                own = f"{part['k']}-{key}"
            tile, cols = part["t"], ATLAS_W // part["t"]
            for i, resource in enumerate(part["_res"]):
                picture = compose(pack, pack.stack(own, resource) or pack.stack(part["k"], resource), night_slots=True)
                if picture is None:
                    continue
                sheet.alpha_composite(on(card_colour, picture, tile, tile, ICON_SHARE), ((i % cols) * tile, part["y"] + (i // cols) * tile))
        name = f"look-{re.sub(r'[^a-z0-9]+', '', key.lower()) or index}.webp"
        save(sheet.convert("RGB"), out / name, 74)
        layout["looks"].append({"k": key, "label": label, "file": name})
    layout["atlas"] = [ATLAS_W, y]
    for part in layout["parts"]:
        del part["_res"]

    # Switches, checkboxes, radios and the dialer buttons, by day and by night, on one sheet.
    cells: list[tuple[Image.Image, int]] = []   # picture, tiles wide
    modes = []
    for night in (False, True):
        suffix = "_night" if night else ""
        control = [c for c in (CONTROL + suffix, CONTROL) if c in pack.by_category]
        dial = DIALPAD + suffix if DIALPAD + suffix in pack.by_category else (DIALPAD if DIALPAD in pack.by_category else None)
        if night and CONTROL + suffix not in pack.by_category and (dial is None or dial == DIALPAD):
            continue
        mode = {"k": "night" if night else "day", "label": "Dark mode" if night else "Light mode", "switches": [], "controls": [], "dial": []}
        ink = rgb(pack.colour("xx3" if night else "lxx3", "#FFFFFF" if night else "#101010"))
        if control and (not night or control[0].endswith("_night")):
            surface = card_colour if night else page_colour
            drawn = []
            for label, track_name, thumb_name in SWITCHES[night]:
                track = patch(pack, control, ["sesl_" + track_name, track_name])
                thumb = patch(pack, control, ["sesl_" + thumb_name, thumb_name])
                if track is not None or thumb is not None:
                    drawn.append((label, switch(track, thumb, label != "Off", ink)))
            # One scale for the three states, at most twice the size on the phone, cut to what is drawn.
            boxes = [p.getbbox() for _, p in drawn if p.getbbox()]
            if boxes:
                box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
                zoom = min(2.0, SWITCH_SPAN * TILE * 0.92 / (box[2] - box[0]), TILE * 0.88 / (box[3] - box[1]))
                for label, picture in drawn:
                    picture = picture.crop(box)
                    picture = picture.resize((round(picture.width * zoom), round(picture.height * zoom)), Image.LANCZOS)
                    mode["switches"].append([label, len(cells)])
                    cells.append((on(surface, picture, SWITCH_SPAN * TILE, TILE), SWITCH_SPAN))
            for resource in pack.resources(control[0]):
                stack = pack.stack(control[0], resource)
                if not stack or stack[0][0].name.endswith(".9.png"):
                    continue
                mode["controls"].append([caption(resource), len(cells)])
                cells.append((on(surface, compose(pack, stack), TILE, TILE, 0.8), 1))
        if dial and (not night or dial.endswith("_night")):
            for resource in pack.resources(dial):
                stack = pack.stack(dial, resource)
                if not stack:
                    continue
                if resource in PANEL_PIECES:
                    name = f"dialpad{'-night' if night else ''}.webp"
                    photo(stack[0][0], out / name, 480, 76)
                    mode["panel"] = name
                    continue
                picture = compose(pack, stack)
                mode["dial"].append([caption(resource), len(cells)])
                cells.append((on(backdrop(picture, card_colour, page_colour), picture, TILE, TILE, ICON_SHARE), 1))
        if mode["switches"] or mode["controls"] or mode["dial"] or "panel" in mode:
            modes.append(mode)
    if cells:
        # Lay the tiles out row by row; a switch never wraps.
        places, col, row = [], 0, 0
        for _, span in cells:
            if col + span > PARTS_COLS:
                col, row = 0, row + 1
            places.append((col, row))
            col += span
        sheet = Image.new("RGBA", (PARTS_COLS * TILE, (row + 1) * TILE), rgb(card_colour) + (255,))
        for (picture, _), (c, r) in zip(cells, places):
            sheet.alpha_composite(picture, (c * TILE, r * TILE))
        save(sheet.convert("RGB"), out / "parts.webp", 80)
        for mode in modes:
            for key in ("switches", "controls", "dial"):
                mode[key] = [[label, *places[i]] for label, i in mode[key]]
        layout["sheet"] = ["parts.webp", PARTS_COLS, row + 1]
    layout["modes"] = modes

    digest = hashlib.sha256()
    for path in sorted(out.glob("*.webp")):
        if OWNED.fullmatch(path.name):
            digest.update(path.name.encode() + path.read_bytes())
    entry = {
        "id": pack.id,
        "name": pack.name,
        "v": digest.hexdigest()[:8],
        "c": {
            "bg": pack.colour("xx0", "#10141C"), "card": pack.colour("xx5", "#1B2230"), "ink": pack.colour("xx3", "#FFFFFF"),
            "accent": pack.colour("xx1", "#3DE0F5"), "second": pack.colour("xx2", "#FF6B5B"),
            "page": pack.colour("lxx0", "#F2F4F8"), "pageCard": pack.colour("lxx5", "#E3E7EE"),
            "pageInk": pack.colour("lxx3", "#10141C"), "pageAccent": pack.colour("lxx1", "#1E6FD9"),
        },
    }
    return entry, layout


# --- the page ---------------------------------------------------------------------------------

def page_block(manifest: dict) -> str:
    tabs = []
    for i, theme in enumerate(manifest["themes"]):
        tabs.append(
            f'<button class="tab" role="tab" type="button" id="b-{theme["id"]}" data-theme="{theme["id"]}" '
            f'aria-selected="{"true" if i == 0 else "false"}" aria-controls="theme-panel" tabindex="{0 if i == 0 else -1}" '
            f'style="--accent:{theme["c"]["accent"]}"><i></i>{html.escape(theme["name"])}</button>'
        )
    data = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    return (
        f"{BEGIN}\n"
        "    <!-- Written by tools/build_themes.py: do not edit by hand. -->\n"
        '    <div class="rail" id="theme-rail">\n'
        '      <button class="rail-btn prev" type="button" aria-label="Scroll the themes back" tabindex="-1" hidden>'
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg></button>\n'
        f'      <div class="tabs" role="tablist" aria-label="Theme packs" aria-orientation="horizontal">\n        '
        + "\n        ".join(tabs) + "\n      </div>\n"
        '      <button class="rail-btn next" type="button" aria-label="Scroll the themes forward" tabindex="-1" hidden>'
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg></button>\n'
        "    </div>\n"
        f'    <div class="pack" id="theme-panel" role="tabpanel" aria-labelledby="b-{manifest["themes"][0]["id"]}" tabindex="-1">\n'
        f'      <noscript><p class="pack-note">Turn on JavaScript to browse the art of all {len(manifest["themes"])} packs.</p></noscript>\n'
        "    </div>\n"
        f'    <script type="application/json" id="themes-data">{data}</script>\n'
        f"    {END}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--packs", required=True, type=Path, help="folder with the pack files, <id>.zip")
    parser.add_argument("--work", required=True, type=Path, help="scratch folder the pictures are unpacked into")
    parser.add_argument("--only", default="", help="comma-separated ids to redraw; the others keep their pictures")
    parser.add_argument("--no-page", action="store_true", help="leave index.html alone")
    args = parser.parse_args()

    config = json.loads(CONFIG.read_text("utf-8"))
    order = config["order"]
    only = {x for x in args.only.split(",") if x}
    cache_path = SITE / "tools" / "themes.lock.json"
    cache = json.loads(cache_path.read_text("utf-8")) if cache_path.is_file() else {}
    missing, themes, layouts = [], [], []
    for pack_id in order:
        if not re.fullmatch(r"[a-z0-9_-]+", pack_id):
            raise SystemExit(f"bad pack id {pack_id!r}")
        if only and pack_id not in only:
            if pack_id not in cache:
                continue
            entry, layout = cache[pack_id]["entry"], cache[pack_id]["layout"]
        else:
            source = args.packs / f"{pack_id}.zip"
            if not source.is_file():
                missing.append(pack_id)
                continue
            pack = Pack(extract(source, args.work))
            entry, layout = build(pack, OUT / pack_id)
            entry["id"] = pack_id
            cache[pack_id] = {"entry": entry, "layout": layout}
            size = sum(p.stat().st_size for p in (OUT / pack_id).glob("*.webp") if OWNED.fullmatch(p.name))
            print(f"{pack_id:16} {entry['name']:18} {size / 1024:7.0f} KB", flush=True)
        if layout not in layouts:
            layouts.append(layout)
        themes.append({**entry, "l": layouts.index(layout)})
    cache_path.write_text("{\n" + ",\n".join(json.dumps(k) + ": " + json.dumps(cache[k], separators=(",", ":"), ensure_ascii=False) for k in order if k in cache) + "\n}" + "\n", "utf-8")
    manifest = {"base": "assets/themes/", "layouts": layouts, "themes": themes}
    if not args.no_page and themes:
        text = INDEX.read_text("utf-8")
        a, b = text.find(BEGIN), text.find(END)
        if a < 0 or b < a:
            raise SystemExit("index.html has no themes:begin / themes:end block")
        INDEX.write_text(text[:a] + page_block(manifest) + text[b + len(END):], "utf-8")
    total = sum(p.stat().st_size for t in themes for p in (OUT / t["id"]).glob("*.webp") if OWNED.fullmatch(p.name))
    print(f"{len(themes)} themes, {total / 1e6:.1f} MB of pictures, {len(layouts)} layout(s)")
    if missing:
        print("no pack file for: " + ", ".join(missing), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
