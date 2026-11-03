"""Rate-limited HTTP client for the USGS web services.

All requests share one token bucket, so the request rate stays under
`min_interval` seconds between request starts no matter how many threads
call it. A 429 or 5xx response pauses every thread, honours Retry-After
when present, and retries with exponential backoff.
"""

import http.client
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

RETRY_STATUSES = {429, 500, 502, 503, 504}
USER_AGENT = "usgs-batch-script/1.0 (python urllib)"


class RateLimitedClient:
    def __init__(self, min_interval=0.25, max_retries=8, timeout=300, verbose=True):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.verbose = verbose
        self._lock = threading.Lock()
        self._next_allowed = 0.0
        self._pause_until = 0.0
        self.requests = 0
        self.retries = 0
        self.rate_limited = 0

    def _wait_turn(self):
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_allowed, self._pause_until)
            self._next_allowed = start + self.min_interval
        delay = start - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def _pause_all(self, seconds, why):
        with self._lock:
            until = time.monotonic() + seconds
            if until > self._pause_until:
                self._pause_until = until
        if self.verbose:
            print(f"    pausing all requests {seconds:.0f}s: {why}", file=sys.stderr)

    def get_json(self, url):
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            self._wait_turn()
            with self._lock:
                self.requests += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code not in RETRY_STATUSES:
                    raise
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = float(retry_after) if retry_after and retry_after.strip().isdigit() else min(300.0, 5.0 * 2 ** (attempt - 1))
                with self._lock:
                    self.retries += 1
                    if e.code == 429:
                        self.rate_limited += 1
                self._pause_all(wait, f"HTTP {e.code}")
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
                    http.client.HTTPException, json.JSONDecodeError) as e:
                last_err = e
                with self._lock:
                    self.retries += 1
                self._pause_all(min(120.0, 2.0 ** attempt), f"{type(e).__name__}: {e}")
        raise RuntimeError(f"gave up after {self.max_retries} attempts on {url}: {last_err}")

    def stats(self):
        return f"requests={self.requests} retries={self.retries} rate_limited={self.rate_limited}"
