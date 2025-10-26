import httpx
import asyncio
from datetime import datetime, timedelta
from auth.selenium_login import get_stealthwriter_cookies
from aws.integration import get_target_credentials
from utils.helpers import structured_log

class MasterSessionManager:
    def __init__(self):
        self._client = None
        self._lock = asyncio.Lock()
        self._last_refresh = None
        self._refresh_interval = timedelta(minutes=50)  # Refresh before 1hr timeout
        self._is_refreshing = False
        
    async def _create_fresh_client(self):
        """Create a new authenticated client using Selenium"""
        structured_log("Creating fresh authenticated session")
        credentials = get_target_credentials()
        
        # Get cookies from Selenium (runs Cloudflare bypass)
        cookies = get_stealthwriter_cookies(
            credentials["username"], 
            credentials["password"]
        )
        
        # Build cookie jar
        jar = httpx.Cookies()
        for cookie in cookies:
            jar.set(
                cookie["name"], 
                cookie["value"], 
                domain=cookie.get("domain"), 
                path=cookie.get("path")
            )
        
        # Headers that mimic a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
        
        client = httpx.AsyncClient(
            headers=headers,
            cookies=jar,
            follow_redirects=True,
            timeout=30.0
        )
        
        self._last_refresh = datetime.now()
        structured_log("Fresh session created successfully")
        return client
    
    async def _should_refresh(self):
        """Check if session needs refresh"""
        if self._last_refresh is None:
            return True
        return datetime.now() - self._last_refresh > self._refresh_interval
    
    async def _refresh_session(self):
        """Refresh the session in background"""
        if self._is_refreshing:
            return
            
        self._is_refreshing = True
        try:
            structured_log("Refreshing master session")
            new_client = await self._create_fresh_client()
            
            # Close old client
            if self._client:
                await self._client.aclose()
            
            self._client = new_client
            structured_log("Master session refreshed successfully")
        except Exception as e:
            structured_log(f"Session refresh failed: {str(e)}")
            raise
        finally:
            self._is_refreshing = False
    
    async def get_client(self):
        """Get the master authenticated client"""
        async with self._lock:
            # Create initial client if needed
            if self._client is None:
                self._client = await self._create_fresh_client()
                return self._client
            
            # Check if refresh is needed
            if await self._should_refresh():
                await self._refresh_session()
            
            return self._client
    
    async def close(self):
        """Close the client connection"""
        async with self._lock:
            if self._client:
                await self._client.aclose()
                self._client = None
                structured_log("Master session closed")

# Global instance
_master_session_manager = MasterSessionManager()

async def get_authenticated_client():
    """Dependency for FastAPI routes"""
    return await _master_session_manager.get_client()

async def close_master_session():
    """Cleanup function for application shutdown"""
    await _master_session_manager.close()
