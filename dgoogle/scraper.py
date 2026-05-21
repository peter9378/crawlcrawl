import json
import logging
import os
import re
import subprocess
import sys
import time
import random
import traceback
from typing import Optional

from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
]

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
        const labelled = el.querySelector('[aria-label]');
        if (labelled) {
            const aria = labelled.getAttribute('aria-label');
            if (aria) return aria;
        }
        const preferred = el.querySelector('.wM6W7d span, .wM6W7d, .lnnVSe');
        if (preferred && preferred.innerText) return preferred.innerText;
        return el.innerText || el.textContent || '';
    };
    const fallbackSelectors = [
        'ul[role="listbox"] li[role="option"]',
        'ul[role="listbox"] li',
        'div[role="listbox"] [role="option"]',
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

_BTN_K_JS = """
() => {
    const btns = Array.from(document.querySelectorAll(
        'input[name="btnK"], button[name="btnK"]'
    ));
    const visible = btns.find(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    });
    if (visible) { visible.click(); return; }
    const f = document.querySelector(
        'form[role="search"], form[action*="/search"]'
    );
    if (f) f.submit();
}
"""


class Scraper:
    _CHROME_PATHS = [
        "/opt/google/chrome/google-chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]

    _FIXED_UA: Optional[str] = None
    _FIXED_VIEWPORT: Optional[dict] = None
    _PROFILE_DIR = os.environ.get("DGOOGLE_PROFILE_DIR", "/tmp/dgoogle_profile")
    _WARMUP_MARKER = "warmup_done"
    _warmup_blocked_until: float = 0.0
    _WARMUP_BLOCK_SECONDS = 300.0
    _captcha_blocked_until: float = 0.0
    _CAPTCHA_BLOCK_SECONDS = 60.0

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
        try:
            proc = subprocess.Popen(
                ["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.5)
            return proc
        except FileNotFoundError:
            return None

    def _build_chromium_options(self) -> ChromiumOptions:
        if Scraper._FIXED_UA is None:
            Scraper._FIXED_UA = random.choice(_USER_AGENTS)
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
        co.set_argument("--no-first-run")
        co.set_argument("--no-default-browser-check")
        co.set_argument("--password-store=basic")
        co.set_argument("--lang=en-US")
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

    def _serp_search_ele(self, page: ChromiumPage, timeout: float = 10):
        return self._home_search_ele(page, timeout=timeout)

    def _paste_query(self, page: ChromiumPage, query: str) -> None:
        ele = self._home_search_ele(page)
        if not ele:
            raise RuntimeError("homepage search box not found")
        ele.click()
        time.sleep(random.uniform(0.1, 0.25))
        try:
            ele.clear()
        except Exception:
            pass
        ele.input(query)

    def _click_google_search(self, page: ChromiumPage) -> None:
        page.run_js(_BTN_K_JS)

    def _wait_after_navigation(self, page: ChromiumPage, seconds: float = 2.0) -> None:
        time.sleep(random.uniform(seconds * 0.75, seconds * 1.25))

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

    def _solve_captcha(self, page: ChromiumPage) -> bool:
        api_key = os.environ.get("CAPSOLVER_API_KEY")
        if not api_key:
            self.logger.error(
                "[captcha] CAPSOLVER_API_KEY env not set — cannot solve captcha"
            )
            return False

        try:
            import capsolver  # type: ignore
        except Exception as e:
            self.logger.error(f"[captcha] capsolver package not available: {e}")
            return False
        capsolver.api_key = api_key

        sorry_url = self._page_url(page)
        sitekey = page.run_js(
            """
            return (() => {
                const direct = document.querySelector('[data-sitekey]');
                if (direct) {
                    const k = direct.getAttribute('data-sitekey');
                    if (k) return k;
                }
                const iframes = Array.from(document.querySelectorAll('iframe'));
                for (const f of iframes) {
                    const src = f.src || '';
                    const m = src.match(/[?&]k=([^&]+)/);
                    if (m) return m[1];
                }
                return null;
            })();
            """
        )
        if not sitekey:
            self.logger.error(f"[captcha] no recaptcha sitekey on {sorry_url}")
            return False

        self.logger.info(
            f"[captcha] solving via CapSolver, sitekey={str(sitekey)[:10]}..."
        )
        token = None
        last_err = None
        for task_type in (
            "ReCaptchaV2TaskProxyless",
            "ReCaptchaV2EnterpriseTaskProxyless",
        ):
            try:
                solution = capsolver.solve(
                    {
                        "type": task_type,
                        "websiteURL": sorry_url,
                        "websiteKey": sitekey,
                    }
                )
                token = (
                    solution.get("gRecaptchaResponse")
                    if isinstance(solution, dict)
                    else None
                )
                if token:
                    self.logger.info(f"[captcha] token via {task_type} (len={len(token)})")
                    break
                last_err = f"{task_type}: empty token"
            except Exception as e:
                last_err = f"{task_type}: {e}"
                self.logger.warning(f"[captcha] {task_type} failed: {e}")

        if not token:
            self.logger.error(f"[captcha] CapSolver failed: {last_err}")
            return False

        try:
            token_js = json.dumps(token)
            page.run_js(
                f"""
                () => {{
                    const token = {token_js};
                    document.querySelectorAll(
                        'textarea[name="g-recaptcha-response"], textarea[name^="g-recaptcha-response"]'
                    ).forEach(t => {{
                        t.style.display = '';
                        t.value = token;
                        t.innerText = token;
                    }});
                    try {{
                        if (typeof ___grecaptcha_cfg !== 'undefined' && ___grecaptcha_cfg.clients) {{
                            for (const client of Object.values(___grecaptcha_cfg.clients)) {{
                                for (const item of Object.values(client)) {{
                                    if (item && typeof item === 'object') {{
                                        for (const v of Object.values(item)) {{
                                            if (v && typeof v === 'object' && typeof v.callback === 'function') {{
                                                try {{ v.callback(token); }} catch(e) {{}}
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }} catch(e) {{}}
                }}
                """
            )
            page.run_js(
                """
                () => {
                    const f = document.querySelector('form');
                    if (f) f.submit();
                }
                """
            )
            self._wait_after_navigation(page, 2.0)
            if self._is_captcha(self._page_url(page)):
                self.logger.error("[captcha] still on /sorry/ after token submit")
                return False
            self.logger.info(f"[captcha] solved → {self._page_url(page)}")
            return True
        except Exception as e:
            self.logger.error(f"[captcha] token submission failed: {e}")
            return False

    def _handle_captcha_if_needed(self, page: ChromiumPage, query: str, tag: str) -> bool:
        """CAPTCHA면 풀이 시도. 통과(True) / CAPTCHA 아님(True) / 실패(False)."""
        if not self._is_captcha(self._page_url(page)):
            return True
        self.logger.warning(f"[browser] CAPTCHA at {tag}, attempting CapSolver")
        self._dump_debug_artifacts(page, query, f"captcha_{tag}")
        if self._solve_captcha(page):
            return True
        Scraper._captcha_blocked_until = time.time() + self._CAPTCHA_BLOCK_SECONDS
        return False

    def _warmup_if_needed(self, page: ChromiumPage) -> None:
        marker_path = os.path.join(self._PROFILE_DIR, self._WARMUP_MARKER)
        if os.path.exists(marker_path):
            return
        if time.time() < Scraper._warmup_blocked_until:
            self.logger.info("[browser] warmup skipped (CAPTCHA cooldown)")
            return

        self.logger.info("[browser] warmup: fresh profile, dummy search")
        try:
            page.get("https://www.google.com")
            self._wait_after_navigation(page, 2.5)
            if not self._handle_captcha_if_needed(page, "warmup", "warmup_home"):
                Scraper._warmup_blocked_until = time.time() + self._WARMUP_BLOCK_SECONDS
                return

            self._paste_query(page, "weather today")
            time.sleep(random.uniform(0.4, 0.8))
            self._click_google_search(page)
            self._wait_after_navigation(page, 2.5)
            if not self._handle_captcha_if_needed(page, "warmup", "warmup_submit"):
                Scraper._warmup_blocked_until = time.time() + self._WARMUP_BLOCK_SECONDS
                return

            with open(marker_path, "w") as f:
                f.write(str(int(time.time())))
            self.logger.info("[browser] warmup completed")
        except Exception as e:
            self.logger.warning(f"[browser] warmup failed: {e}")

    def _extract_searchbox_suggestions(
        self, page: ChromiumPage, query: str, limit: int
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

        self.logger.info(f"[browser/extract] source={source}, raw={len(raw_items)}")
        if raw_items:
            preview = [str(s)[:80] for s in raw_items[:10]]
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
        text = re.sub(r"\s+", " ", text or "").strip()
        text = re.sub(
            r"\s*(?:Remove|삭제|검색어 삭제)\s*$", "", text, flags=re.IGNORECASE
        )
        return text.strip()

    def _scrape_via_browser(self, query: str, limit: int) -> list:
        """DrissionPage: google.com → 검색 → SERP → 검색창 클릭 → dropdown 추출."""
        results = []
        xvfb_proc = None
        page = None

        try:
            if self._is_linux():
                xvfb_proc = self._start_xvfb()
                if xvfb_proc:
                    os.environ["DISPLAY"] = ":99"
                    print("[dp] Xvfb started on :99")
                else:
                    print("[dp] Xvfb not found")

            page = self._open_page()
            self.logger.info("[browser] DrissionPage Chromium started")

            self._warmup_if_needed(page)

            page.get("https://www.google.com")
            self._wait_after_navigation(page, 2.0)
            if not self._handle_captcha_if_needed(page, query, "home"):
                return results

            try:
                title = page.title
            except Exception:
                title = "?"
            self.logger.info(
                f"[browser] home url={self._page_url(page)}, title={title!r}"
            )

            self._paste_query(page, query)
            time.sleep(random.uniform(0.4, 0.8))
            self._click_google_search(page)
            self._wait_after_navigation(page, 2.0)

            if not self._handle_captcha_if_needed(page, query, "after_submit"):
                return results

            url = self._page_url(page)
            if "/search" not in url:
                self.logger.error(f"[browser] not on SERP after submit: {url}")
                self._dump_debug_artifacts(page, query, "no_serp")
                return results

            self.logger.info(f"[browser] post-search url={url}")

            serp_ele = self._serp_search_ele(page)
            if not serp_ele:
                self.logger.warning("[browser] SERP search box not found")
                self._dump_debug_artifacts(page, query, "no_searchbox")
            else:
                try:
                    serp_ele.click()
                    try:
                        page.wait.ele_loaded(
                            "css:li[data-attrid=AutocompletePrediction]",
                            timeout=1.5,
                        )
                        self.logger.info("[browser] dropdown listbox attached")
                    except Exception:
                        self.logger.warning(
                            "[browser] dropdown wait timeout; extracting anyway"
                        )
                    time.sleep(random.uniform(0.4, 0.8))
                except Exception as e:
                    self.logger.warning(f"[browser] SERP search box click failed: {e}")
                    self._dump_debug_artifacts(page, query, "click_failed")

            results = self._extract_searchbox_suggestions(page, query, limit)
            if results:
                self.logger.info(
                    f"[browser] keywords={[r['keyword'] for r in results]}"
                )
            else:
                self.logger.warning(
                    f"[browser] no suggestions for query={query!r}"
                )

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

        return results

    def scrape_google(self, query: str, limit: int = 30) -> list:
        """SERP 검색창 클릭 후 dropdown 추천어만 반환. autocomplete API 미사용."""
        print(f"[scraper] query={query}, limit={limit}")

        if time.time() < Scraper._captcha_blocked_until:
            cd = Scraper._captcha_blocked_until - time.time()
            self.logger.warning(
                f"[scraper] CAPTCHA cooldown ({cd:.0f}s left), returning empty"
            )
            return []

        for attempt in (1, 2):
            results = self._scrape_via_browser(query, limit)
            if results:
                self.logger.info(
                    f"[scraper] success attempt {attempt}: {len(results)} "
                    f"keywords={[r['keyword'] for r in results]}"
                )
                return results
            if attempt == 1 and time.time() >= Scraper._captcha_blocked_until:
                backoff = random.uniform(5.0, 8.0)
                self.logger.warning(
                    f"[scraper] retry after {backoff:.1f}s"
                )
                time.sleep(backoff)
            else:
                break

        self.logger.error(
            "[scraper] failed — empty list. Check [browser]/[captcha] logs. "
            "Set CAPSOLVER_API_KEY if CAPTCHA persists."
        )
        return []


if __name__ == "__main__":
    print(Scraper().scrape_google("beauty of joseon sunscreen review", limit=10))
