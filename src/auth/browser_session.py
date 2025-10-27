import asyncio
import json
import os
import time
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Optional, Dict, Any

class BrowserSession:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self._lock = asyncio.Lock()
        self._last_activity = 0
        self._session_timeout = int(os.getenv("SESSION_TIMEOUT", 3600))

    async def start(self):
        """Start the browser session"""
        async with self._lock:
            if self.browser:
                return
            
            self.playwright = await async_playwright().start()
            
            # Launch browser with stealth settings
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps',
                    '--disable-component-extensions-with-background-pages',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-web-security',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection'
                ]
            )
            
            # Create context with stealth settings
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
            )
            
            # Add stealth script
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                window.chrome = {
                    runtime: {},
                };
            """)
            
            self.page = await self.context.new_page()
            self._last_activity = time.time()
            print("🚀 Browser session started successfully")

    async def load_cookies(self):
        """Load cookies from manual_cookies.json"""
        try:
            PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            COOKIES_FILE = os.path.join(PROJECT_ROOT, "manual_cookies.json")
            
            if not os.path.exists(COOKIES_FILE):
                print("❌ manual_cookies.json file not found")
                return False
                
            with open(COOKIES_FILE, "r") as f:
                cookies_data = json.load(f)
            
            cookies = cookies_data.get("cookies", [])
            if not cookies:
                print("❌ No cookies found in file")
                return False
            
            # Convert cookies to Playwright format and fix sameSite values
            playwright_cookies = []
            for cookie in cookies:
                # Fix sameSite value - capitalize first letter
                same_site = cookie.get('sameSite', 'Lax')
                if same_site.lower() == 'lax':
                    same_site = 'Lax'
                elif same_site.lower() == 'strict':
                    same_site = 'Strict'
                elif same_site.lower() == 'none':
                    same_site = 'None'
                
                playwright_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie.get('domain', 'app.stealthwriter.ai'),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', True),
                    'httpOnly': cookie.get('httpOnly', False),
                    'sameSite': same_site
                }
                
                if 'expirationDate' in cookie:
                    playwright_cookie['expires'] = int(cookie['expirationDate'])
                
                playwright_cookies.append(playwright_cookie)
            
            await self.context.add_cookies(playwright_cookies)
            print(f"✅ Loaded {len(playwright_cookies)} cookies into browser")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load cookies: {e}")
            return False

    async def navigate_to_page(self, url: str) -> Dict[str, Any]:
        """Navigate to a page and return response details"""
        try:
            if not self.page:
                await self.start()
            
            self._last_activity = time.time()
            
            # Navigate to page with longer timeout and different wait strategy
            response = await self.page.goto(
                url, 
                wait_until='domcontentloaded',  # Changed from 'networkidle' to 'domcontentloaded'
                timeout=60000  # Increased timeout to 60 seconds
            )
            
            # Wait a bit for any dynamic content
            await asyncio.sleep(2)
            
            # Check for Cloudflare challenge
            page_content = await self.page.content()
            if "challenge-platform" in page_content.lower() or "checking your browser" in page_content.lower():
                print("⚠️ Cloudflare challenge detected, waiting...")
                await asyncio.sleep(10)  # Wait longer for challenge to complete
                page_content = await self.page.content()
            
            return {
                'status_code': response.status if response else 200,
                'content': page_content,
                'url': self.page.url,
                'headers': dict(response.headers) if response else {}
            }
            
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return {
                'status_code': 500,
                'content': f"<html><body><h1>Navigation Error</h1><p>{str(e)}</p></body></html>",
                'url': url,
                'headers': {}
            }

    async def make_request(self, method: str, url: str, headers: dict = None, data: bytes = None) -> Dict[str, Any]:
        """Make a request using the browser"""
        try:
            if not self.page:
                await self.start()
            
            self._last_activity = time.time()
            
            # For simple GET requests, just navigate
            if method.upper() == 'GET' and not data:
                return await self.navigate_to_page(url)
            
            # For other requests, use page.evaluate with fetch
            fetch_options = {
                'method': method,
                'headers': headers or {}
            }
            
            if data:
                fetch_options['body'] = data.decode('utf-8', errors='ignore')
            
            result = await self.page.evaluate("""
                async ({ url, options }) => {
                    try {
                        const response = await fetch(url, options);
                        const text = await response.text();
                        return {
                            status: response.status,
                            content: text,
                            headers: Object.fromEntries(response.headers.entries())
                        };
                    } catch (error) {
                        return {
                            status: 500,
                            content: `<html><body><h1>Fetch Error</h1><p>${error.message}</p></body></html>`,
                            headers: {}
                        };
                    }
                }
            """, {'url': url, 'options': fetch_options})
            
            return {
                'status_code': result['status'],
                'content': result['content'],
                'url': url,
                'headers': result['headers']
            }
            
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return {
                'status_code': 500,
                'content': f"<html><body><h1>Request Error</h1><p>{str(e)}</p></body></html>",
                'url': url,
                'headers': {}
            }

    async def is_expired(self) -> bool:
        """Check if session has expired"""
        return time.time() - self._last_activity > self._session_timeout

    async def close(self):
        """Close the browser session"""
        async with self._lock:
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            print("🔒 Browser session closed")

# Global browser session instance
_browser_session: Optional[BrowserSession] = None
_browser_lock = asyncio.Lock()

async def get_browser_session() -> BrowserSession:
    """Get or create the global browser session"""
    global _browser_session
    async with _browser_lock:
        if _browser_session is None or await _browser_session.is_expired():
            if _browser_session:
                await _browser_session.close()
            
            _browser_session = BrowserSession()
            await _browser_session.start()
            await _browser_session.load_cookies()
        
        return _browser_session

async def refresh_browser_session():
    """Force refresh the browser session"""
    global _browser_session
    async with _browser_lock:
        if _browser_session:
            await _browser_session.close()
        
        _browser_session = BrowserSession()
        await _browser_session.start()
        await _browser_session.load_cookies()
        return _browser_session
