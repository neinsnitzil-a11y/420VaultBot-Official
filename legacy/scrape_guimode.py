import asyncio, time, itertools
from playwright.async_api import async_playwright
from urllib.parse import urldefrag, urlparse
from collections import deque
from rich.console import Console, Group
from rich.prompt import Prompt
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.rule import Rule
from rich.progress_bar import ProgressBar

# ===== CONFIG =====
MAX_CONCURRENT_PAGES = 6
MAX_RECENT = 25
EVENT_LOG_SIZE = 14

visited = set()
found_links = set()
queue = deque()
recent_links = deque(maxlen=MAX_RECENT)
event_log = deque(maxlen=EVENT_LOG_SIZE)
failed_links = deque(maxlen=10)

console = Console()
start_time = time.time()
pulse = itertools.cycle(["▮", "▯", "▮", "▯"])

SITE_ROOT = None  

# ===== UTILS =====
def normalize(url):
    url, _ = urldefrag(url)
    return url.rstrip("/")

def log_event(msg, style="white"):
    event_log.appendleft(Text(f"[{time.strftime('%H:%M:%S')}] {msg}", style))

def threat_level():
    q = len(queue)
    if q < 10: return ("LOW", "green")
    if q < 50: return ("MED", "yellow")
    return ("HIGH", "red")

def hacker_banner():
    banner = Text(
"""┌────────────────────────────────────────────────────────────────┐
│__________.__                 __      _________.__  __          │
│\\______   \\  | _____    ____ |  | __ /   _____/|__|/  |_  ____  │
│ |    |  _/  | \\__  \\ _/ ___\\|  |/ / \\_____  \\ |  \\   __\\/ __ \\ │
│ |    |   \\  |__/ __ \\\\  \\___|    <  /        \\|  ||  | \\  ___/ │
│ |______  /____(____  /\\___  >__|_ \\/_______  /|__||__|  \\___  >│
│        \\/          \\/     \\/     \\/        \\/               \\/ │
│  _________                                                     │
│ /   _____/ ________________  ______   ___________              │
│ \\_____  \\_/ ___\\_  __ \\__  \\ \\____ \\_/ __ \\_  __ \\             │
│ /        \\  \\___|  | \\// __ \\|  |_> >  ___/|  | \\/             │
│/_______  /\\___  >__|  (____  /   __/ \\___  >__|                │
│        \\/     \\/           \\/|__|        \\/                    │
└────────────────────────────────────────────────────────────────┘
""",
        style="bold green",
        justify="center"
    )
    return Align.center(banner)

# ===== PLAYWRIGHT =====
async def crawl_page(browser, url):
    page = await browser.new_page(
        ignore_https_errors=True,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
        }
    )

    try:
        # Retry normal navigation once. This helps with transient connection,
        # TLS, or HTTP protocol errors without changing the crawl behavior.
        last_error = None

        for attempt in range(2):
            try:
                await page.goto(
                    url,
                    timeout=45000,
                    wait_until="domcontentloaded"
                )

                try:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=7000
                    )
                except:
                    # networkidle is not required for a page to be crawlable.
                    pass

                await page.wait_for_timeout(1000)
                break

            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    await page.wait_for_timeout(1500)
                else:
                    raise

        # Extract normal links plus image-map links.
        links = await page.eval_on_selector_all(
            "a[href], area[href]",
            "els => els.map(e => e.href).filter(Boolean)"
        )

        return list(dict.fromkeys(links))

    except Exception as exc:
        failed_links.append(url)

        # The old code swallowed the actual Playwright error, making every
        # navigation failure simply appear as "FAIL". Show the real reason.
        error_text = str(last_error or exc).replace("\\n", " ")
        if len(error_text) > 180:
            error_text = error_text[:177] + "..."

        log_event(f"FAIL {url}", "red")
        log_event(f"REASON {error_text}", "yellow")

        return []

    finally:
        await page.close()

