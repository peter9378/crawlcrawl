import logging
import html
import os
import re
import subprocess
import sys
import time
import random
import traceback
from urllib.parse import urlencode
from typing import Optional

from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

_EXTRACT_JS = """
return (() => {
    const predicted = document.querySelectorAll(
        'li[data-attrid="AutocompletePrediction"][data-entityname]'
    );
    const primary = [];
    for (const item of predicted) {
        const name = item.getAttribute('data-entityname');
        if (name && name.trim()) primary.push(name.trim());
    }
    if (primary.length > 0) return {source: 'data-entityname', items: primary};

    const isVisible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.visibility !== 'hidden' && style.display !== 'none'
            && rect.width > 0 && rect.height > 0;
    };
    const textFrom = (el) => {
        const preferred = el.querySelector(
            '.wM6W7d span, .wM6W7d, .lnnVSe, [role="option"] span'
        );
        if (preferred && preferred.innerText) return preferred.innerText;
        const labelled = el.matches('[aria-label]')
            ? el
            : el.querySelector('[aria-label]');
        if (labelled) {
            const aria = labelled.getAttribute('aria-label');
            if (aria) return aria;
        }
        return el.innerText || el.textContent || '';
    };
    const fallbackSelectors = [
        'ul[role="listbox"] li[role="option"]',
        'ul[role="listbox"] li',
        'div[role="listbox"] [role="option"]',
        'li[role="presentation"]',
        'li.sbct',
    ];
    for (const selector of fallbackSelectors) {
        const items = [];
        for (const node of document.querySelectorAll(selector)) {
            if (!isVisible(node)) continue;
            const text = textFrom(node);
            if (text) items.push(text);
        }
        if (items.length > 0) return {source: `fallback:${selector}`, items: items};
    }
    return {source: 'none', items: []};
})();
"""

_ACCEPT_CONSENT_JS = """
return (() => {
    const visible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.visibility !== 'hidden' && style.display !== 'none'
            && rect.width > 0 && rect.height > 0;
    };
    const wanted = [
        'accept all', 'i agree', 'agree', '동의', '모두 수락', '모두 동의'
    ];
    const controls = Array.from(document.querySelectorAll(
        'button, input[type="submit"], div[role="button"]'
    ));
    for (const el of controls) {
        if (!visible(el)) continue;
        const text = (
            el.innerText || el.value || el.getAttribute('aria-label') || ''
        ).trim().toLowerCase();
        const id = (el.id || '').toLowerCase();
        if (id === 'l2aglb' || wanted.some(w => text.includes(w))) {
            el.click();
            return text || id;
        }
    }
    return null;
})();
"""

_CLEAR_SEARCH_JS = """
return (() => {
    const el = document.querySelector(
        'textarea[name="q"], input[name="q"]:not([type="hidden"])'
    );
    if (!el) return false;
    el.focus();
    const proto = el.tagName === 'TEXTAREA'
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
    if (descriptor && descriptor.set) descriptor.set.call(el, '');
    else el.value = '';
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
    return true;
})();
"""

_SUBMIT_SEARCH_JS = """
return (() => {
    const visible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.visibility !== 'hidden' && style.display !== 'none'
            && rect.width > 0 && rect.height > 0;
    };
    const buttons = Array.from(document.querySelectorAll(
        'input[name="btnK"], button[name="btnK"]'
    ));
    const button = buttons.find(visible);
    if (button) {
        button.click();
        return 'button';
    }
    const input = document.querySelector(
        'textarea[name="q"], input[name="q"]:not([type="hidden"])'
    );
    const form = input ? input.closest('form') : document.querySelector(
        'form[role="search"], form[action*="/search"]'
    );
    if (form) {
        form.requestSubmit ? form.requestSubmit() : form.submit();
        return 'form';
    }
    return null;
})();
"""

_FOCUS_SEARCH_JS = """
return (() => {
    const el = document.querySelector(
        'textarea[name="q"], input[name="q"]:not([type="hidden"])'
    );
    if (!el) return false;
    el.focus();
    el.click();
    el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
    el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    return true;
})();
"""


