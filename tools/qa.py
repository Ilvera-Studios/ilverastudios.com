"""QA for the built site: overflow at every width, broken links and anchors, console errors,
failed requests, and screenshots.

  python3 tools/qa.py [--shots page1,page2] [--widths 320,375,...]
Serves dist/ on a local port, so pretty URLs resolve the way a static host serves them.
"""
import argparse, http.server, json, re, socketserver, threading, sys
from functools import partial
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SHOTS = Path("/home/claude/qa"); SHOTS.mkdir(exist_ok=True)
ROUTES = ["/", "/work/", "/work/the-simple-proof/", "/services/", "/services/youtube-production/",
          "/originals/", "/about/", "/contact/", "/privacy/", "/404.html"]

ap = argparse.ArgumentParser()
ap.add_argument("--widths", default="320,375,390,430,768,1024,1280,1440,1920")
ap.add_argument("--shots", default="")
ap.add_argument("--shot-widths", default="390,1440")
args = ap.parse_args()
widths = [int(w) for w in args.widths.split(",")]
shot_routes = [r for r in args.shots.split(",") if r]
shot_widths = [int(w) for w in args.shot_widths.split(",")]

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), partial(Quiet, directory=str(DIST)))
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{port}"

problems = []
def flag(msg):
    problems.append(msg); print("  !", msg)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
    # 1. links and anchors (desktop width once per page)
    page = b.new_page(viewport={"width": 1280, "height": 900})
    seen_ids = {}
    links = []
    for r in ROUTES:
        errs = []
        page.on("console", lambda m, errs=errs: errs.append(m.text) if m.type == "error" else None)
        failed = []
        page.on("response", lambda resp, failed=failed: failed.append(f"{resp.status} {resp.url}") if resp.status >= 400 and not resp.url.endswith("404.html") else None)
        page.goto(BASE + r, wait_until="networkidle")
        ids = page.eval_on_selector_all("[id]", "els => els.map(e => e.id)")
        seen_ids[r] = set(ids)
        dup = {i for i in ids if ids.count(i) > 1}
        if dup: flag(f"{r}: duplicate ids {sorted(dup)}")
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
        for h in hrefs: links.append((r, h))
        for e in errs: flag(f"{r}: console error: {e}")
        for f in failed: flag(f"{r}: failed request {f}")
        page.remove_listener("console", page.listeners("console")[0]) if hasattr(page, "listeners") else None
    for src, h in links:
        if h.startswith(("mailto:", "http://", "https://")):
            if h.startswith(("http://127.0.0.1",)): flag(f"{src}: absolute local link {h}")
            continue
        full = urljoin(BASE + src, h)
        u = urlparse(full)
        path = u.path
        if src == "/404.html" and not h.startswith(("/", "#")): flag(f"404 page uses relative link {h}")
        fpath = DIST / path.lstrip("/")
        if path.endswith("/"): fpath = fpath / "index.html"
        if not fpath.exists(): flag(f"{src}: broken link {h} -> {path}"); continue
        if u.fragment:
            target_route = path if path.endswith("/") or path.endswith(".html") else path + "/"
            if target_route not in seen_ids:
                continue
            if u.fragment not in seen_ids[target_route]: flag(f"{src}: missing anchor #{u.fragment} on {target_route}")
    page.close()
    # 2. overflow + screenshots at every width
    for w in widths:
        ctx = b.new_context(viewport={"width": w, "height": 900 if w >= 768 else 820}, device_scale_factor=1 if w >= 1024 else 2,
                            has_touch=w < 1024, is_mobile=w < 768, reduced_motion="no-preference")
        pg = ctx.new_page()
        for r in ROUTES:
            pg.goto(BASE + r, wait_until="networkidle")
            pg.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
            pg.evaluate("document.querySelectorAll('.reveal').forEach(e => e.classList.add('is-in'))")
            if r in shot_routes and w in shot_widths:
                pg.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
                pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(600)
            pg.evaluate("document.fonts.ready")
            sw = pg.evaluate("document.documentElement.scrollWidth")
            if sw > w:
                wide = pg.evaluate(f"""[...document.querySelectorAll('body *')].filter(e => {{const r = e.getBoundingClientRect(); return r.right > {w} + 1 && getComputedStyle(e).position !== 'fixed'}}).slice(0,5).map(e => e.tagName.toLowerCase() + '.' + [...e.classList].join('.') + ' right=' + Math.round(e.getBoundingClientRect().right))""")
                flag(f"{r} @ {w}px: horizontal overflow {sw}px; widest: {wide}")
            small = pg.evaluate("""[...document.querySelectorAll('a, button, input, select, textarea, summary')].filter(e => {const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && (r.height < 24 || r.width < 24) && !e.closest('.footer-nav, .footer-contact, .footer-legal, .crumbs, p, li, dd, td, figcaption, .hero-proof, .aside-note, .choice')}).slice(0,4).map(e => e.tagName.toLowerCase() + '.' + [...e.classList].join('.') + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height))""")
            if small: flag(f"{r} @ {w}px: small targets {small}")
            if r in shot_routes and w in shot_widths:
                name = (r.strip('/').replace('/', '_') or 'home').replace('.html', '')
                pg.screenshot(path=str(SHOTS / f"{name}_{w}.png"), full_page=True)
        ctx.close()
    b.close()
srv.shutdown()
print(f"\nQA done: {len(problems)} problem(s)")
json.dump(problems, open(SHOTS / "problems.json", "w"), indent=1)
