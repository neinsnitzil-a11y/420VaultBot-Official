import asyncio, csv, json, time, re, sys, argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, parse_qsl, urlencode, urlunparse
from collections import deque
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from rich.console import Console, Group
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.rule import Rule
from rich.progress_bar import ProgressBar

ASSET_EXT = {'.zip','.rar','.7z','.tar','.gz','.bz2','.xz','.dmg','.pkg','.exe','.msi','.iso','.pdf','.txt','.csv','.json','.xml','.mp3','.wav','.flac','.aiff','.m4a','.ogg','.mp4','.mov','.webm','.avi','.jpg','.jpeg','.png','.gif','.webp','.svg','.woff','.woff2','.ttf','.otf','.css','.js'}
DOWNLOAD_HINTS = re.compile(r'(download|mirror|mediafire|mega\.|drive\.google|dropbox|onedrive|gofile|pixeldrain|workupload|sendspace|rapidgator|katfile|uploadgig|1fichier)', re.I)
TRACKING_KEYS = {'utm_source','utm_medium','utm_campaign','utm_term','utm_content','gclid','fbclid','mc_cid','mc_eid'}
SYSTEM_PATH_HINTS = ('/wp-admin','/wp-login','/login','/logout','/register','/cart','/checkout','/my-account')

@dataclass(frozen=True)
class LinkRecord:
    source: str
    url: str
    kind: str
    text: str = ''

