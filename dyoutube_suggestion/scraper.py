import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

from DrissionPage import ChromiumOptions, ChromiumPage


class Scraper:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    SEARCH_INPUT_SELECTORS = (
        "input[name='search_query']",
        "input#search",
        "input.ytSearchboxComponentInput",
        "ytd-searchbox input",
        "yt-searchbox input",
        "form[role='search'] input",
    )

    def __init__(self):
        self.logger = logging.getLogger("uvicorn")
        self.crawl_timeout_seconds = int(os.getenv("DRISSION_CRAWL_TIMEOUT_SECONDS", "55"))
        self.page_timeout_seconds = float(os.getenv("DRISSION_PAGE_TIMEOUT_SECONDS", "30"))
        self.input_timeout_seconds = float(os.getenv("DRISSION_INPUT_TIMEOUT_SECONDS", "15"))
        self.dropdown_timeout_seconds = float(os.getenv("DRISSION_DROPDOWN_TIMEOUT_SECONDS", "6"))
        self.use_subprocess = (
            os.getenv("DRISSION_CRAWL_SUBPROCESS", "1") != "0"
            and os.getenv("YOUTUBE_DRISSION_CHILD") != "1"
        )

    def get_suggestions(self, query: str):
        query = (query or "").strip()
        if not query:
            return self._build_suggestion_response(query, [])

        if self.use_subprocess:
            return self._get_suggestions_via_subprocess(query)

        return self._get_suggestions_direct(query)

    def _get_suggestions_via_subprocess(self, query: str):
        env = os.environ.copy()
        env["YOUTUBE_DRISSION_CHILD"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        child_code = (
            "import json, logging, sys; "
            "logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s'); "
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
            detail = f"DrissionPage subprocess timed out after {self.crawl_timeout_seconds}s"
            stderr = self._stringify_output(e.stderr)
            if stderr:
                detail = f"{detail}: {stderr[-500:]}"
            self.logger.warning(f"[YOUTUBE] {detail}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=detail,
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if stderr.strip():
            for line in stderr.strip().splitlines()[-15:]:
                self.logger.info(f"[YOUTUBE_CHILD] {line}")

        if completed.returncode != 0:
            detail = (stderr or stdout or f"child exit code {completed.returncode}")[-500:]
            self.logger.warning(f"[YOUTUBE] DrissionPage subprocess failed: {detail}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=detail,
            )

        try:
            json_line = next(
                line for line in reversed(stdout.strip().splitlines())
                if line.strip().startswith("{")
            )
            return json.loads(json_line)
        except (StopIteration, json.JSONDecodeError) as e:
            detail = f"Invalid DrissionPage subprocess output: {e}; stdout={stdout[-300:]}"
            self.logger.warning(f"[YOUTUBE] {detail}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=detail,
            )

    def _get_suggestions_direct(self, query: str):
        page = None
        xvfb_proc = None
        profile_dir = tempfile.mkdtemp(prefix="dyoutube_suggestion_profile_")
        try:
            xvfb_proc = self._start_xvfb_if_needed()
            page = self._open_page(profile_dir)
            suggestions = self._crawl_suggestions(page, query)
            result = self._build_suggestion_response(query, suggestions)
            self.logger.info(f"[YOUTUBE] Final suggestion result: {result}")
            return result
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] DrissionPage suggestion crawl failed: {e}")
            return self._build_suggestion_response(
                query,
                [],
                error="youtube_unreachable",
                detail=str(e),
            )
        finally:
            if page is not None:
                try:
                    page.quit()
                except Exception as e:
                    self.logger.debug(f"[YOUTUBE] Error closing DrissionPage: {e}")
            if xvfb_proc is not None:
                try:
                    xvfb_proc.terminate()
                    xvfb_proc.wait(timeout=3)
                except Exception:
                    try:
                        xvfb_proc.kill()
                    except Exception:
                        pass
            shutil.rmtree(profile_dir, ignore_errors=True)

    def _crawl_suggestions(self, page: ChromiumPage, query: str):
        self.logger.info(f"[YOUTUBE] Starting DrissionPage crawl for: {query}")

        home_url = "https://www.youtube.com/?hl=ko&gl=KR"
        self.logger.info(f"[YOUTUBE] Opening YouTube home: {home_url}")
        page.get(home_url, timeout=self.page_timeout_seconds)
        self._set_locale_cookies(page)
        self._short_wait(1.0, 1.8)
        self._accept_consent_if_present(page)
        self._log_page_state(page, "home_loaded")

        search_input = self._find_search_input(page, self.input_timeout_seconds)
        if not search_input:
            self._dump_debug_artifacts(page, query, "home_search_input_not_found")
            raise RuntimeError("YouTube home search input not found")

        self._submit_search(page, search_input, query)
        if not self._wait_for_results_page(page, query):
            self._dump_debug_artifacts(page, query, "results_page_not_loaded")
            raise RuntimeError(f"YouTube search results page did not load: {self._page_url(page)}")
        self._log_page_state(page, "results_loaded")

        results_input = self._find_search_input(page, self.input_timeout_seconds)
        if not results_input:
            self._dump_debug_artifacts(page, query, "results_search_input_not_found")
            raise RuntimeError("YouTube results search input not found")

        self._click_results_search_box(page, results_input)
        suggestions = self._wait_for_dropdown_suggestions(page)
        if not suggestions:
            self._dump_debug_artifacts(page, query, "suggestions_not_found")
            self.logger.warning("[YOUTUBE] Dropdown suggestions were not found after clicking results search box")
        return self._expand_ellipsis_suggestions(suggestions, query)

    def _open_page(self, profile_dir: str):
        co = ChromiumOptions()
        co.headless(False)
        chrome_path = self._find_chrome()
        if chrome_path:
            co.set_browser_path(chrome_path)
        else:
            self.logger.warning("[YOUTUBE] Chrome executable not found explicitly; DrissionPage will use default discovery")
        co.set_user_data_path(profile_dir)
        co.auto_port(True)

        width = random.randint(1700, 1920)
        height = random.randint(900, 1080)
        for arg in (
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--mute-audio",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--disable-infobars",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=Translate,MediaRouter",
            "--no-first-run",
            "--no-default-browser-check",
            "--password-store=basic",
            "--lang=ko-KR",
            "--accept-lang=ko-KR,ko,en-US,en",
            f"--user-agent={self.USER_AGENT}",
            f"--window-size={width},{height}",
        ):
            co.set_argument(arg)

        if os.getenv("YOUTUBE_SYSTEM_DNS_FAILED") == "1" or os.getenv("YOUTUBE_FORCE_CHROME_DOH") == "1":
            co.set_argument("--enable-features=DnsOverHttps")
            co.set_argument("--dns-over-https-mode=secure")
            co.set_argument("--dns-over-https-templates=https://dns.google/dns-query")
            co.set_argument(
                "--host-resolver-rules=MAP dns.google 8.8.8.8,"
                "MAP cloudflare-dns.com 1.1.1.1,"
                "EXCLUDE localhost,EXCLUDE 127.0.0.1"
            )
            self.logger.info("[YOUTUBE] Chrome DNS-over-HTTPS enabled for DrissionPage")

        page = ChromiumPage(co)
        page.set.timeouts(base=self.page_timeout_seconds, page_load=self.page_timeout_seconds)
        self.logger.info(
            "[YOUTUBE] DrissionPage Chromium started: "
            f"chrome={chrome_path or 'default'}, profile={profile_dir}, "
            f"display={os.getenv('DISPLAY', '')}, headless=False"
        )
        return page

    def _find_chrome(self):
        candidates = [
            os.getenv("DRISSION_CHROME_PATH", ""),
            "/usr/bin/google-chrome",
            "/opt/google/chrome/google-chrome",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "google-chrome",
            "chrome",
        ]
        for candidate in candidates:
            if not candidate:
                continue
            if os.path.isabs(candidate):
                if os.path.exists(candidate):
                    return candidate
            else:
                resolved = shutil.which(candidate)
                if resolved:
                    return resolved
        return None

    def _start_xvfb_if_needed(self):
        if sys.platform != "linux" or os.getenv("DRISSION_START_XVFB", "1") == "0":
            return None
        if os.getenv("DRISSION_USE_EXISTING_DISPLAY", "0") == "1" and os.getenv("DISPLAY"):
            self.logger.info(f"[YOUTUBE] Using existing DISPLAY={os.getenv('DISPLAY')}")
            return None
        if not shutil.which("Xvfb"):
            self.logger.warning("[YOUTUBE] Xvfb not found; Chrome will start without virtual display")
            return None

        fixed_display = os.getenv("DRISSION_XVFB_DISPLAY")
        last_error = ""
        for attempt in range(1, 4):
            display = fixed_display or f":{random.randint(90, 199)}"
            os.environ["DISPLAY"] = display
            proc = subprocess.Popen(
                ["Xvfb", display, "-screen", "0", "1920x1080x24", "-ac", "+extension", "RANDR"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.6)
            if proc.poll() is None:
                self.logger.info(f"[YOUTUBE] Xvfb started on {display} (attempt {attempt})")
                return proc

            try:
                last_error = proc.stderr.read() if proc.stderr else ""
            except Exception:
                last_error = ""
            self.logger.warning(
                f"[YOUTUBE] Xvfb start failed on {display} "
                f"(attempt {attempt}/3): {last_error[-300:]}"
            )
            if fixed_display:
                break

        raise RuntimeError(f"Xvfb failed to start: {last_error[-500:]}")

    def _set_locale_cookies(self, page: ChromiumPage):
        script = """
        document.cookie = 'PREF=hl=ko&gl=KR; path=/; domain=.youtube.com; max-age=31536000; SameSite=Lax';
        document.cookie = 'CONSENT=YES+cb.20210328-17-p0.ko+FX+667; path=/; domain=.youtube.com; max-age=31536000; SameSite=Lax';
        document.cookie = 'SOCS=CAI; path=/; domain=.youtube.com; max-age=31536000; SameSite=Lax';
        return document.cookie;
        """
        try:
            cookie_preview = page.run_js(script)
            self.logger.info(f"[YOUTUBE] Locale cookies set: {str(cookie_preview)[:160]}")
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] Failed to set locale cookies: {e}")

    def _accept_consent_if_present(self, page: ChromiumPage):
        script = """
        const labels = ['모두 동의', '동의', 'Accept all', 'I agree'];
        const nodes = Array.from(document.querySelectorAll('button, tp-yt-paper-button, ytd-button-renderer'));
        const target = nodes.find((node) => {
            const text = (node.innerText || node.textContent || '').trim();
            return labels.some((label) => text.includes(label));
        });
        if (target) {
            target.click();
            return (target.innerText || target.textContent || '').trim();
        }
        return '';
        """
        try:
            clicked = page.run_js(script)
            if clicked:
                self.logger.info(f"[YOUTUBE] Consent accepted: {clicked!r}")
                self._short_wait(0.8, 1.4)
        except Exception as e:
            self.logger.debug(f"[YOUTUBE] Consent check skipped: {e}")

    def _find_search_input(self, page: ChromiumPage, timeout: float):
        deadline = time.time() + timeout
        last_error = None
        while time.time() < deadline:
            for selector in self.SEARCH_INPUT_SELECTORS:
                try:
                    ele = page.ele(f"css:{selector}", timeout=0.5)
                    if ele:
                        self.logger.info(f"[YOUTUBE] Search input found by selector: {selector}")
                        return ele
                except Exception as e:
                    last_error = e
            self._short_wait(0.2, 0.35)
        self.logger.warning(f"[YOUTUBE] Search input not found within {timeout}s; last_error={last_error}")
        return None

    def _submit_search(self, page: ChromiumPage, search_input, query: str):
        search_input.click()
        self._short_wait(0.2, 0.45)
        self._clear_search_input(page, search_input)

        for char in query:
            search_input.input(char)
            time.sleep(random.uniform(0.02, 0.07))
        self._short_wait(0.35, 0.75)

        submitted = False
        try:
            search_input.input("\n")
            submitted = True
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] Enter submit failed: {e}")

        if not submitted:
            script = """
            const button = document.querySelector('button#search-icon-legacy, ytd-searchbox button, yt-searchbox button');
            if (button) {
                button.click();
                return true;
            }
            return false;
            """
            submitted = bool(page.run_js(script))

        self.logger.info(f"[YOUTUBE] Search submitted: {submitted}")
        self._short_wait(2.0, 3.0)

    def _clear_search_input(self, page: ChromiumPage, search_input):
        try:
            page.run_js(
                """
                const el = document.querySelector("input[name='search_query'], input#search, input.ytSearchboxComponentInput");
                if (el) {
                    el.focus();
                    el.value = '';
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
                return false;
                """
            )
        except Exception:
            pass
        try:
            search_input.clear()
        except Exception:
            pass

    def _wait_for_results_page(self, page: ChromiumPage, query: str):
        deadline = time.time() + self.page_timeout_seconds
        last_url = ""
        while time.time() < deadline:
            current_url = self._page_url(page)
            if current_url != last_url:
                self.logger.info(f"[YOUTUBE] Waiting results page, current_url={current_url}")
                last_url = current_url
            if "/results" in current_url and "search_query=" in current_url:
                return True
            self._short_wait(0.25, 0.5)
        return False

    def _click_results_search_box(self, page: ChromiumPage, search_input):
        try:
            search_input.click()
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] Native search box click failed: {e}")

        script = """
        const el = document.querySelector("input[name='search_query'], input#search, input.ytSearchboxComponentInput");
        if (!el) return false;
        el.scrollIntoView({block: 'center', inline: 'center'});
        el.focus();
        for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
            el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
        }
        return true;
        """
        try:
            page.run_js(script)
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] JS search box click failed: {e}")
        self._short_wait(0.5, 0.9)
        self._log_page_state(page, "results_search_box_clicked")

    def _wait_for_dropdown_suggestions(self, page: ChromiumPage):
        deadline = time.time() + self.dropdown_timeout_seconds
        suggestions = []
        while time.time() < deadline:
            suggestions = self._extract_dropdown_suggestions(page)
            if suggestions:
                self.logger.info(f"[YOUTUBE] Dropdown suggestions found: {suggestions}")
                return suggestions
            self._short_wait(0.2, 0.35)
        self.logger.warning(f"[YOUTUBE] Dropdown suggestions not found within {self.dropdown_timeout_seconds}s")
        return suggestions

    def _extract_dropdown_suggestions(self, page: ChromiumPage):
        script = """
        const result = [];
        const pushText = (el) => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            if (rect.width <= 0 || rect.height <= 0 || style.visibility === 'hidden' || style.display === 'none') {
                return;
            }
            const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
            if (text) result.push(text);
        };

        const input = document.querySelector("input[name='search_query'], input#search, input.ytSearchboxComponentInput");
        const controls = input && input.getAttribute('aria-controls');
        const controlled = controls && document.getElementById(controls);
        if (controlled) {
            controlled.querySelectorAll("[role='option'], li, div.ytSuggestionComponentSuggestion").forEach(pushText);
        }

        document.querySelectorAll(
            "div.ytSuggestionComponentSuggestion div.ytSuggestionComponentText, " +
            "div.ytSuggestionComponentSuggestion, " +
            "[role='option'], " +
            "li.sbsb_c .sbqs_c, " +
            "li.sbsb_c"
        ).forEach(pushText);

        return result;
        """
        try:
            return self._dedupe_suggestions(page.run_js(script) or [])
        except Exception as e:
            self.logger.warning(f"[YOUTUBE] Dropdown extraction failed: {e}")
            return []

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

    def _page_url(self, page: ChromiumPage):
        try:
            return page.url or ""
        except Exception:
            return ""

    def _log_page_state(self, page: ChromiumPage, label: str):
        script = """
        const inputs = Array.from(document.querySelectorAll('input')).slice(0, 12).map((el) => {
            const rect = el.getBoundingClientRect();
            return {
                name: el.getAttribute('name') || '',
                id: el.id || '',
                cls: el.className || '',
                type: el.type || '',
                value: el.value || '',
                aria: el.getAttribute('aria-label') || '',
                controls: el.getAttribute('aria-controls') || '',
                w: Math.round(rect.width),
                h: Math.round(rect.height)
            };
        });
        const body = (document.body && document.body.innerText || '').replace(/\\s+/g, ' ').trim();
        return {
            readyState: document.readyState,
            ytdApp: !!document.querySelector('ytd-app'),
            inputCount: document.querySelectorAll('input').length,
            searchboxCount: document.querySelectorAll("ytd-searchbox, yt-searchbox, input[name='search_query'], input#search").length,
            suggestionCount: document.querySelectorAll("div.ytSuggestionComponentSuggestion, [role='option'], li.sbsb_c").length,
            inputs,
            bodyPreview: body.slice(0, 240)
        };
        """
        try:
            state = page.run_js(script)
            self.logger.info(
                f"[YOUTUBE_DEBUG] {label}: url={self._page_url(page)}, "
                f"title={page.title!r}, state={state}"
            )
        except Exception as e:
            self.logger.info(
                f"[YOUTUBE_DEBUG] {label}: url={self._page_url(page)}, "
                f"title_unavailable_error={e}"
            )

    def _dump_debug_artifacts(self, page: ChromiumPage, query: str, tag: str):
        if os.getenv("YOUTUBE_DEBUG_DUMP", "0") != "1":
            return
        safe_query = re.sub(r"[^a-zA-Z0-9가-힣]+", "_", query)[:40]
        base = f"/tmp/dyoutube_suggestion_{tag}_{safe_query}_{int(time.time())}"
        html_path = f"{base}.html"
        png_path = f"{base}.png"
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.html or "")
            self.logger.warning(f"[YOUTUBE_DEBUG] html dumped: {html_path}")
        except Exception as e:
            self.logger.warning(f"[YOUTUBE_DEBUG] html dump failed: {e}")
        try:
            page.get_screenshot(path=png_path, full_page=True)
            self.logger.warning(f"[YOUTUBE_DEBUG] screenshot dumped: {png_path}")
        except Exception as e:
            self.logger.warning(f"[YOUTUBE_DEBUG] screenshot dump failed: {e}")

    def _short_wait(self, low: float, high: float):
        time.sleep(random.uniform(low, high))

    def _stringify_output(self, value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return str(value)

    def get_list(self, query: str, limit: int = 30):
        self.logger.warning("[YOUTUBE] get_list is not supported by dyoutube_suggestion")
        return []
