"""Render share images (1200x630) and PNG icons with the brand fonts and logo.

  python3 tools/og.py
Writes static/img/og/*.png and static/img/brand/{favicon-32,apple-touch-icon,icon-512}.png
"""
import html, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ST = ROOT / "static"
(ST / "img/og").mkdir(parents=True, exist_ok=True)
media = json.loads((ST / "media/media.json").read_text())
vb, d = (ST / "img/brand/wordmark.path.txt").read_text().split("\n", 1)

def still(name):
    v = sorted(media[name], key=lambda x: -x["w"])[0]
    return (ST / "media" / f"{name}-{v['w']}.webp").as_uri()

MARK = '<svg viewBox="12 20 84 60" class="mk"><rect x="20" y="22" width="12" height="56" rx="1.5" fill="#fff"/><polygon points="40,22 53,22 65,61 77,22 90,22 70,78 59,78" fill="#fff"/><polygon points="14,68 92,38 94,45 16,75" fill="#E03E49"/></svg>'
WORD = f'<svg viewBox="{vb.strip()}" class="wm"><path fill="#fff" d="{d.strip()}"/></svg>'

CARDS = {
    "home": dict(label="ILVERA Studios", title="Made to be watched. Start to finish.", sub="YouTube channels, product ads, commercials and branded series for businesses.", images=["still-tsp-infinity", "still-tsp-mandelbrot", "still-sienna-board", "still-wvhh-jackie"]),
    "work": dict(label="Work", title="Real work, labeled honestly.", sub="Published videos, founder projects and ILVERA originals.", images=["still-sienna-board"]),
    "case-the-simple-proof": dict(label="Case study", title="The Simple Proof", sub="111,946 views in under seven weeks, no ads. YouTube Studio, Oct 9 to Nov 23, 2026.", images=["still-tsp-mandelbrot"]),
    "services": dict(label="Services", title="What we produce for businesses.", sub="YouTube, product ads, commercials, explainers, series and digital talent.", images=["still-tsp-mandelbrot"]),
    "youtube": dict(label="YouTube production", title="The production team your YouTube channel never had.", sub="Long-form, Shorts and recurring series for businesses.", images=["still-tsp-infinity"]),
    "originals": dict(label="ILVERA Originals", title="Stories, characters and channels we own.", sub="Sienna Torneu, Will Vegas Hire Her? and He Chose This.", images=["still-sienna-portrait"], serif=True),
    "about": dict(label="About", title="A small studio that delivers finished work.", sub="Founded by Evan Surratt and Justin Whitmore.", images=[]),
    "contact": dict(label="Contact", title="Book a discovery call.", sub="Tell us what you want to make.", images=[]),
}

FONTS = "".join(
    f'@font-face{{font-family:"{fam}";src:url({(ST / "fonts" / f).as_uri()}) format("woff2");font-weight:{w};{extra}}}'
    for fam, f, w, extra in [("Syne", "syne.woff2", "400 800", ""), ("Jakarta", "jakarta.woff2", "200 800", ""),
                             ("Mono", "jetbrains.woff2", "100 800", ""), ("Corm", "cormorant.woff2", "300 700", "")])

CSS = FONTS + """
*{box-sizing:border-box;margin:0}
body{width:1200px;height:630px;background:#070709;color:#F9F8F6;font-family:Jakarta;overflow:hidden;position:relative}
.wrap{position:absolute;inset:0;padding:64px 64px 56px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:16px}
.mk{height:44px;width:auto}
.lab{font:500 17px Mono;letter-spacing:.16em;text-transform:uppercase;color:#B8AEB2;display:flex;align-items:center;gap:14px}
.lab:before{content:"";width:26px;height:5px;background:#E03E49;transform:rotate(-21deg)}
h1{font:800 64px/1 Syne;letter-spacing:-.03em;margin-top:auto;max-width:640px}
h1.serif{font:600 72px/1 Corm;letter-spacing:0}
p.sub{font-size:24px;line-height:1.35;color:#B8AEB2;margin-top:22px;max-width:600px}
.foot{display:flex;align-items:center;justify-content:space-between;margin-top:34px}
.wm{height:20px;width:auto}
.url{font:500 17px Mono;letter-spacing:.08em;color:#B8AEB2}
.pic{position:absolute;right:56px;top:56px;width:452px;height:518px;border-radius:18px;overflow:hidden;border:1px solid #2A1D22;background:#000}
.pic img{width:100%;height:100%;object-fit:cover}
.grid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:8px;background:#070709}
.g3{grid-template-rows:1.15fr 1fr}.g3 img:first-child{grid-column:1/-1}
.slash{position:absolute;right:430px;top:96px;width:170px;height:12px;background:#E03E49;transform:rotate(-21deg);box-shadow:0 0 30px rgba(224,62,73,.5)}
.big{position:absolute;right:40px;top:40px;height:420px;width:auto;opacity:.08}
.with-pic h1,.with-pic p.sub{max-width:560px}
"""

def card_html(key, c):
    imgs = c["images"]
    if len(imgs) > 1:
        pic = f'<div class="pic grid{" g3" if len(imgs) == 3 else ""}">' + "".join(f'<img src="{still(n)}">' for n in imgs) + "</div><span class='slash'></span>"
    elif imgs:
        pic = f'<div class="pic"><img src="{still(imgs[0])}"></div><span class="slash"></span>'
    else:
        pic = MARK.replace('class="mk"', 'class="big"')
    cls = "with-pic" if imgs else ""
    h1cls = "serif" if c.get("serif") else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body class="{cls}">{pic}
<div class="wrap"><div class="top">{MARK}<span class="lab">{html.escape(c['label'])}</span></div>
<h1 class="{h1cls}">{html.escape(c['title'])}</h1><p class="sub">{html.escape(c['sub'])}</p>
<div class="foot">{WORD}<span class="url">ilverastudios.com</span></div></div></body></html>"""

ICON = """<!doctype html><html><head><style>*{margin:0}body{width:%dpx;height:%dpx;background:#070709;display:grid;place-items:center}svg{width:72%%;height:auto}</style></head>
<body><svg viewBox="12 20 84 60"><rect x="20" y="22" width="12" height="56" rx="1.5" fill="#fff"/><polygon points="40,22 53,22 65,61 77,22 90,22 70,78 59,78" fill="#fff"/><polygon points="14,68 92,38 94,45 16,75" fill="#E03E49"/></svg></body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1200, "height": 630})
    tmp = ROOT / "tools" / "_og.html"
    for key, c in CARDS.items():
        tmp.write_text(card_html(key, c))
        pg.goto(tmp.as_uri()); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(250)
        pg.screenshot(path=str(ST / "img/og" / f"{key}.png"))
    for name, size in [("favicon-32", 32), ("apple-touch-icon", 180), ("icon-512", 512)]:
        tmp.write_text(ICON % (size, size))
        pi = b.new_page(viewport={"width": size, "height": size})
        pi.goto(tmp.as_uri()); pi.screenshot(path=str(ST / "img/brand" / f"{name}.png")); pi.close()
    tmp.unlink()
    b.close()
print("og + icons ok")
