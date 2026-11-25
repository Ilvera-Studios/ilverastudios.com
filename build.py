"""Build ilverastudios.com into dist/ (or dist-preview/ with --preview).

  python3 build.py            production build: pretty URLs, CNAME, sitemap, robots
  python3 build.py --preview  links end in index.html, for hosts without directory indexes

Content lives in content/*.yaml, layout in templates/, assets in static/.
The build stops if any page contains an em or en dash.
"""
import datetime, hashlib, json, os, posixpath, re, shutil, sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape

ROOT = Path(__file__).resolve().parent
PREVIEW = "--preview" in sys.argv
OUT = ROOT / ("dist-preview" if PREVIEW else "dist")

def load(name):
    with open(ROOT / "content" / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)

SITE = load("site.yaml")
CATALOG = load("catalog.yaml")
CASES = load("case_studies.yaml")
YT_FAQ = load("youtube_faq.yaml")
media = json.loads((ROOT / "static/media/media.json").read_text())
MEDIA = {k: sorted(v, key=lambda x: -x["w"]) for k, v in media.items() if k != "reel_cues"}
vb, d = (ROOT / "static/img/brand/wordmark.path.txt").read_text().split("\n", 1)
WORDMARK = {"viewbox": vb.strip(), "d": d.strip()}
updated = datetime.date.fromisoformat(SITE["updated"])
SITE["updated_human"] = updated.strftime("%B %-d, %Y")

REEL_TEXT = {
    "tsp-infinity": {"title": "The Simple Proof", "meta": "The Geometry of Infinity · Founder project · Published", "short": "founder project, published"},
    "tsp-mandelbrot": {"title": "The Simple Proof", "meta": "Mandelbrot film · Founder project · Published", "short": "founder project, published"},
    "lights-on": {"title": "Lights On!", "meta": "Animated series for young children · Founder project", "short": "founder project, pilot episodes"},
    "wvhh": {"title": "Will Vegas Hire Her?", "meta": "Vertical microdrama · ILVERA original · In development", "short": "ILVERA original, in development"},
    "sienna": {"title": "Sienna Torneu", "meta": "Chess lessons with a digital presenter · ILVERA original · In production", "short": "ILVERA original, in production"},
}
REEL_CUES = [dict(c, title=REEL_TEXT[c["id"]]["title"], meta=REEL_TEXT[c["id"]]["meta"]) for c in media["reel_cues"]]
REEL_LABELS = [REEL_TEXT[c["id"]] for c in media["reel_cues"]]

ORG = {
    "@context": "https://schema.org", "@type": "Organization", "@id": SITE["url"] + "/#organization",
    "name": "ILVERA Studios", "url": SITE["url"] + "/", "email": SITE["email"],
    "logo": SITE["url"] + "/img/brand/icon-512.png",
    "description": "Independent production company making YouTube channels, product ads, commercials and branded series for businesses, plus original entertainment.",
    "founder": [{"@type": "Person", "name": "Evan Surratt"}, {"@type": "Person", "name": "Justin Whitmore"}],
    "sameAs": [SITE["instagram_url"]],
}

def crumbs(*items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE["url"] + p} for i, (n, p) in enumerate(items)]}

PAGES = [
    dict(route="/", template="home.html", slug="home", section="/", og="home",
         title="ILVERA Studios | YouTube, ads and branded video production",
         og_title="ILVERA Studios: made to be watched, start to finish",
         description="An independent production company making YouTube channels, product ads, commercials and branded series for businesses, plus original entertainment of our own.",
         jsonld=[ORG, {"@context": "https://schema.org", "@type": "WebSite", "name": "ILVERA Studios", "url": SITE["url"] + "/", "publisher": {"@id": ORG["@id"]}}]),
    dict(route="/work/", template="work.html", slug="work", section="/work/", og="work",
         title="Work | ILVERA Studios",
         description="Published videos, founder projects and ILVERA originals, each labeled with who owns it and whether it's finished.",
         jsonld=[ORG, crumbs(("Home", "/"), ("Work", "/work/"))]),
    dict(route="/work/the-simple-proof/", template="case_study.html", slug="case", section="/work/", og="case-the-simple-proof", case="the-simple-proof",
         title="The Simple Proof case study | ILVERA Studios",
         og_title="Case study: The Simple Proof",
         description="How an educational YouTube channel drew 111,946 views in its first seven weeks with no ads: the method, the data and what it means for your channel.",
         jsonld=[ORG, crumbs(("Home", "/"), ("Work", "/work/"), ("The Simple Proof", "/work/the-simple-proof/"))]),
    dict(route="/services/", template="services.html", slug="services", section="/services/", og="services",
         title="Video production services | ILVERA Studios",
         description="YouTube channel production, product ads, brand commercials, explainer videos, branded series, microdramas and digital talent for businesses.",
         jsonld=[ORG, crumbs(("Home", "/"), ("Services", "/services/"))]),
    dict(route="/services/youtube-production/", template="youtube.html", slug="youtube", section="/services/youtube-production/", og="youtube",
         title="YouTube video production for businesses | ILVERA Studios",
         og_title="YouTube video production for businesses",
         description="We plan, script, produce and package YouTube videos for businesses: long-form, Shorts and recurring series, without an in-house production team.",
         jsonld=[ORG, crumbs(("Home", "/"), ("Services", "/services/"), ("YouTube production", "/services/youtube-production/")),
                 {"@context": "https://schema.org", "@type": "Service", "name": "YouTube video production for businesses",
                  "serviceType": "YouTube channel and video production", "provider": {"@id": ORG["@id"]},
                  "url": SITE["url"] + "/services/youtube-production/",
                  "description": "Channel positioning, recurring formats, scripts, production, packaging and publishing schedules for business YouTube channels."}]),
    dict(route="/originals/", template="originals.html", slug="originals", section="/originals/", og="originals",
         title="ILVERA Originals | ILVERA Studios",
         description="Series, characters and channels owned by ILVERA Studios, with honest status labels: Sienna Torneu, Will Vegas Hire Her? and He Chose This.",
         jsonld=[ORG, crumbs(("Home", "/"), ("Originals", "/originals/"))]),
    dict(route="/about/", template="about.html", slug="about", section="/about/", og="about",
         title="About the studio | ILVERA Studios",
         description="ILVERA Studios is an independent production company founded by Evan Surratt and Justin Whitmore. What we believe, how we work and who we are.",
         jsonld=[ORG, crumbs(("Home", "/"), ("About", "/about/"))]),
    dict(route="/contact/", template="contact.html", slug="contact", section="/contact/", og="contact",
         title="Book a discovery call | ILVERA Studios",
         description="Tell us what you want to make. We'll reply with times for a short call, usually within one business day.",
         jsonld=[ORG, crumbs(("Home", "/"), ("Book a discovery call", "/contact/"))]),
    dict(route="/privacy/", template="privacy.html", slug="privacy", section="/privacy/", og="home",
         title="Privacy notice | ILVERA Studios",
         description="What ILVERA Studios collects when you contact us, why, and what you can ask us to do with it.",
         jsonld=[ORG]),
    dict(route="/404.html", template="404.html", slug="notfound", section="", og="home", absolute=True,
         title="Page not found | ILVERA Studios",
         description="This page isn't here. Find our work, services and contact details.", jsonld=[ORG]),
]

