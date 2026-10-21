"""Build docs/demo.gif from the real run: inbox thumbnails, the real log, the real report."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
W, H = 900, 620
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
MONO = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
root = Path(__file__).resolve().parent.parent
frames, durs = [], []

def card(title, sub=""):
    im = Image.new("RGB", (W, H), (250, 248, 243)); d = ImageDraw.Draw(im)
    d.text((30, 22), title, font=FB, fill=(30, 30, 30))
    if sub: d.text((30, 60), sub, font=F, fill=(110, 110, 110))
    return im, d

# 1. inbox
im, d = card("11 pm: drop the day's Pix screenshots in a folder", "12 (fictional) receipts, 11 open orders. Then go to sleep.")
thumbs = sorted((root / "samples/inbox").glob("*.png"))
for i, p in enumerate(thumbs):
    t = Image.open(p).convert("RGB"); t.thumbnail((120, 200))
    im.paste(t, (30 + (i % 6) * 142, 110 + (i // 6) * 240))
frames.append(im); durs.append(2600)

# 2. terminal, line by line (real log)
log = [l for l in (root / "docs/run.log").read_text().splitlines() if l.startswith("[")]
for n in range(0, len(log) + 1, 3):
    im, d = card("Overnight: Gemma 4 reads them on 2 CPU cores", "about 52 s per receipt; nothing leaves the machine")
    d.rectangle([30, 110, W - 30, H - 30], fill=(24, 24, 32))
    d.text((50, 125), "$ python sloth.py --inbox inbox --orders orders.csv ...", font=MONO, fill=(140, 220, 160))
    for j, l in enumerate(log[:n]):
        d.text((50, 160 + j * 30), l.strip(), font=MONO, fill=(230, 230, 235))
    frames.append(im); durs.append(700)
durs[-1] = 1500

# 3. report
rep = Image.open(root / "docs/report.png").convert("RGB")
for top in (0, 330, 1250):
    im, d = card("7 am: one short list of what needs you", "rules decide; anything doubtful goes to a human")
    crop = rep.crop((0, top, 1000, top + 560)); crop.thumbnail((W - 60, H - 100))
    im.paste(crop, (30, 100)); frames.append(im); durs.append(2600)

frames[0].save(root / "docs/demo.gif", save_all=True, append_images=frames[1:], duration=durs, loop=0, optimize=True)
print("frames", len(frames), (root / "docs/demo.gif").stat().st_size // 1024, "KB")
