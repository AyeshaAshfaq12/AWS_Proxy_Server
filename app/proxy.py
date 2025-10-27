import httpx
from typing import Dict, List, Tuple
from fastapi import Request
from starlette.responses import Response
from bs4 import BeautifulSoup
from .config import Config, parse_cookie_string

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def filter_request_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP_HEADERS or lk == "host":
            continue
        # Remove any headers that could leak client identity to target
        if lk.startswith("x-forwarded-") or lk.startswith("x-real-"):
            continue
        out[k] = v
    # Add a sensible User-Agent if none
    if "user-agent" not in {h.lower() for h in out}:
        out["User-Agent"] = "aws-proxy-server/1.0"
    return out


def filter_response_headers(headers: httpx.Headers) -> List[Tuple[str, str]]:
    out = []
    for k, v in headers.items():
        if k.lower() in HOP_BY_HOP_HEADERS:
            continue
        # We do not forward set-cookie to clients (session stays server-side)
        if k.lower() == "set-cookie":
            continue
        # Avoid leaking target host header
        if k.lower() == "content-length":
            # let Response compute it
            continue
        out.append((k, v))
    return out


def rewrite_html_links(html: str, target_base: str, proxy_base: str) -> str:
    # Lightweight rewrite using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # attributes that contain URLs
    url_attrs = ["href", "src", "action", "data-src", "data-href"]
    
    # Extract domain from URLs for protocol-relative matching
    target_domain = target_base.replace("https://", "").replace("http://", "")
    proxy_domain = proxy_base.replace("https://", "").replace("http://", "")
    
    for tag in soup.find_all(True):
        for attr in url_attrs:
            val = tag.get(attr)
            if not val:
                continue
            # Only rewrite absolute links to the target domain
            if val.startswith(target_base):
                # replace target base with proxy base
                new = val.replace(target_base, proxy_base)
                tag[attr] = new
            elif val.startswith("//" + target_domain):
                # handle protocol-relative
                tag[attr] = val.replace("//" + target_domain, proxy_domain)
    return str(soup)


def _extract_domain(url: str) -> str:
    """Extract domain from URL by removing protocol and path."""
    return url.replace("https://", "").replace("http://", "").split("/")[0]


class ProxyClient:
    def __init__(self, cookie_string: str):
        self.target = Config.TARGET_BASE_URL.rstrip("/")
        self.proxy_base = Config.PROXY_BASE_URL.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
        self.set_cookies_from_string(cookie_string)

    def set_cookies_from_string(self, cookie_string: str):
        cookies = parse_cookie_string(cookie_string)
        # Clear then set
        jar = httpx.Cookies()
        for k, v in cookies.items():
            jar.set(k, v, domain=_extract_domain(self.target), path="/")
        # assign cookies to client using public API
        self._client.cookies = jar

    async def proxy_request(self, request: Request, path: str):
        method = request.method
        target_url = f"{self.target}/{path}" if path else self.target + "/"
        # Clean headers
        incoming_headers = {k: v for k, v in request.headers.items()}
        headers = filter_request_headers(incoming_headers)

        content = await request.body()
        params = dict(request.query_params)

        try:
            resp = await self._client.request(method, target_url, headers=headers, params=params, content=content)
        except httpx.RequestError as e:
            return Response(content=f"Upstream request failed: {str(e)}", status_code=502)
        
        # Prepare response content and headers
        content_type = resp.headers.get("content-type", "")
        # Optionally rewrite HTML
        body = resp.content
        if "text/html" in content_type:
            try:
                text = resp.text
                rewritten = rewrite_html_links(text, self.target, self.proxy_base)
                body = rewritten.encode(resp.encoding or "utf-8")
            except Exception:
                # if rewriting fails, fall back to raw
                body = resp.content

        headers_filtered = filter_response_headers(resp.headers)
        return Response(content=body, status_code=resp.status_code, headers={k: v for k, v in headers_filtered}, media_type=content_type)
