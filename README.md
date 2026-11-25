# ilverastudios.com

The ILVERA Studios website: a static site generated from plain content files.

## Edit the words

All copy lives in `content/`, so edits never touch code:

| File | What's in it |
| --- | --- |
| `content/site.yaml` | Email, links, form service, booking link, analytics |
| `content/catalog.yaml` | Services, packages, work, originals, founders |
| `content/case_studies.yaml` | Case studies (one entry per case study page) |
| `content/youtube_faq.yaml` | Questions on the YouTube production page |

## Build

```
pip install jinja2 pyyaml rcssmin rjsmin
python3 build.py            # production build into dist/
python3 build.py --preview  # preview build into dist-preview/ (links end in index.html)
```

The build stops if an en or em dash appears in any page.

## Switch things on

In `content/site.yaml`:

- `form.endpoint`: the address from Formspree or Web3Forms. Until it's set, the form hands the message to the visitor's email app, with a Copy button as backup.
- `booking_url`: a Calendly or Cal.com link. Empty means no booking button.
- `analytics`: `provider: plausible` or `umami`, plus `script_src` and `site_id`. Update the privacy notice the same day.

## Deploy (GitHub Pages)

`dist/` already contains `CNAME` (ilverastudios.com), `.nojekyll`, `sitemap.xml` and `robots.txt`. Publish the contents of `dist/` with GitHub Pages, set the custom domain to ilverastudios.com and enforce HTTPS.

DNS at the registrar: four A records for `@` pointing to 185.199.108.153, 185.199.109.153, 185.199.110.153 and 185.199.111.153, and a CNAME record for `www` pointing to the GitHub Pages address. Leave email records (MX, SPF, DKIM, DMARC) as they are.

## Tools

- `tools/media.py`: cuts the reel, previews, clips and stills from source footage (needs ffmpeg and the source files)
- `tools/og.py`: renders the social preview images and icons (needs Playwright)
- `tools/qa.py`: layout checks at nine widths, links, ids, console errors, screenshots
- `tools/qa_interact.py`: accessibility scan (axe-core) and interaction tests, including the form

Fonts are under the SIL Open Font License; see `static/fonts/LICENSE.txt`.
