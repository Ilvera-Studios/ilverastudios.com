"""Accessibility scan (axe-core) on every page at phone and desktop widths, plus interaction tests:
menu, reel, filters, copy, and the inquiry form (validation, email hand-off, and a mocked form service).

  python3 tools/qa_interact.py
"""
import http.server, json, socketserver, threading
from functools import partial
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AXE = Path("/home/claude/tools/node_modules/axe-core/axe.min.js").read_text()
ROUTES = ["/", "/work/", "/work/the-simple-proof/", "/services/", "/services/youtube-production/",
          "/originals/", "/about/", "/contact/", "/privacy/", "/404.html"]

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve(directory):
    srv = socketserver.TCPServer(("127.0.0.1", 0), partial(Quiet, directory=str(directory)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"

results = {"axe": {}, "tests": []}
def ok(name, cond, detail=""):
    results["tests"].append([name, bool(cond), detail]); print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))

srv, BASE = serve(ROOT / "dist")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
    # axe
    for w in (390, 1280):
        ctx = b.new_context(viewport={"width": w, "height": 900}, reduced_motion="reduce")
        pg = ctx.new_page()
        for r in ROUTES:
            pg.goto(BASE + r, wait_until="networkidle")
            pg.add_script_tag(content=AXE)
            res = pg.evaluate("""async () => { const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}});
              return r.violations.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, targets: v.nodes.slice(0,3).map(x => x.target.join(' '))})); }""")
            results["axe"][f"{r}@{w}"] = res
            for v in res:
                print(f"  axe {r}@{w}: {v['id']} ({v['impact']}) x{v['n']}: {v['targets']}")
        ctx.close()
    # interactions, phone
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.goto(BASE + "/", wait_until="networkidle")
    t = pg.locator(".menu-toggle")
    t.click()
    ok("menu opens", pg.evaluate("document.documentElement.classList.contains('menu-is-open')") and t.get_attribute("aria-expanded") == "true")
    ok("menu focuses first link", pg.evaluate("document.activeElement.closest('#mobile-menu') !== null"))
    pg.keyboard.press("Escape")
    ok("Escape closes menu and returns focus", t.get_attribute("aria-expanded") == "false" and pg.evaluate("document.activeElement.classList.contains('menu-toggle')"))
    ctx.close()
    # interactions, desktop
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    pg.goto(BASE + "/", wait_until="networkidle")
    pg.wait_for_timeout(500)
    playing = pg.evaluate("!document.querySelector('.reel-video').paused")
    ok("reel autoplays muted", playing and pg.evaluate("document.querySelector('.reel-video').muted"))
    # let it play into the second clip (the local test server can't seek, so no jumping ahead)
    pg.wait_for_function("document.querySelector('.reel-video').currentTime > 3.8 && document.querySelector('.reel-video').currentTime < 6.5", timeout=10000)
    pg.wait_for_timeout(300)
    cues = pg.evaluate("JSON.parse(document.querySelector('[data-reel]').dataset.cues)")
    lab = pg.inner_text(".reel-label")
    ok("reel label follows the clip", f"2 / {len(cues)}" in lab and cues[1]["title"] in lab, lab.replace("\n", " "))
    pg.click(".reel-toggle")
    ok("reel pause button pauses", pg.evaluate("document.querySelector('.reel-video').paused"))
    pg.click(".reel-toggle")
    ok("reel play button resumes", not pg.evaluate("document.querySelector('.reel-video').paused"))
    pg.hover(".work-card:has([data-preview]) >> nth=0")
    pg.wait_for_timeout(600)
    ok("card hover preview plays", pg.evaluate("(() => { const v = document.querySelector('.work-card:has([data-preview]) .preview'); return !!v && !v.paused; })()"))
    pg.goto(BASE + "/work/", wait_until="networkidle")
    pg.click(".filter[data-filter=founder]")
    vis = pg.evaluate("[...document.querySelectorAll('.work-grid-all .work-card')].filter(c => !c.hidden).map(c => c.id)")
    ok("work filter: founder portfolio", vis == ["the-simple-proof", "lights-on"], str(vis))
    pg.click(".filter[data-filter=development]")
    vis = pg.evaluate("[...document.querySelectorAll('.work-grid-all .work-card')].filter(c => !c.hidden).map(c => c.id)")
    ok("work filter: in development", vis == ["sienna-torneu", "will-vegas-hire-her", "he-chose-this"], str(vis))
    # form, no endpoint: validation then email hand-off
    pg.goto(BASE + "/contact/?utm_source=linkedin&utm_medium=dm&utm_campaign=launch&utm_content=acme", wait_until="networkidle")
    pg.click("button[type=submit]")
    ok("empty submit shows errors", pg.is_visible("#e-name") and pg.get_attribute("#f-name", "aria-invalid") == "true")
    ok("focus moves to first invalid field", pg.evaluate("document.activeElement.id") == "f-name")
    pg.fill("#f-name", "Test Person"); pg.fill("#f-business", "Acme Co"); pg.fill("#f-email", "not-an-email"); pg.fill("#f-goals", "A launch video")
    pg.click("button[type=submit]")
    ok("bad email blocked", pg.get_attribute("#f-email", "aria-invalid") == "true" and pg.is_visible("#e-email"))
    pg.fill("#f-email", "test@example.com")
    pg.select_option("#f-service", label="YouTube channel production")
    pg.check("input[name=engagement][value='Recurring production']")
    nav = []
    pg.on("framenavigated", lambda f: nav.append(f.url))
    pg.click("button[type=submit]")
    pg.wait_for_timeout(500)
    txt = pg.inner_text("[data-form-status]") if pg.is_visible("[data-form-status]") else ""
    ok("email hand-off card shown", "send it from your email" in txt.lower(), txt[:80].replace("\n", " "))
    msg = pg.inner_text(".status-msg") if pg.locator(".status-msg").count() else ""
    ok("hand-off message carries the fields and source", "Business: Acme Co" in msg and "Came from: linkedin / dm / launch / acme" in msg, msg.replace("\n", " | ")[:160])
    ok("never claims a send", "thanks, your request is in" not in txt.lower())
    # form with a mocked service
    ctx.close()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    html = (ROOT / "dist/contact/index.html").read_text().replace('data-endpoint=""', 'data-endpoint="https://forms.example.test/f/abc"')
    pg.route(BASE + "/contact/", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
    posted = []
    pg.route("https://forms.example.test/**", lambda route: (posted.append(route.request.post_data or ""), route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body='{"ok":true}')))
    pg.goto(BASE + "/contact/", wait_until="networkidle")
    pg.fill("#f-name", "Test Person"); pg.fill("#f-business", "Acme Co"); pg.fill("#f-email", "test@example.com"); pg.fill("#f-goals", "A launch video")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(800)
    txt = pg.inner_text("[data-form-status]")
    ok("configured service: success message after a 200", "your request is in" in txt.lower(), txt[:60].replace("\n", " "))
    ok("configured service: payload posted without the honeypot", bool(posted) and "Acme Co" in posted[0] and "company_website" not in posted[0])
    pg.unroute("https://forms.example.test/**")
    pg.route("https://forms.example.test/**", lambda route: route.fulfill(status=500, headers={"Access-Control-Allow-Origin": "*"}, body="no"))
    pg.fill("#f-name", "Test Person"); pg.fill("#f-business", "Acme Co"); pg.fill("#f-email", "test@example.com"); pg.fill("#f-goals", "A launch video")
    pg.click("button[type=submit]")
    pg.wait_for_timeout(800)
    txt = pg.inner_text("[data-form-status]")
    ok("configured service: failure falls back to email, nothing lost", "couldn't send" in txt.lower() and pg.locator(".status-msg").count() == 1)
    ctx.close()
    b.close()
srv.shutdown()
Path("/home/claude/qa/interact.json").write_text(json.dumps(results, indent=1))
fails = [t for t in results["tests"] if not t[1]]
nviol = sum(len(v) for v in results["axe"].values())
print(f"\n{len(results['tests']) - len(fails)}/{len(results['tests'])} interaction checks passed; axe violations: {nviol}")