def out_path(route):
    if route.endswith(".html"):
        return OUT / route.lstrip("/")
    return OUT / route.lstrip("/") / "index.html"

def rel(from_route, to_path):
    from_dir = from_route if from_route.endswith("/") else posixpath.dirname(from_route) + "/"
    r = posixpath.relpath(to_path, from_dir)
    if to_path.endswith("/") and not r.endswith("/"):
        r = "./" if r == "." else r + "/"
    return r

def build_id():
    h = hashlib.sha1()
    for p in ["static/css/site.css", "static/js/site.js"]:
        h.update((ROOT / p).read_bytes())
    return h.hexdigest()[:10]

def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT, ignore=shutil.ignore_patterns("media.json", "wordmark.path.txt", "LICENSE-*"))
    # Minify the shipped CSS and JS; the readable sources stay in static/.
    try:
        import rcssmin, rjsmin
        for f in (OUT / "css").glob("*.css"):
            f.write_text(rcssmin.cssmin(f.read_text(encoding="utf-8")), encoding="utf-8")
        for f in (OUT / "js").glob("*.js"):
            f.write_text(rjsmin.jsmin(f.read_text(encoding="utf-8")), encoding="utf-8")
    except ImportError:
        print("note: rcssmin/rjsmin not installed, shipping unminified CSS and JS")
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=False, lstrip_blocks=False)

    @pass_context
    def link(ctx, path, anchor=""):
        page = ctx["page"]
        if "#" in path and not anchor:
            path, frag = path.split("#", 1)
            anchor = "#" + frag
        if page.get("absolute"):
            return path + anchor
        target = rel(page["route"], path)
        if PREVIEW and target.endswith("/"):
            target += "index.html"
        return target + anchor

    @pass_context
    def asset(ctx, path):
        page = ctx["page"]
        if page.get("absolute"):
            return "/" + path
        return rel(page["route"], "/") + path if rel(page["route"], "/") != "./" else path

    env.globals.update(
        SITE=SITE, CATALOG=CATALOG, MEDIA=MEDIA, WORDMARK=WORDMARK, YT_FAQ=YT_FAQ,
        REEL_CUES=REEL_CUES, REEL_LABELS=REEL_LABELS, YEAR=updated.year, BUILD_ID=build_id(),
        JS_CONFIG={"formExtra": SITE["form"].get("extra_fields") or {}}, PREFILL_SERVICE=None,
        link=link, asset=asset, abs_url=lambda p: SITE["url"] + p,
    )
    for page in PAGES:
        tpl = env.get_template(page["template"])
        ctx = {"page": page, "CASE": CASES[page.get("case", "the-simple-proof")]}
        html = tpl.render(**ctx)
        html = re.sub(r"\n\s*\n+", "\n", html)
        p = out_path(page["route"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")

    if not PREVIEW:
        urls = "".join(f"  <url><loc>{SITE['url']}{pg['route']}</loc><lastmod>{SITE['updated']}</lastmod></url>\n"
                       for pg in PAGES if not pg["route"].endswith(".html"))
        (OUT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
        (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE['url']}/sitemap.xml\n")
        (OUT / "CNAME").write_text(SITE["url"].split("//", 1)[1] + "\n")
        (OUT / ".nojekyll").write_text("")

    bad = []
    for f in OUT.rglob("*"):
        if f.suffix in {".html", ".css", ".js", ".xml", ".txt", ".json"} and f.is_file():
            t = f.read_text(encoding="utf-8", errors="ignore")
            for ch in ("—", "–"):
                if ch in t:
                    bad.append(f"{f.relative_to(OUT)}: {t.count(ch)} x U+{ord(ch):04X}")
    if bad:
        sys.exit("Dash check failed:\n" + "\n".join(bad))
    n = sum(1 for _ in OUT.rglob("*.html"))
    print(f"built {n} pages into {OUT.relative_to(ROOT)} (preview={PREVIEW})")

if __name__ == "__main__":
    main()