class UniversalScraper:
    def __init__(self, start_url, out_dir='scrape_output', concurrency=4, delay=0.6, max_pages=0,
                 max_depth=0, include_subdomains=False, headless=True, obey_robots=True):
        self.start_url = self.normalize(start_url)
        p = urlparse(self.start_url)
        self.root_host = (p.hostname or '').lower()
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.concurrency = max(1, concurrency)
        self.delay = max(0, delay)
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.include_subdomains = include_subdomains
        self.headless = headless
        self.obey_robots = obey_robots
        self.queue = deque([(self.start_url, 0)])
        self.queued = {self.start_url}
        self.visited = set()
        self.records = set()
        self.recent = deque(maxlen=22)
        self.events = deque(maxlen=13)
        self.failures = deque(maxlen=10)
        self.status_counts = {}
        self.started = time.time()
        self.console = Console()
        self.stop_reason = ''
        self.robots_disallow = []

    @staticmethod
    def normalize(url):
        url, _ = urldefrag(url.strip())
        p = urlparse(url)
        if not p.scheme:
            url = 'https://' + url
            p = urlparse(url)
        query = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in TRACKING_KEYS]
        path = re.sub(r'/+', '/', p.path or '/')
        if path != '/': path = path.rstrip('/')
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, '', urlencode(query, doseq=True), ''))

    def allowed_host(self, url):
        h = (urlparse(url).hostname or '').lower()
        return h == self.root_host or (self.include_subdomains and h.endswith('.' + self.root_host))

    def log(self, msg, style='white'):
        self.events.appendleft(Text(f"[{time.strftime('%H:%M:%S')}] {msg}", style))

    def classify(self, url, text='', content_type=''):
        p = urlparse(url); path = p.path.lower()
        ext = Path(path).suffix.lower()
        if ext in ASSET_EXT:
            if ext in {'.zip','.rar','.7z','.tar','.gz','.bz2','.xz','.dmg','.pkg','.exe','.msi','.iso'}: return 'download'
            if ext in {'.mp3','.wav','.flac','.aiff','.m4a','.ogg','.mp4','.mov','.webm','.avi'}: return 'media'
            if ext in {'.jpg','.jpeg','.png','.gif','.webp','.svg'}: return 'image'
            return 'asset'
        if not self.allowed_host(url):
            return 'external_download' if DOWNLOAD_HINTS.search(url + ' ' + text) else 'external'
        if re.search(r'/page/\d+/?$', path) or re.search(r'(^|[?&])(page|paged)=\d+', p.query): return 'pagination'
        if any(x in path for x in ('/category/','/tag/','/archive/','/collections','/presets','/plugins','/kits','/samples')): return 'archive'
        if DOWNLOAD_HINTS.search(text): return 'download_link'
        return 'page'

    def crawlable(self, url, kind):
        if not self.allowed_host(url): return False
        if kind in {'download','media','image','asset','external','external_download'}: return False
        return not any(x in urlparse(url).path.lower() for x in SYSTEM_PATH_HINTS)

    async def load_robots(self, context):
        if not self.obey_robots: return
        page = await context.new_page()
        try:
            u = f"{urlparse(self.start_url).scheme}://{urlparse(self.start_url).netloc}/robots.txt"
            r = await page.goto(u, wait_until='domcontentloaded', timeout=15000)
            if r and r.ok:
                body = await page.locator('body').inner_text()
                active = False
                for raw in body.splitlines():
                    line = raw.split('#',1)[0].strip()
                    if ':' not in line: continue
                    k,v = [x.strip() for x in line.split(':',1)]
                    if k.lower() == 'user-agent': active = v == '*'
                    elif active and k.lower() == 'disallow' and v: self.robots_disallow.append(v)
                self.log(f"ROBOTS loaded ({len(self.robots_disallow)} rules)", 'cyan')
        except Exception:
            self.log('ROBOTS unavailable; continuing conservatively', 'yellow')
        finally: await page.close()

    def robots_allowed(self, url):
        if not self.obey_robots: return True
        path = urlparse(url).path or '/'
        return not any(path.startswith(x) for x in self.robots_disallow)

    async def crawl_page(self, context, url, depth):
        page = await context.new_page()
        try:
            await asyncio.sleep(self.delay)
            response = await page.goto(url, timeout=45000, wait_until='domcontentloaded')
            status = response.status if response else 0
            self.status_counts[status] = self.status_counts.get(status,0)+1
            if status in (401,403,429):
                self.failures.append(url); self.log(f"BLOCKED {status} {url}", 'yellow'); return []
            if status >= 400:
                self.failures.append(url); self.log(f"HTTP {status} {url}", 'red'); return []
            try: await page.wait_for_load_state('networkidle', timeout=5000)
            except Exception: pass
            ctype = (response.headers.get('content-type','') if response else '').lower()
            if 'html' not in ctype and ctype:
                return []
            title = (await page.title()).strip()
            self.log(f"OK {status} {title[:55] or url}", 'green')
            rows = await page.locator('a[href], area[href]').evaluate_all("""els => els.map(e => ({href:e.href, text:(e.innerText||e.getAttribute('aria-label')||e.title||'').trim()}))""")
            return rows
        except PlaywrightTimeoutError:
            self.failures.append(url); self.log(f"TIMEOUT {url}", 'red'); return []
        except Exception as exc:
            self.failures.append(url); self.log(f"FAIL {url} :: {str(exc)[:100]}", 'red'); return []
        finally:
            await page.close()

    def add_record(self, source, url, text=''):
        try: url = self.normalize(url)
        except Exception: return
        if urlparse(url).scheme not in ('http','https'): return
        kind = self.classify(url, text)
        rec = LinkRecord(source, url, kind, re.sub(r'\s+',' ',text)[:300])
        if rec not in self.records:
            self.records.add(rec); self.recent.appendleft((kind,url)); self.log(f"FOUND {kind.upper()} {url[:100]}", 'bright_green')
        return kind, url

    def banner(self):
        return Align.center(Text("UNIVERSAL LINK SCRAPER\nPLAYWRIGHT DISCOVERY ENGINE", style='bold green'))

    def dashboard(self):
        layout=Layout(); layout.split_column(Layout(Panel(self.banner(),border_style='green'),size=5),Layout(name='body'))
        layout['body'].split_row(Layout(name='left'),Layout(name='right',ratio=2))
        elapsed=max(time.time()-self.started,.001); stats=Table.grid(expand=True); stats.add_column(); stats.add_column(justify='right')
        for a,b in [('TARGET',self.root_host),('VISITED',len(self.visited)),('QUEUE',len(self.queue)),('LINKS',len(self.records)),('LINKS/SEC',f'{len(self.records)/elapsed:.2f}'),('FAILURES',len(self.failures))]: stats.add_row(str(a),str(b))
        bar=ProgressBar(total=100,completed=min(len(self.queue),100)); layout['left'].update(Panel(Group(stats,Rule('QUEUE PRESSURE'),bar),title='SYSTEM CORE',border_style='bright_blue'))
        lt=Table(show_header=True,expand=True); lt.add_column('LIVE LINK STREAM',overflow='fold')
        for kind,u in self.recent: lt.add_row(Text(f'[{kind}] {u}',style='cyan'))
        ev=Table(show_header=False,expand=True); ev.add_column('EVENT TRACE')
        for e in self.events: ev.add_row(e)
        layout['right'].update(Panel(Group(lt,Rule('EVENT TRACE'),ev),border_style='magenta')); return layout

    def save(self):
        rows=sorted((asdict(r) for r in self.records), key=lambda x:(x['kind'],x['url'],x['source']))
        with open(self.out/'links.csv','w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=['source','url','kind','text']); w.writeheader(); w.writerows(rows)
        (self.out/'links.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
        groups={}
        for r in rows: groups.setdefault(r['kind'],[]).append(r['url'])
        for kind,urls in groups.items(): (self.out/f'{kind}_links.txt').write_text('\n'.join(sorted(set(urls)))+'\n',encoding='utf-8')
        (self.out/'visited.txt').write_text('\n'.join(sorted(self.visited))+'\n',encoding='utf-8')
        (self.out/'failed.txt').write_text('\n'.join(self.failures)+'\n',encoding='utf-8')
        summary={'start_url':self.start_url,'visited':len(self.visited),'records':len(self.records),'queued_remaining':len(self.queue),'status_counts':self.status_counts,'elapsed_seconds':round(time.time()-self.started,2),'stop_reason':self.stop_reason}
        (self.out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

    async def run(self):
        self.log('SYSTEM ONLINE','green'); self.log(f'TARGET ACQUIRED {self.start_url}','cyan')
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=self.headless)
            context=await browser.new_context(ignore_https_errors=True, viewport={'width':1440,'height':900})
            await self.load_robots(context)
            with Live(self.dashboard(),refresh_per_second=6,console=self.console) as live:
                while self.queue:
                    if self.max_pages and len(self.visited)>=self.max_pages: self.stop_reason='max_pages'; break
                    batch=[]
                    while self.queue and len(batch)<self.concurrency:
                        u,d=self.queue.popleft(); self.queued.discard(u)
                        if u in self.visited: continue
                        if self.max_depth and d>self.max_depth: continue
                        if not self.robots_allowed(u): self.log(f'ROBOTS SKIP {u}','yellow'); continue
                        self.visited.add(u); batch.append((u,d)); self.log(f'SCAN depth={d} {u}','bright_black')
                    if not batch: continue
                    results=await asyncio.gather(*(self.crawl_page(context,u,d) for u,d in batch))
                    for (source,depth),links in zip(batch,results):
                        for item in links:
                            href=item.get('href',''); text=item.get('text','')
                            result=self.add_record(source,href,text)
                            if not result: continue
                            kind,u=result
                            if self.crawlable(u,kind) and u not in self.visited and u not in self.queued:
                                if not self.max_depth or depth+1<=self.max_depth:
                                    self.queue.append((u,depth+1)); self.queued.add(u)
                    self.save(); live.update(self.dashboard())
            await context.close(); await browser.close()
        self.save(); self.console.print(f"\n[bold green]✔ COMPLETE[/bold green] — {len(self.records)} links | {len(self.visited)} pages | output: {self.out}")

def parse_args():
    ap=argparse.ArgumentParser(description='Universal public-site link discovery crawler')
    ap.add_argument('url',nargs='?'); ap.add_argument('--output',default='scrape_output'); ap.add_argument('--concurrency',type=int,default=4); ap.add_argument('--delay',type=float,default=.6); ap.add_argument('--max-pages',type=int,default=0); ap.add_argument('--max-depth',type=int,default=0); ap.add_argument('--include-subdomains',action='store_true'); ap.add_argument('--headed',action='store_true'); ap.add_argument('--ignore-robots',action='store_true')
    return ap.parse_args()

async def amain():
    a=parse_args(); console=Console(); url=a.url
    if not url:
        console.clear(); console.print(Panel('[bold green]UNIVERSAL LINK SCRAPER[/bold green]\nPublic-page recursive discovery',border_style='green'))
        url=Prompt.ask('[bold cyan]Target URL[/bold cyan]')
        a.output=Prompt.ask('[bold cyan]Output folder[/bold cyan]',default=a.output)
        a.concurrency=IntPrompt.ask('[bold cyan]Concurrent pages[/bold cyan]',default=a.concurrency)
        a.include_subdomains=Confirm.ask('[bold cyan]Include subdomains?[/bold cyan]',default=False)
        a.headed=Confirm.ask('[bold cyan]Show browser?[/bold cyan]',default=False)
    s=UniversalScraper(url,a.output,a.concurrency,a.delay,a.max_pages,a.max_depth,a.include_subdomains,not a.headed,not a.ignore_robots)
    try: await s.run()
    except KeyboardInterrupt:
        s.stop_reason='user_interrupt'; s.save(); console.print('\n[yellow]Stopped safely; current results saved.[/yellow]')

if __name__=='__main__':
    try: asyncio.run(amain())
    except KeyboardInterrupt: pass
