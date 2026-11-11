#!/usr/bin/env python3
"""Draw website artwork with the Gemini API.

Reads the key from the GEMINI_API_KEY environment variable (an Actions secret) and
never prints it. Writes PNGs to assets/ai/ named after each prompt below; existing
files are kept, so re-running only fills gaps unless --force is given.
"""
import base64, json, os, sys, time, urllib.error, urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "ai")

STYLE = ("Premium tech product marketing artwork, dark navy background (#070b1a), "
         "glowing cyan (#22d3ee) and coral (#ff6b6b) accents, soft volumetric light, "
         "crisp detail, no text, no letters, no logos, no watermark.")

PROMPTS = {
    "hero-backdrop": "Wide 16:9 abstract scene of floating translucent glass hexagons "
                     "drifting through deep space, faint nebula, light trails. " + STYLE,
    "ai-orb": "Square illustration of a glowing AI core made of liquid colour ribbons "
              "pouring paint onto a floating modern smartphone outline, magical, elegant. " + STYLE,
    "palette-wave": "Wide 16:9 flowing ribbons of colour swatches (cyan, violet, coral, gold) "
                    "sweeping like silk waves across a dark backdrop. " + STYLE,
    "icons-burst": "Square: dozens of colourful rounded app icon tiles with simple abstract "
                   "glyphs exploding outward from a central point, depth of field. " + STYLE,
    "galaxy-mood": "Wide 16:9 cosmic galaxy spiral with purple and teal stars, dreamy, "
                   "suitable as a phone theme mood board background. " + STYLE,
    "heroes-mood": "Wide 16:9 bold comic-inspired abstract energy bursts, halftone dots, "
                   "red gold and blue, no characters, no people. " + STYLE,
    "kameha-mood": "Wide 16:9 abstract crackling blue-white energy beam and orange aura "
                   "glow over rocky horizon, anime-inspired energy, no characters, no people. " + STYLE,
    "beta-glow": "Wide 16:9 minimal dark backdrop with a single glowing hexagon portal "
                 "opening, rays of cyan light, sense of exclusive invitation. " + STYLE,
}


def call(url, body=None):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def image_models():
    names = []
    page = ""
    while True:
        data = call(f"{API}/models?pageSize=200" + (f"&pageToken={page}" if page else ""))
        for m in data.get("models", []):
            n = m["name"].split("/", 1)[-1]
            methods = m.get("supportedGenerationMethods", [])
            if "image" in n or "imagen" in n:
                names.append((n, methods))
        page = data.get("nextPageToken", "")
        if not page:
            return names


def rank(name):
    order = ["gemini-3-pro-image", "imagen-4.0-ultra", "imagen-4.0-generate", "gemini-2.5-flash-image",
             "imagen-4.0-fast", "imagen-3", "gemini-2.0-flash"]
    for i, p in enumerate(order):
        if name.startswith(p):
            return i
    return len(order)


def generate(model, methods, prompt):
    if "predict" in methods:  # Imagen
        aspect = "16:9" if "16:9" in prompt else "1:1"
        data = call(f"{API}/models/{model}:predict",
                    {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": aspect}})
        return base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
    data = call(f"{API}/models/{model}:generateContent",
                {"contents": [{"parts": [{"text": prompt}]}],
                 "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}})
    for part in data["candidates"][0]["content"]["parts"]:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline:
            return base64.b64decode(inline["data"])
    raise RuntimeError("no image in reply")


def main():
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        sys.exit("GEMINI_API_KEY is not set in this repository's Actions secrets")
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    models = sorted(image_models(), key=lambda m: rank(m[0]))
    print("Image models on this key:", ", ".join(n for n, _ in models) or "none")
    made = 0
    for name, prompt in PROMPTS.items():
        path = os.path.join(OUT, name + ".png")
        if os.path.exists(path) and not force:
            continue
        for model, methods in models:
            try:
                png = generate(model, methods, prompt)
                with open(path, "wb") as f:
                    f.write(png)
                print(f"{name}: drawn by {model} ({len(png)} bytes)")
                made += 1
                break
            except urllib.error.HTTPError as e:
                print(f"{name}: {model} answered HTTP {e.code}: {e.read()[:200]!r}")
            except Exception as e:  # noqa: BLE001
                print(f"{name}: {model} failed: {e}")
            time.sleep(2)
    print(f"{made} new pictures")


if __name__ == "__main__":
    main()
