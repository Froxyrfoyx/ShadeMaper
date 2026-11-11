import os
import asyncio
from urllib.parse import urlparse ,parse_qs
from playwright.async_api import BrowserContext, async_playwright
import random
import os
import asyncio
import random
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
import os
import asyncio
import random
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright

class DomScaner:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, headless=True) -> None:
        if getattr(self, '_initialized', False):
            return
        self.browser_context = None
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.semaphore = asyncio.Semaphore(5)
        self._initialized = True

    def _get_browser_path(self) -> str:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        return os.path.join(
            local_app_data,
            "ms-playwright",
            "chromium_headless_shell-1228",
            "chrome-headless-shell-win64",
            "chrome-headless-shell.exe"
        )

    async def start(self):
        if not self.browser:
            self.playwright = await async_playwright().start()
            executable_path = self._get_browser_path()

            if not os.path.exists(executable_path):
                executable_path = None

            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                executable_path=executable_path,
                args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
            )
            self.browser_context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )

    async def render_page(self, url):
        if url.lower().startswith(('javascript:', 'mailto:', 'tel:')):
                    return None
        if not self.browser:
            await self.start()

        async with self.semaphore:
            page = None
            try:
                page = await self.browser_context.new_page()
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                return await page.content()
            except Exception as e:
                print(f" Ошибка рендеринга страницы {url}: {e}")
                return None
            finally:
                if page:
                    await page.close()



    async def monke_clicks(self, context, content: str, base_url: str, clicks: int = 15):
       fparams = set()
       cdata = {}
       page = await context.new_page()

       parsed_base = urlparse(base_url)
       base_host = parsed_base.netloc

       ignored_extensions = (
           '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
           '.ico', '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.webm'
       )

       async def handle_req(req):
           try:
               req_url = req.url
               if not req_url or req_url.lower().startswith('javascript:'):
                   return

               parsed = urlparse(req_url)
               if parsed.netloc != base_host and not parsed.netloc.endswith('.' + base_host):
                   return

               if parsed.path.lower().endswith(ignored_extensions):
                   return

               if parsed.query:
                   params = parse_qs(parsed.query)
                   for param, vals in params.items():
                       if param not in fparams:
                           fparams.add(param)
                           cdata[param] = vals
           except Exception as e:
               print(f"Ошибка обработчика запроса: {e}")

       page.on("request", handle_req)

       try:
           await page.set_content(content, wait_until="domcontentloaded")

           for _ in range(clicks):
               try:
                   selectors = (
                       "button:not([data-monked]), "
                       "a:not([data-monked]), "
                       "[role='button']:not([data-monked]), "
                       ".btn:not([data-monked]), "
                       ".button:not([data-monked]), "
                       "input[type='submit']:not([data-monked])"
                   )
                   elements = await page.query_selector_all(selectors)
                   if not elements:
                       break

                   valid_elements = []
                   for el in elements:
                       if await el.is_visible() and await el.is_enabled():
                           valid_elements.append(el)

                   if not valid_elements:
                       break

                   target = random.choice(valid_elements)
                   await target.evaluate("el => el.setAttribute('data-monked', 'true')")
                   tag_name = await target.evaluate("el => el.tagName")

                   if tag_name == "A":
                       href = await target.get_attribute("href")
                       if href:
                           if href.lower().startswith('javascript:'):
                               await target.click(timeout=2500)
                               await asyncio.sleep(0.7)
                               continue

                           parsed_href = urlparse(href)
                           if parsed_href.netloc and parsed_href.netloc != base_host:
                               continue
                       await target.evaluate("el => el.setAttribute('target', '_self')")

                   await target.click(timeout=2500)
                   await asyncio.sleep(0.7)

                   current_page_url = page.url
                   if not current_page_url or current_page_url.lower().startswith('javascript:'):
                       continue

                   parsed_page_url = urlparse(current_page_url)
                   if parsed_page_url.netloc == base_host and parsed_page_url.query:
                       page_params = parse_qs(parsed_page_url.query)
                       for param, values in page_params.items():
                           if param not in fparams:
                               fparams.add(param)
                               cdata[param] = values
               except Exception:
                   pass
       finally:
           try:
               page.remove_listener("request", handle_req)
           except Exception:
               pass
           await page.close()

       print(f"Успешно собрано уникальных параметров: {len(cdata)}")
       print(f"Список параметров: {list(cdata.keys())}")
       return cdata


    async def stop(self):
        try:
            if self.browser_context:
                await self.browser_context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        finally:
            self.browser_context = None
            self.browser = None
            self.playwright = None

    async def force_close(self):
        await self.stop()