class Scraper:
    _CHROME_PATHS = [
        "/opt/google/chrome/google-chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]

    _FIXED_VIEWPORT: Optional[dict] = None
    _PROFILE_DIR = os.environ.get(
        "DGOOGLE_PROFILE_DIR", "/tmp/dgoogle_profile_suggest"
    )
    _SUGGEST_WAIT_SECONDS = float(os.environ.get("DGOOGLE_SUGGEST_WAIT", "6"))
    # CAPTCHA 연속 실패 시 대기(초): 1분 → 2분30초 → 5분 → 10분
    _CAPTCHA_BACKOFF_SECONDS = (60, 150, 300, 600)

    def __init__(self):
        self.logger = logging.getLogger("uvicorn")
        if not self.logger.handlers and not self.logger.parent.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s:  %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False

    @staticmethod
    def _is_linux() -> bool:
        return sys.platform.startswith("linux")

    @staticmethod
    def _is_captcha(url: str) -> bool:
        if not url:
            return False
        return "/sorry/" in url or url.startswith("https://www.google.com/sorry")

    def _is_captcha_page(self, page: ChromiumPage) -> bool:
        if self._is_captcha(self._page_url(page)):
            return True
        try:
            html = page.html or ""
        except Exception:
            return False
        markers = (
            'id="captcha-form"',
            "Our systems have detected unusual traffic",
            "unusual traffic from your computer network",
            "g-recaptcha",
            "/recaptcha/",
        )
        return any(marker in html for marker in markers)

    def _google_home_url(self) -> str:
        params = {
            "hl": os.environ.get("DGOOGLE_HL", "en"),
            "gl": os.environ.get("DGOOGLE_GL", "us"),
            "pws": "0",
        }
        return "https://www.google.com/?" + urlencode(params)

    def _google_search_url(self, query: str) -> str:
        params = {
            "q": query,
            "hl": os.environ.get("DGOOGLE_HL", "en"),
            "gl": os.environ.get("DGOOGLE_GL", "us"),
            "pws": "0",
        }
        return "https://www.google.com/search?" + urlencode(params)

    def _find_chrome(self) -> Optional[str]:
        for path in self._CHROME_PATHS:
            if os.path.isfile(path):
                return path
        for cmd in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
        ):
            try:
                path = subprocess.check_output(
                    ["which", cmd], stderr=subprocess.DEVNULL, timeout=3
                ).decode().strip()
                if path and os.path.isfile(path):
                    return path
            except Exception:
                pass
        return None

    def _start_xvfb(self) -> Optional[subprocess.Popen]:
        display = os.environ.get("DGOOGLE_XVFB_DISPLAY", ":99")
        try:
            proc = subprocess.Popen(
                ["Xvfb", display, "-screen", "0", "1920x1080x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.environ["DISPLAY"] = display
            time.sleep(1.0)
            if proc.poll() is not None:
                self.logger.info(
                    f"[browser] Xvfb did not stay running on {display}; "
                    "assuming an existing display or host Chrome display"
                )
                return None
            return proc
        except FileNotFoundError:
            return None

    def _build_chromium_options(self) -> ChromiumOptions:
        if Scraper._FIXED_VIEWPORT is None:
            Scraper._FIXED_VIEWPORT = {
                "width": random.randint(1800, 1920),
                "height": random.randint(900, 1080),
            }
        w = Scraper._FIXED_VIEWPORT["width"]
        h = Scraper._FIXED_VIEWPORT["height"]

        os.makedirs(self._PROFILE_DIR, exist_ok=True)

        co = ChromiumOptions()
        co.headless(False)
        chrome = self._find_chrome()
        if chrome:
            co.set_browser_path(chrome)
        co.set_user_data_path(self._PROFILE_DIR)
        co.set_local_port(int(os.environ.get("DGOOGLE_CHROME_PORT", "9222")))

        co.set_argument("--no-sandbox")
        co.set_argument("--disable-dev-shm-usage")
        co.set_argument("--disable-gpu")
        co.set_argument("--mute-audio")
        co.set_argument("--disable-notifications")
        co.set_argument("--disable-popup-blocking")
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--disable-infobars")
        co.set_argument("--disable-extensions")
        co.set_argument("--disable-features=Translate,MediaRouter")
        co.set_argument("--no-first-run")
        co.set_argument("--no-default-browser-check")
        co.set_argument("--password-store=basic")
        co.set_argument(f"--lang={os.environ.get('DGOOGLE_LANG', 'en-US')}")
        co.set_argument(
            f"--accept-lang={os.environ.get('DGOOGLE_ACCEPT_LANG', 'en-US,en')}"
        )
        co.set_argument(f"--window-size={w},{h}")

        return co

    def _open_page(self) -> ChromiumPage:
        co = self._build_chromium_options()
        page = ChromiumPage(co)
        page.set.timeouts(base=30, page_load=30)
        return page

    def _page_url(self, page: ChromiumPage) -> str:
        try:
            return page.url or ""
        except Exception:
            return ""

    def _home_search_ele(self, page: ChromiumPage, timeout: float = 10):
        ele = page.ele("css:textarea[name='q']", timeout=timeout)
        if ele:
            return ele
        return page.ele("css:input[name='q']:not([type='hidden'])", timeout=timeout)

    def _clear_search_box(self, page: ChromiumPage, ele) -> None:
        try:
            page.run_js(_CLEAR_SEARCH_JS)
        except Exception:
            pass
        try:
            ele.clear()
        except Exception:
            pass

    def _wait_after_navigation(self, page: ChromiumPage, seconds: float = 2.0) -> None:
        time.sleep(random.uniform(seconds * 0.75, seconds * 1.25))

    def _accept_consent_if_present(self, page: ChromiumPage) -> None:
        try:
            clicked = page.run_js(_ACCEPT_CONSENT_JS)
            if clicked:
                self.logger.info(f"[browser] consent accepted via {clicked!r}")
                self._wait_after_navigation(page, 1.0)
        except Exception as e:
            self.logger.debug(f"[browser] consent check skipped: {e}")

    def _dump_debug_artifacts(self, page: ChromiumPage, query: str, tag: str) -> None:
        try:
            ts = int(time.time())
            safe_query = re.sub(r"[^a-zA-Z0-9]+", "_", query)[:40]
            base = f"/tmp/dgoogle_{tag}_{safe_query}_{ts}"
            html_path = f"{base}.html"
            png_path = f"{base}.png"
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page.html or "")
            except Exception as e:
                self.logger.warning(f"[browser/debug] html dump failed: {e}")
                html_path = None
            try:
                page.get_screenshot(path=png_path, full_page=True)
            except Exception as e:
                self.logger.warning(f"[browser/debug] screenshot failed: {e}")
                png_path = None
            self.logger.warning(
                f"[browser/debug] saved tag={tag} url={self._page_url(page)} "
                f"html={html_path} png={png_path}"
            )
        except Exception as e:
            self.logger.warning(f"[browser/debug] dump completely failed: {e}")

    def _handle_captcha_if_needed(self, page: ChromiumPage, query: str, tag: str) -> bool:
        """CAPTCHA면 중단. CAPTCHA 아님(True) / 차단됨(False)."""
        if not self._is_captcha_page(page):
            return True
        self.logger.warning(
            f"[captcha] blocked at {tag}; not solving CAPTCHA or using "
            "autocomplete API"
        )
        self._dump_debug_artifacts(page, query, f"captcha_{tag}")
        return False

    def _extract_searchbox_suggestions(
        self, page: ChromiumPage, query: str, limit: int, log: bool = True
    ) -> list:
        raw_items = []
        source = "none"

        try:
            extraction = page.run_js(_EXTRACT_JS)
            if isinstance(extraction, dict):
                source = extraction.get("source", "none")
                raw_items = extraction.get("items") or []
        except Exception as e:
            self.logger.warning(f"[browser/extract] run_js failed: {e}")

        if not raw_items:
            soup = BeautifulSoup(page.html or "", "html.parser")
            for li in soup.select(
                'li[data-attrid="AutocompletePrediction"][data-entityname]'
            ):
                name = (li.get("data-entityname") or "").strip()
                if name:
                    raw_items.append(name)
            if raw_items:
                source = "bs4:data-entityname"

            if not raw_items:
                selectors = (
                    "ul[role='listbox'] li[role='option']",
                    "ul[role='listbox'] li",
                    "div[role='listbox'] [role='option']",
                    "li[role='presentation']",
                    "li.sbct",
                )
                for node in soup.select(", ".join(selectors)):
                    text = node.get_text(separator=" ", strip=True)
                    if text:
                        raw_items.append(text)
                if raw_items:
                    source = "bs4:listbox"

        if log:
            self.logger.info(
                f"[browser/extract] source={source}, raw={len(raw_items)}"
            )
        if log and raw_items:
            preview = [str(s)[:80] for s in raw_items[:30]]
            self.logger.info(f"[browser/extract] raw_preview={preview}")

        results = []
        seen = set()
        ignored = {
            "",
            query.lower(),
            "google search",
            "i'm feeling lucky",
            "search",
            "remove",
        }
        for raw_text in raw_items:
            for line in str(raw_text).splitlines():
                text = self._normalize_suggestion_text(line)
                key = text.lower()
                if not text or key in ignored or "click here" in key:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                results.append({"rank": len(results) + 1, "keyword": text})
                if len(results) >= limit:
                    return results
        return results

    @staticmethod
    def _normalize_suggestion_text(text: str) -> str:
        text = html.unescape(text or "")
        if "<" in text and ">" in text:
            text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text or "").strip()
        text = re.sub(r"^(?:Search for|Google Search)\s+", "", text, flags=re.I)
        text = re.sub(r"\s+(?:Google Search|Search)$", "", text, flags=re.I)
        text = re.sub(
            r"\s*(?:Remove|삭제|검색어 삭제)\s*$", "", text, flags=re.IGNORECASE
        )
        return text.strip()

    def _wait_for_suggestions(
        self, page: ChromiumPage, query: str, limit: int, wait_seconds: float
    ) -> list:
        deadline = time.time() + wait_seconds
        results = []
        while time.time() < deadline:
            if self._is_captcha_page(page):
                return []
            results = self._extract_searchbox_suggestions(
                page, query, limit, log=False
            )
            if results:
                return results
            time.sleep(random.uniform(0.2, 0.4))
        return self._extract_searchbox_suggestions(page, query, limit, log=True)

    def _type_query_for_suggestions(
        self, page: ChromiumPage, query: str, slow: bool = False
    ) -> None:
        ele = self._home_search_ele(page)
        if not ele:
            raise RuntimeError("search box not found")
        ele.click()
        time.sleep(random.uniform(0.15, 0.35))
        self._clear_search_box(page, ele)
        if slow:
            for char in query:
                ele.input(char)
                time.sleep(random.uniform(0.04, 0.12))
        else:
            ele.input(query)
        time.sleep(random.uniform(0.35, 0.7))

    def _submit_search_from_home(self, page: ChromiumPage, query: str) -> bool:
        ele = self._home_search_ele(page)
        if not ele:
            self.logger.warning("[browser] home search box not found")
            return False
        ele.click()
        time.sleep(random.uniform(0.25, 0.5))
        self._clear_search_box(page, ele)
        for char in query:
            ele.input(char)
            time.sleep(random.uniform(0.03, 0.09))
        time.sleep(random.uniform(0.45, 0.9))

        submitted = None
        try:
            submitted = page.run_js(_SUBMIT_SEARCH_JS)
        except Exception as e:
            self.logger.warning(f"[browser] JS submit failed: {e}")
        if not submitted:
            try:
                ele.input("\n")
                submitted = "enter"
            except Exception as e:
                self.logger.warning(f"[browser] Enter submit failed: {e}")

        self.logger.info(f"[browser] search submitted via {submitted!r}")
        self._wait_after_navigation(page, 2.5)
        return "/search" in self._page_url(page)

    def _ensure_results_page(self, page: ChromiumPage, query: str) -> bool:
        if "/search" in self._page_url(page):
            return True

        search_url = self._google_search_url(query)
        self.logger.warning(
            f"[browser] submit did not reach SERP, opening search url: {search_url}"
        )
        page.get(search_url)
        self._wait_after_navigation(page, 2.5)
        return "/search" in self._page_url(page)

    def _click_serp_searchbox(self, page: ChromiumPage, query: str) -> bool:
        ele = self._home_search_ele(page, timeout=8)
        if not ele:
            self.logger.warning("[browser] SERP search box not found")
            self._dump_debug_artifacts(page, query, "no_serp_searchbox")
            return False

        try:
            ele.click()
            page.run_js(_FOCUS_SEARCH_JS)
        except Exception as e:
            self.logger.warning(f"[browser] SERP search box click failed: {e}")
            self._dump_debug_artifacts(page, query, "serp_click_failed")
            return False
        time.sleep(random.uniform(0.5, 0.9))
        return True

    def _scrape_via_browser(self, query: str, limit: int) -> tuple[list, bool]:
        """DrissionPage: google.com 검색 후 SERP 검색창 dropdown 추천어 추출.

        Returns:
            (results, captcha_hit) — captcha_hit이 True면 CAPTCHA로 중단됨.
        """
        results = []
        captcha_hit = False
        xvfb_proc = None
        page = None

        try:
            if self._is_linux():
                xvfb_proc = self._start_xvfb()
                if xvfb_proc:
                    print(f"[dp] Xvfb started on {os.environ.get('DISPLAY')}")
                else:
                    print("[dp] Xvfb not started")

            page = self._open_page()
            self.logger.info("[browser] DrissionPage Chromium started")

            home_url = self._google_home_url()
            page.get(home_url)
            self._wait_after_navigation(page, 2.0)
            self._accept_consent_if_present(page)
            if not self._handle_captcha_if_needed(page, query, "home"):
                return [], True

            try:
                title = page.title
            except Exception:
                title = "?"
            self.logger.info(
                f"[browser] home url={self._page_url(page)}, title={title!r}"
            )

            if not self._submit_search_from_home(page, query):
                if not self._handle_captcha_if_needed(page, query, "after_submit"):
                    return [], True
            if not self._ensure_results_page(page, query):
                self.logger.warning(f"[browser] not on SERP: {self._page_url(page)}")
                self._dump_debug_artifacts(page, query, "no_serp")
                if self._is_captcha_page(page):
                    return [], True
                return [], False
            if not self._handle_captcha_if_needed(page, query, "serp"):
                return [], True

            self.logger.info(f"[browser] SERP url={self._page_url(page)}")
            if not self._click_serp_searchbox(page, query):
                return [], False

            results = self._wait_for_suggestions(
                page, query, limit, self._SUGGEST_WAIT_SECONDS
            )

            if not results and not self._is_captcha_page(page):
                self.logger.info(
                    "[browser] retrying SERP suggestion input with slow typing"
                )
                self._type_query_for_suggestions(page, query, slow=True)
                results = self._wait_for_suggestions(
                    page, query, limit, self._SUGGEST_WAIT_SECONDS
                )

            if not self._handle_captcha_if_needed(page, query, "suggest"):
                return [], True
            if results:
                self.logger.info(
                    f"[browser] keywords={[r['keyword'] for r in results]}"
                )
            else:
                self.logger.warning(
                    f"[browser] no suggestions for query={query!r}"
                )
                self._dump_debug_artifacts(page, query, "no_suggestions")

            if not results and page is not None and self._is_captcha_page(page):
                captcha_hit = True

        except Exception as e:
            self.logger.error(f"[browser] unexpected error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            if page is not None:
                try:
                    page.quit()
                except Exception:
                    pass
            if xvfb_proc:
                xvfb_proc.terminate()

        return results, captcha_hit

    @staticmethod
    def _format_backoff(seconds: float) -> str:
        if seconds >= 60:
            mins, secs = divmod(int(seconds), 60)
            if secs:
                return f"{mins}m{secs}s"
            return f"{mins}m"
        return f"{int(seconds)}s"

    def scrape_google(self, query: str, limit: int = 30) -> list:
        """google.com 검색 결과 페이지 검색창 dropdown 추천어 반환."""
        print(f"[scraper] query={query}, limit={limit}")

        captcha_failures = 0
        generic_retries = 0
        run = 0

        while True:
            run += 1
            results, captcha_hit = self._scrape_via_browser(query, limit)
            if results:
                self.logger.info(
                    f"[scraper] success run {run}: {len(results)} "
                    f"keywords={[r['keyword'] for r in results]}"
                )
                return results

            if captcha_hit:
                captcha_failures += 1
                if captcha_failures > len(self._CAPTCHA_BACKOFF_SECONDS):
                    self.logger.error(
                        f"[captcha] gave up after {captcha_failures} CAPTCHA "
                        f"failures for query={query!r}"
                    )
                    break
                wait = self._CAPTCHA_BACKOFF_SECONDS[captcha_failures - 1]
                self.logger.warning(
                    f"[captcha] failure {captcha_failures}/"
                    f"{len(self._CAPTCHA_BACKOFF_SECONDS)} for query={query!r}; "
                    f"waiting {self._format_backoff(wait)} before retry"
                )
                time.sleep(wait)
                continue

            if generic_retries < 1:
                generic_retries += 1
                backoff = random.uniform(5.0, 8.0)
                self.logger.warning(
                    f"[scraper] no results (non-CAPTCHA), retry after {backoff:.1f}s"
                )
                time.sleep(backoff)
                continue

            break

        self.logger.error(
            "[scraper] failed — empty list. Check [browser]/[captcha] logs and "
            "debug artifacts under /tmp."
        )
        return []


if __name__ == "__main__":
    print(Scraper().scrape_google("beauty of joseon sunscreen review", limit=30))
