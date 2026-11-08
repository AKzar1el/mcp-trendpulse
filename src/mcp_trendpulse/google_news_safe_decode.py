"""Decode Google News RSS links using a caller-provided, IP-pinned Session.

The third-party Google News decoder uses module-level requests.get/post calls,
which bypass TrendPulse's vetted article transport. Keep the small wire
protocol locally so every request uses the same security-reviewed adapter.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urlsplit

from requests import Session
from selectolax.parser import HTMLParser


_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,4096}={0,2}\Z")
_SIGNATURE = re.compile(r"[A-Za-z0-9_.~+/\-=]{1,2048}\Z")
_TIMESTAMP = re.compile(r"[0-9]{1,16}\Z")
_GOOGLE_NEWS_BATCH = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


def _bounded_body(response, max_bytes: int) -> str | None:
    """Reject redirects, HTTP failures and oversized decompressed responses."""
    with response:
        if response.status_code != 200:
            return None
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=16_384):
            total += len(chunk)
            if total > max_bytes:
                return None
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def decode_google_news_url_pinned(
    source_url: str,
    session: Session,
    *,
    timeout: float,
    max_bytes: int = 2_000_000,
) -> dict[str, object]:
    """Return the decoder's status/decoded_url contract, without raw egress.

    The supplied session MUST have trust_env disabled, no proxy and a pinned
    ArticlePinnedHTTPAdapter mounted for HTTP(S). Redirects are never followed.
    """
    try:
        parsed = urlsplit(source_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "news.google.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment
        ):
            return {"status": False, "message": "Invalid Google News URL."}
        parts = parsed.path.rstrip("/").split("/")
        if len(parts) != 4 or parts[1] != "rss" or parts[2] not in ("articles", "read"):
            return {"status": False, "message": "Invalid Google News article path."}
        token = parts[3]
        if not _TOKEN.fullmatch(token):
            return {"status": False, "message": "Invalid Google News article token."}
        if timeout <= 0 or max_bytes <= 0:
            return {"status": False, "message": "Invalid resource budget."}

        signature: str | None = None
        timestamp: str | None = None
        for path in ("articles", "rss/articles"):
            # Never let a redirect or response-supplied URL become a new target.
            url = f"https://news.google.com/{path}/{token}"
            text = _bounded_body(
                session.get(url, timeout=timeout, stream=True, allow_redirects=False),
                max_bytes,
            )
            if text is None:
                continue
            element = HTMLParser(text).css_first("c-wiz > div[jscontroller]")
            if element is None:
                continue
            signature = element.attributes.get("data-n-a-sg")
            timestamp = element.attributes.get("data-n-a-ts")
            if signature and timestamp:
                break
        if (
            not isinstance(signature, str)
            or not isinstance(timestamp, str)
            or not _SIGNATURE.fullmatch(signature)
            or not _TIMESTAMP.fullmatch(timestamp)
        ):
            return {"status": False, "message": "Google News decoding metadata unavailable."}

        payload = [
            "Fbv4je",
            f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{token}",{timestamp},"{signature}"]',
        ]
        text = _bounded_body(
            session.post(
                _GOOGLE_NEWS_BATCH,
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                data=f"f.req={quote(json.dumps([[payload]]))}",
                timeout=timeout,
                stream=True,
                allow_redirects=False,
            ),
            max_bytes,
        )
        if text is None:
            return {"status": False, "message": "Google News batch response unavailable."}
        frames = text.split("\n\n", 1)
        if len(frames) != 2:
            return {"status": False, "message": "Google News batch response malformed."}
        data = json.loads(frames[1])
        decoded = json.loads(data[0][2])[1]
        if not isinstance(decoded, str) or urlsplit(decoded).scheme not in ("http", "https"):
            return {"status": False, "message": "Google News article URL invalid."}
        return {"status": True, "decoded_url": decoded}
    except Exception:
        # Fail closed on DNS, proxy, TLS, parsing or budget errors. Do not log
        # signed URLs, response bodies or backend exception details.
        return {"status": False, "message": "Google News decoding unavailable."}
