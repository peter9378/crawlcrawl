import logging
import json
import os
import random
import re
import socket
import struct
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


class Scraper:
    YOUTUBE_HOSTS = ("www.youtube.com", "youtube.com", "m.youtube.com")
    PUBLIC_DNS_SERVERS = ("8.8.8.8", "1.1.1.1", "9.9.9.9")
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    SEARCH_INPUT_SELECTORS = (
        "input[name='search_query'], "
        "input#search, "
        "input.ytSearchboxComponentInput, "
        "ytd-searchbox input, "
        "yt-searchbox input, "
        "form[role='search'] input"
    )

    def __init__(self):
        self.logger = logging.getLogger("uvicorn")
        self.chrome_executable = os.getenv("PLAYWRIGHT_CHROME_EXECUTABLE", "/usr/bin/google-chrome")
        self.headless = os.getenv("PLAYWRIGHT_HEADLESS", "1") != "0"
        self.launch_timeout_ms = int(os.getenv("PLAYWRIGHT_LAUNCH_TIMEOUT_MS", "20000"))
        self.navigation_timeout_ms = int(os.getenv("PLAYWRIGHT_NAVIGATION_TIMEOUT_MS", "15000"))
        self.input_timeout_ms = int(os.getenv("PLAYWRIGHT_INPUT_TIMEOUT_MS", "10000"))
        self.suggestion_timeout_ms = int(os.getenv("PLAYWRIGHT_SUGGESTION_TIMEOUT_MS", "3500"))
        self.navigation_retries = int(os.getenv("PLAYWRIGHT_NAVIGATION_RETRIES", "1"))
        self.crawl_timeout_seconds = int(os.getenv("PLAYWRIGHT_CRAWL_TIMEOUT_SECONDS", "30"))
        self.use_subprocess = (
            os.getenv("PLAYWRIGHT_CRAWL_SUBPROCESS", "1") != "0" and
            os.getenv("YOUTUBE_PLAYWRIGHT_CHILD") != "1"
        )

    def get_suggestions(self, query: str):
        query = (query or "").strip()
        if not query:
            return self._build_suggestion_response(query, [])

        if self.use_subprocess:
            return self._get_suggestions_via_subprocess(query)

        return self._get_suggestions_direct(query)

    def _get_suggestions_direct(self, query: str):
        url = f"https://www.youtube.com/results?search_query={quote(query)}&hl=ko&gl=KR"
        try:
            suggestions = self._crawl_suggestions(query, url)
            result = self._build_suggestion_response(query, suggestions)
            self.logger.info(f"[YOUTUBE] Final suggestion result: {result}")
            return result
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] Playwright suggestion crawl failed for {url}: {e}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=str(e),
            )

    def _get_suggestions_via_subprocess(self, query: str):
        env = os.environ.copy()
        env["YOUTUBE_PLAYWRIGHT_CHILD"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        child_code = (
            "import json, sys; "
            "from scraper import Scraper; "
            "print(json.dumps(Scraper().get_suggestions(sys.argv[1]), ensure_ascii=False))"
        )

        try:
            completed = subprocess.run(
                [sys.executable, "-c", child_code, query],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.crawl_timeout_seconds,
            )
        except subprocess.TimeoutExpired as e:
            detail = f"Playwright subprocess timed out after {self.crawl_timeout_seconds}s"
            stderr = (e.stderr or "").strip()
            if stderr:
                detail = f"{detail}: {stderr[-300:]}"
            self.logger.warning(f"[YOUTUBE] {detail}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=detail,
            )

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if stderr:
            for line in stderr.splitlines()[-10:]:
                self.logger.info(f"[YOUTUBE_CHILD] {line}")

        if completed.returncode != 0:
            detail = stderr[-500:] or stdout[-500:] or f"child exit code {completed.returncode}"
            self.logger.warning(f"[YOUTUBE] Playwright subprocess failed: {detail}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=detail,
            )

        try:
            json_line = next(
                line for line in reversed(stdout.splitlines())
                if line.strip().startswith("{")
            )
            return json.loads(json_line)
        except (StopIteration, json.JSONDecodeError) as e:
            detail = f"Invalid Playwright subprocess output: {e}; stdout={stdout[-300:]}"
            self.logger.warning(f"[YOUTUBE] {detail}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=detail,
            )

    def _crawl_suggestions(self, query: str, url: str):
        self.logger.info(f"[YOUTUBE] Getting suggestions with Playwright for: {query}")
        with self._new_page() as page:
            self._goto_results_page(page, url)
            self._log_page_state(page, "results_loaded")

            search_input = self._find_visible_search_input(page, self.input_timeout_ms)
            if not search_input:
                self._log_page_state(page, "search_input_not_found", warning=True)
                return []

            html = search_input.evaluate("(el) => el.outerHTML")
            self.logger.info(f"[YOUTUBE] Found search input: {html[:220]}")

            self._open_suggestion_dropdown(page, search_input)
            list_a = self._wait_for_suggestions(page)
            self.logger.info(f"[YOUTUBE] List A (Focus): {list_a}")

            self._refresh_suggestions_with_keyboard(page, search_input)
            list_b = self._wait_for_suggestions(page)
            self.logger.info(f"[YOUTUBE] List B (Space): {list_b}")

            suggestions = self._expand_ellipsis_suggestions(
                self._dedupe_suggestions(list_b + list_a),
                query,
            )
            if not suggestions:
                self._log_page_state(page, "suggestions_empty", warning=True)
            return suggestions

    @contextmanager
    def _new_page(self):
        playwright = sync_playwright().start()
        browser = None
        context = None
        try:
            browser = playwright.chromium.launch(
                headless=self.headless,
                executable_path=self._chrome_executable_path(),
                timeout=self.launch_timeout_ms,
                args=self._browser_args(),
            )
            context = browser.new_context(
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                viewport={"width": 1920, "height": 1080},
                user_agent=self.USER_AGENT,
                extra_http_headers={
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
                },
            )
            context.set_default_timeout(self.input_timeout_ms)
            context.set_default_navigation_timeout(self.navigation_timeout_ms)
            self._set_locale_cookies(context)

            page = context.new_page()
            page.route("**/*", self._route_request)
            yield page
        finally:
            if context:
                try:
                    context.close()
                except PlaywrightError as e:
                    self.logger.debug(f"[YOUTUBE] Error closing context: {e}")
            if browser:
                try:
                    browser.close()
                except PlaywrightError as e:
                    self.logger.debug(f"[YOUTUBE] Error closing browser: {e}")
            playwright.stop()

    def _chrome_executable_path(self):
        if self.chrome_executable and os.path.exists(self.chrome_executable):
            return self.chrome_executable
        if self.chrome_executable != "/usr/bin/google-chrome":
            self.logger.warning(
                f"[YOUTUBE] PLAYWRIGHT_CHROME_EXECUTABLE not found: {self.chrome_executable}"
            )
        return None

    def _browser_args(self):
        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--disable-translate",
            "--disable-sync",
            "--disable-domain-reliability",
            "--disable-renderer-backgrounding",
            "--disable-device-discovery-notifications",
            "--disable-quic",
            "--dns-prefetch-disable",
            "--mute-audio",
            "--blink-settings=imagesEnabled=false",
            "--window-size=1920,1080",
        ]
        resolver_rules = self._host_resolver_rules()
        if resolver_rules:
            args.append(f"--host-resolver-rules={resolver_rules}")
            self.logger.info(f"[YOUTUBE] Applying Chrome host resolver rules: {resolver_rules}")
        return args

    def _host_resolver_rules(self):
        if os.getenv("YOUTUBE_DISABLE_HOST_RESOLVER_RULES") == "1":
            return ""

        explicit_rules = os.getenv("YOUTUBE_HOST_RESOLVER_RULES")
        if explicit_rules:
            return explicit_rules

        ip = os.getenv("YOUTUBE_HOST_IP", "").strip()
        if not ip and (
            os.getenv("YOUTUBE_SYSTEM_DNS_FAILED") == "1" or
            os.getenv("YOUTUBE_AUTO_HOST_RESOLVE") == "1"
        ):
            ip = self._resolve_youtube_ip_with_public_dns()
            if ip:
                self.logger.warning(
                    f"[YOUTUBE] System DNS failed; applying fresh YouTube IP for Chrome resolver: {ip}"
                )
        if not ip:
            return ""

        rules = [f"MAP {host} {ip}" for host in self.YOUTUBE_HOSTS]
        rules.append("EXCLUDE localhost")
        rules.append("EXCLUDE 127.0.0.1")
        return ",".join(rules)

    def _resolve_youtube_ip_with_public_dns(self):
        for server in self.PUBLIC_DNS_SERVERS:
            for protocol in ("udp", "tcp"):
                try:
                    ip = self._resolve_a_record("www.youtube.com", server, protocol)
                    if ip:
                        self.logger.info(
                            f"[YOUTUBE] Resolved www.youtube.com via DNS {server}/{protocol}: {ip}"
                        )
                        return ip
                except Exception as e:
                    self.logger.debug(f"[YOUTUBE] DNS {server}/{protocol} failed: {e}")
        return ""

    def _resolve_a_record(self, host: str, server: str, protocol: str):
        query_id = random.randint(0, 65535)
        packet = self._build_dns_query(host, query_id)

        if protocol == "udp":
            sock_type = socket.SOCK_DGRAM
        else:
            sock_type = socket.SOCK_STREAM

        with socket.socket(socket.AF_INET, sock_type) as sock:
            sock.settimeout(1.5)
            sock.connect((server, 53))
            if protocol == "udp":
                sock.send(packet)
                data = sock.recv(512)
            else:
                sock.sendall(struct.pack("!H", len(packet)) + packet)
                header = sock.recv(2)
                if len(header) != 2:
                    return ""
                response_len = struct.unpack("!H", header)[0]
                data = b""
                while len(data) < response_len:
                    chunk = sock.recv(response_len - len(data))
                    if not chunk:
                        break
                    data += chunk
            return self._parse_dns_a_response(data, query_id)

    def _build_dns_query(self, host: str, query_id: int):
        header = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
        qname = b"".join(
            bytes([len(part)]) + part.encode("ascii")
            for part in host.split(".")
        ) + b"\x00"
        question = qname + struct.pack("!HH", 1, 1)
        return header + question

    def _parse_dns_a_response(self, data: bytes, query_id: int):
        if len(data) < 12:
            return ""

        response_id, _flags, qdcount, ancount, _nscount, _arcount = struct.unpack(
            "!HHHHHH", data[:12]
        )
        if response_id != query_id:
            return ""

        offset = 12
        for _ in range(qdcount):
            offset = self._skip_dns_name(data, offset)
            offset += 4

        for _ in range(ancount):
            offset = self._skip_dns_name(data, offset)
            if offset + 10 > len(data):
                return ""
            rtype, rclass, _ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
            offset += 10
            rdata = data[offset:offset + rdlength]
            offset += rdlength
            if rtype == 1 and rclass == 1 and rdlength == 4:
                return socket.inet_ntoa(rdata)
        return ""

    def _skip_dns_name(self, data: bytes, offset: int):
        while offset < len(data):
            length = data[offset]
            if length == 0:
                return offset + 1
            if length & 0xC0 == 0xC0:
                return offset + 2
            offset += 1 + length
        return offset

    def _set_locale_cookies(self, context):
        expires = int(time.time()) + 60 * 60 * 24 * 365
        cookies = [
            {
                "name": "PREF",
                "value": "hl=ko&gl=KR",
                "domain": ".youtube.com",
                "path": "/",
                "expires": expires,
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            },
            {
                "name": "CONSENT",
                "value": "YES+cb.20210328-17-p0.ko+FX+667",
                "domain": ".youtube.com",
                "path": "/",
                "expires": expires,
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            },
            {
                "name": "SOCS",
                "value": "CAI",
                "domain": ".youtube.com",
                "path": "/",
                "expires": expires,
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            },
        ]
        context.add_cookies(cookies)

    def _route_request(self, route):
        if route.request.resource_type in {"image", "media", "font"}:
            route.abort()
            return
        route.continue_()

    def _goto_results_page(self, page, url: str):
        last_error = None
        for attempt in range(1, self.navigation_retries + 1):
            try:
                self.logger.info(
                    f"[YOUTUBE] Loading YouTube results page with Playwright: {url} "
                    f"(attempt {attempt}/{self.navigation_retries})"
                )
                page.goto(url, wait_until="commit", timeout=self.navigation_timeout_ms)
                self._raise_if_browser_error_page(page, url)
                self._find_visible_search_input(page, self.input_timeout_ms)
                self.logger.info(f"[YOUTUBE] Search results page ready: {page.url}")
                return
            except (PlaywrightTimeoutError, PlaywrightError, RuntimeError) as e:
                last_error = e
                page_url = getattr(page, "url", "unavailable")
                self.logger.warning(
                    f"[YOUTUBE] Playwright navigation attempt {attempt}/{self.navigation_retries} "
                    f"failed at {page_url}: {e}"
                )
                if attempt < self.navigation_retries:
                    page.wait_for_timeout(700 * attempt)
        raise RuntimeError(f"Failed to load youtube.com results page: {last_error}")

    def _raise_if_browser_error_page(self, page, url: str):
        state = self._page_state(page)
        text = " ".join(str(state.get(key, "")) for key in ("href", "title", "bodyPreview"))
        markers = (
            "chrome-error://",
            "ERR_NAME_NOT_RESOLVED",
            "ERR_INTERNET_DISCONNECTED",
            "ERR_CONNECTION_TIMED_OUT",
            "ERR_CONNECTION_CLOSED",
            "ERR_TUNNEL_CONNECTION_FAILED",
            "DNS_PROBE",
            "사이트에 연결할 수 없음",
            "This site can't be reached",
            "This site can’t be reached",
            "server IP address could not be found",
        )
        if any(marker in text for marker in markers):
            raise RuntimeError(f"Chrome error page while loading {url}: {state}")

    def _find_visible_search_input(self, page, timeout_ms: int):
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            try:
                handle = page.evaluate_handle(
                    """
                    (selector) => {
                        const inputs = Array.from(document.querySelectorAll(selector));
                        return inputs.find((el) => {
                            const rect = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return rect.width > 0 &&
                                rect.height > 0 &&
                                style.visibility !== 'hidden' &&
                                style.display !== 'none';
                        }) || null;
                    }
                    """,
                    self.SEARCH_INPUT_SELECTORS,
                )
                element = handle.as_element()
                if element:
                    return element
                handle.dispose()
            except PlaywrightError:
                pass
            page.wait_for_timeout(300)
        return None

    def _open_suggestion_dropdown(self, page, search_input):
        search_input.scroll_into_view_if_needed(timeout=5000)
        search_input.click(timeout=5000)
        search_input.evaluate(
            """
            (input) => {
                input.focus();
                ['pointerdown', 'mousedown', 'mouseup', 'click'].forEach((type) => {
                    input.dispatchEvent(new MouseEvent(type, {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }));
                });
                input.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    inputType: 'insertText',
                    data: ''
                }));
            }
            """
        )
        page.wait_for_timeout(500)
        active = page.evaluate(
            """
            () => {
                const el = document.activeElement;
                if (!el) return '';
                return `${el.tagName.toLowerCase()}.${el.className || ''}`;
            }
            """
        )
        self.logger.info(f"[YOUTUBE] Active Element: {active}")

    def _refresh_suggestions_with_keyboard(self, page, search_input):
        try:
            search_input.press(" ")
            page.wait_for_timeout(150)
            search_input.press("Backspace")
            page.wait_for_timeout(300)
            self.logger.info("[YOUTUBE] Dispatched keyboard refresh for suggestions")
        except PlaywrightError as e:
            self.logger.warning(f"[YOUTUBE] Failed to refresh suggestions with keyboard: {e}")

    def _wait_for_suggestions(self, page):
        deadline = time.monotonic() + (self.suggestion_timeout_ms / 1000)
        last_result = []
        while time.monotonic() < deadline:
            last_result = self._scrape_suggestion_texts(page)
            if last_result:
                return last_result
            page.wait_for_timeout(250)
        return last_result

    def _scrape_suggestion_texts(self, page):
        try:
            texts = page.evaluate(
                """
                () => {
                    const result = [];
                    const pushText = (el) => {
                        const text = (el.innerText || el.textContent || '').trim();
                        if (text) result.push(text);
                    };

                    const input = document.querySelector(
                        "input[name='search_query'], input#search, input.ytSearchboxComponentInput"
                    );
                    const controls = input && input.getAttribute('aria-controls');
                    const controlledList = controls && document.getElementById(controls);
                    if (controlledList) {
                        controlledList
                            .querySelectorAll("[role='option'], li, div.ytSuggestionComponentSuggestion")
                            .forEach(pushText);
                    }

                    document
                        .querySelectorAll(
                            "div.ytSuggestionComponentSuggestion div.ytSuggestionComponentText, " +
                            "div.ytSuggestionComponentSuggestion, " +
                            "[role='option'], " +
                            "li.sbsb_c .sbqs_c, " +
                            "li.sbsb_c"
                        )
                        .forEach(pushText);

                    return result;
                }
                """
            )
            return self._dedupe_suggestions(texts or [])
        except PlaywrightError as e:
            self.logger.warning(f"[YOUTUBE] Error extracting suggestion texts: {e}")
            return []

    def _log_page_state(self, page, label: str, warning: bool = False):
        state = self._page_state(page)
        log = self.logger.warning if warning else self.logger.info
        log(f"[YOUTUBE_DEBUG] {label}: {state}")

    def _page_state(self, page):
        try:
            return page.evaluate(
                """
                () => {
                    const inputInfo = Array.from(document.querySelectorAll('input'))
                        .slice(0, 12)
                        .map((el) => {
                            const rect = el.getBoundingClientRect();
                            return {
                                name: el.getAttribute('name') || '',
                                id: el.id || '',
                                cls: el.className || '',
                                type: el.type || '',
                                placeholder: el.getAttribute('placeholder') || '',
                                aria: el.getAttribute('aria-label') || '',
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                                visible: rect.width > 0 && rect.height > 0
                            };
                        });
                    const bodyText = (document.body && document.body.innerText || '')
                        .replace(/\\s+/g, ' ')
                        .trim();
                    return {
                        href: location.href,
                        readyState: document.readyState,
                        title: document.title || '',
                        inputCount: document.querySelectorAll('input').length,
                        ytdApp: !!document.querySelector('ytd-app'),
                        searchboxCount: document.querySelectorAll(
                            "ytd-searchbox, yt-searchbox, input[name='search_query'], input#search"
                        ).length,
                        suggestionsCount: document.querySelectorAll(
                            "div.ytSuggestionComponentSuggestion, [role='option'], li.sbsb_c"
                        ).length,
                        inputs: inputInfo,
                        bodyPreview: bodyText.slice(0, 300)
                    };
                }
                """
            )
        except PlaywrightError as e:
            return {
                "href": getattr(page, "url", "unavailable"),
                "error": type(e).__name__,
                "bodyPreview": "",
            }

    def _dedupe_suggestions(self, suggestions):
        seen = set()
        result = []
        for item in suggestions:
            for part in str(item).splitlines():
                text = " ".join(part.split())
                if text and text not in seen:
                    result.append(text)
                    seen.add(text)
        return result

    def _expand_ellipsis_suggestions(self, suggestions, query: str):
        result = []
        query_parts = query.split()
        query_prefix = " ".join(query_parts[:-1])
        query_last = query_parts[-1].lower() if query_parts else ""

        for suggestion in suggestions:
            text = suggestion.strip()
            if text.startswith("...") or text.startswith("\u2026"):
                suffix = text[3:].strip() if text.startswith("...") else text[1:].strip()
                if suffix and query_last and suffix.lower().startswith(query_last):
                    text = f"{query_prefix} {suffix}".strip()
                else:
                    text = f"{query} {suffix}".strip() if suffix else query
            result.append(text)
        return self._dedupe_suggestions(result)

    def _build_suggestion_response(self, query: str, suggestions, error: str = None, detail: str = None):
        response = {
            "keyword": query,
            "result": [
                {
                    "rank": index + 1,
                    "query": suggestion,
                }
                for index, suggestion in enumerate(suggestions)
            ],
        }
        if error:
            response["error"] = error
            response["detail"] = (detail or "")[:500]
        return response

    def get_list(self, query: str, limit: int = 30):
        base_url = f"https://www.youtube.com/results?search_query={quote(query)}&hl=ko&gl=KR"
        results = []
        try:
            self.logger.info(f"[YOUTUBE] Starting Playwright scrape for query: {query}, limit: {limit}")
            with self._new_page() as page:
                self._goto_results_page(page, base_url)
                for _ in range(max(1, limit + 1)):
                    page.mouse.wheel(0, 800)
                    page.wait_for_timeout(500)

                soup = BeautifulSoup(page.content(), "html.parser")
                all_items = soup.select("ytd-video-renderer, ytd-reel-item-renderer")
                self.logger.info(f"[YOUTUBE] Parsed {len(all_items)} items from search page.")
                results = self._parse_items(all_items, limit)
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] Unexpected error in get_list(): {e}")
        finally:
            self.logger.info(f"[YOUTUBE] Final result count: {len(results)}")
        return results

    def _parse_items(self, all_items, limit):
        results = []
        for item in all_items:
            if len(results) >= limit:
                break

            if item.name == "ytd-video-renderer":
                title_tag = item.select_one("#video-title")
                if not title_tag:
                    continue

                title = title_tag.get("title", "").strip()
                href = title_tag.get("href", "")
                url = f"https://www.youtube.com{href}" if href.startswith("/") else href
                channel_tag = item.select_one("ytd-channel-name #text")
                channel = channel_tag.get_text(strip=True) if channel_tag else ""

                meta_info = item.select_one("#metadata-line")
                view_count, published_date = "", ""
                if meta_info:
                    spans = meta_info.find_all("span")
                    if len(spans) >= 2:
                        view_count = self.get_view_count(spans[0].get_text(strip=True))
                        published_date = self.calculate_before_date(spans[1].get_text(strip=True))

                desc_texts = []
                for container in item.select("div.metadata-snippet-container-one-line"):
                    for selector in (
                        "a.metadata-snippet-timestamp yt-formatted-string.metadata-snippet-text-navigation",
                        "yt-formatted-string.metadata-snippet-text",
                    ):
                        snippet = container.select_one(selector)
                        if snippet:
                            desc_texts.append(snippet.get_text(separator=" ", strip=True))

                video_title_tag = item.find("a", id="video-title")
                aria_label = video_title_tag.get("aria-label", "") if video_title_tag else ""
                match = re.search(r"(?:조회수\s+)?([\d,]+)(?:회| views)", aria_label)
                if match:
                    view_count = match.group(1).replace(",", "")

                results.append({
                    "VideoID": self.get_video_id_with_split(url),
                    "title": title,
                    "channel": channel,
                    "url": url,
                    "description": "\n".join(desc_texts).strip(),
                    "publishedDate": published_date,
                    "videoCount": view_count,
                    "videoType": "shorts" if "shorts" in url else "video",
                })

            elif item.name == "ytd-reel-item-renderer":
                title_tag = item.select_one("#shorts-title")
                shorts_link_tag = item.select_one("a#thumbnail")
                if not title_tag or not shorts_link_tag:
                    continue

                href = shorts_link_tag.get("href", "")
                url = f"https://www.youtube.com{href}"
                channel_tag = item.select_one("ytd-channel-name #text")
                results.append({
                    "VideoID": self.get_video_id_with_split(url),
                    "title": title_tag.get_text(strip=True),
                    "channel": channel_tag.get_text(strip=True) if channel_tag else "",
                    "url": url,
                    "description": "",
                    "publishedDate": "",
                    "videoCount": "",
                    "videoType": "shorts",
                })
        return results

    def calculate_before_date(self, input_str: str):
        pattern = r"(\d+)\s*(년|개월|주|일|시간|분|초|year|month|week|day|hour|minute|second)s?\s*(전|ago)"
        match = re.search(pattern, input_str.strip(), re.IGNORECASE)
        if not match:
            return ""

        number_str, unit_str, _ = match.groups()
        number = int(number_str)
        unit_map = {
            "년": "years", "year": "years",
            "개월": "months", "month": "months",
            "주": "weeks", "week": "weeks",
            "일": "days", "day": "days",
            "시간": "hours", "hour": "hours",
            "분": "minutes", "minute": "minutes",
            "초": "seconds", "second": "seconds",
        }

        unit_key = unit_str.lower()
        if unit_key not in unit_map:
            return ""

        before_date = datetime.now() - relativedelta(**{unit_map[unit_key]: number})
        return before_date.strftime("%Y-%m-%d")

    def get_view_count(self, view_str: str) -> str:
        s = view_str.strip().lower()
        s = re.sub(r"(조회수|views|회|\s+)", "", s)

        korean_match = re.match(r"^(\d+(?:\.\d+)?)(만|천)$", s)
        if korean_match:
            number_str, unit_str = korean_match.groups()
            number = float(number_str)
            if unit_str == "만":
                return str(int(number * 10_000))
            if unit_str == "천":
                return str(int(number * 1_000))

        multiplier = 1
        if "k" in s:
            multiplier = 1_000
            s = s.replace("k", "")
        elif "m" in s:
            multiplier = 1_000_000
            s = s.replace("m", "")

        try:
            value = float(s)
        except ValueError:
            return "0"
        return str(int(value * multiplier))

    def to_kst(self, timestamp: str):
        dt = datetime.fromisoformat(timestamp)
        return dt.astimezone(timezone(timedelta(hours=9))).isoformat()

    def get_video_id_with_split(self, url: str):
        if "shorts/" in url:
            return url.split("shorts/", 1)[1].split("?", 1)[0].split("&", 1)[0]
        if "v=" not in url:
            return ""
        return url.split("v=", 1)[1].split("&", 1)[0]