# ===== DASHBOARD =====
def build_dashboard(flash=False):
    layout = Layout()

    layout.split_column(
        Layout(Panel(hacker_banner(), border_style="green"), size=9),
        Layout(name="body")
    )

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right", ratio=2)
    )

    elapsed = time.time() - start_time
    speed = len(found_links) / elapsed if elapsed else 0
    threat, color = threat_level()

    stats = Table.grid(expand=True)
    stats.add_column(justify="left")
    stats.add_column(justify="right")

    stats.add_row("🎯 TARGET", "LOCKED")
    stats.add_row("🧠 VISITED", str(len(visited)))
    stats.add_row("📡 QUEUE", str(len(queue)))
    stats.add_row("🔗 LINKS", str(len(found_links)))
    stats.add_row("⚡ LINKS/SEC", f"{speed:.2f}")
    stats.add_row("🚨 FAILURES", str(len(failed_links)))
    stats.add_row("☣ LOAD", Text(threat, style=f"bold {color}"))

    queue_bar = ProgressBar(total=100, completed=min(len(queue), 100))

    layout["left"].update(
        Panel(
            Group(stats, Rule("QUEUE PRESSURE"), queue_bar),
            title="SYSTEM CORE",
            border_style="bright_blue"
        )
    )

    links_table = Table(show_header=True, expand=True)
    links_table.add_column("LIVE LINK STREAM", style="cyan", overflow="fold")

    for link in recent_links:
        style = "bold bright_green" if flash else "cyan"
        links_table.add_row(Text(link, style=style))

    log_table = Table(show_header=False, expand=True)
    log_table.add_column("EVENT LOG", style="white")
    for event in event_log:
        log_table.add_row(event)

    layout["right"].update(
        Panel(
            Group(links_table, Rule("EVENT TRACE", style="bright_black"), log_table),
            border_style="magenta"
        )
    )
    return layout

# ===== MAIN =====
async def main():
    global SITE_ROOT

    console.clear()
    base_url = Prompt.ask("[bold cyan]Target URL[/bold cyan]", default="https://kits4beats.com")
    output_file = Prompt.ask("[bold cyan]Output file[/bold cyan]", default="links.txt")

    parsed = urlparse(base_url)
    SITE_ROOT = f"{parsed.scheme}://{parsed.netloc}"  

    queue.append(normalize(base_url))
    log_event("SYSTEM ONLINE", "green")
    log_event(f"TARGET ACQUIRED: {base_url}", "cyan")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-http2",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        flash = False
        with Live(build_dashboard(), refresh_per_second=8, console=console) as live:
            while queue:
                batch = []
                while queue and len(batch) < MAX_CONCURRENT_PAGES:
                    url = normalize(queue.popleft())
                    if url in visited:
                        continue
                    visited.add(url)
                    batch.append(url)
                    log_event(f"SCAN {url}", "bright_black")

                results = await asyncio.gather(*[crawl_page(browser, u) for u in batch])

                for links in results:
                    for link in links:
                        # 1. Enforce strict same-domain root restriction.
                        #    Compare hostnames instead of string-prefix matching
                        #    so a different host cannot accidentally qualify.
                        link_parts = urlparse(link)
                        root_parts = urlparse(SITE_ROOT)

                        if (
                            link_parts.scheme not in ("http", "https")
                            or link_parts.hostname != root_parts.hostname
                        ):
                            continue

                        # Remove #fragments before duplicate checking.
                        link = normalize(link)

                        # 2. Keep active pagination queries, but filter
                        #    unrelated tracking/query URLs.
                        if "?" in link:
                            if "paged=" not in link and "page=" not in link:
                                continue

                        # 3. Filter asset/download URLs. These aren't HTML pages
                        #    that need to be recursively crawled.
                        if link.lower().endswith((
                            '.zip', '.rar', '.7z', '.pdf',
                            '.png', '.jpg', '.jpeg', '.gif', '.webp',
                            '.mp3', '.wav', '.flac', '.mp4', '.webm',
                            '.css', '.js', '.json', '.xml'
                        )):
                            continue

                        # 4. Filter administrative utility pages.
                        system_paths = [
                            '/about-us', '/contact-us', '/dmca',
                            '/privacy-policy', '/terms-of-service',
                            '/faq', '/broken-links', '/abuse'
                        ]
                        if any(path in link.lower() for path in system_paths):
                            continue

                        # 5. IMPORTANT FIX:
                        #    Previously only "hub" URLs were placed into the
                        #    queue. Normal content/kit URLs were merely saved,
                        #    so their own links were never discovered.
                        #
                        #    Now every valid same-domain HTML URL is queued.
                        if link not in visited and link not in queue:
                            queue.append(link)

                        # 6. Preserve the existing found_links/output behavior.
                        if link not in found_links:
                            found_links.add(link)
                            recent_links.appendleft(link)
                            log_event(
                                f"FOUND KIT {link.replace(SITE_ROOT, '')}",
                                "bold green"
                            )
                            flash = True

                live.update(build_dashboard(flash))
                flash = False

        await browser.close()

    with open(output_file, "w", encoding="utf-8") as f:
        for link in sorted(found_links):
            f.write(link + "\n")

    console.print(
        f"\n[bold green]✔ OPERATION COMPLETE[/bold green] — {len(found_links)} LINKS EXTRACTED"
    )

if __name__ == "__main__":
    asyncio.run(main())
