# Universal Plugin-Site Link Scraper

A Playwright + Rich recursive crawler modeled after the supplied dashboard scraper, generalized for public websites.

## Install (Windows)
Double-click `install.bat` once. Then double-click `run_scraper.bat`.

## CLI
```powershell
python universal_scraper.py https://example.com --output example_results
python universal_scraper.py https://example.com --max-pages 100 --delay 1.0
python universal_scraper.py https://example.com --include-subdomains --headed
```

`--max-pages 0` and `--max-depth 0` mean unlimited. Default concurrency is 4. The crawler respects robots.txt by default. `--ignore-robots` exists for sites you own/control or where you have permission; it does not bypass authentication, CAPTCHA, anti-bot challenges, paywalls, or access controls.

## What it does
- Recursively follows public same-domain HTML pages.
- Optional subdomain recursion.
- Uses Chromium via Playwright for JavaScript-rendered links.
- Records anchor text and the source page for every discovered HTTP(S) link.
- Classifies links as page, archive, pagination, download, media, image, asset, external, external_download, or download_link.
- Binary/download links are recorded, not recursively opened.
- 401/403/429 are logged as blocked instead of treated as successful pages.
- Saves after every crawl batch, so Ctrl+C loses very little work.
- Removes fragments and common tracking query parameters.

## Output
`links.csv` and `links.json` contain source URL, discovered URL, classification and anchor text. Separate `<kind>_links.txt` files are generated automatically, plus `visited.txt`, `failed.txt`, and `summary.json`.

## Scope
This is a discovery/indexing crawler. It does not defeat CAPTCHA/Cloudflare challenges, authentication, paywalls, countdown/access controls, or other restrictions. Respect site terms, robots.txt, copyright, and server capacity.
