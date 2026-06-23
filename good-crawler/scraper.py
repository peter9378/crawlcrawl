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

from DrissionPage import ChromiumOptions, ChromiumPage


class YouTubeCrawler:
    HOME_URL = "https://www.youtube.com"
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
        self.page_timeout = float(os.getenv("CRAWLER_PAGE_TIMEOUT", "35"))
        self.input_timeout = float(os.getenv("CRAWLER_INPUT_TIMEOUT", "15"))
        self.results_timeout = float(os.getenv("CRAWLER_RESULTS_TIMEOUT", "35"))
        self.load_mode = os.getenv("DRISSION_LOAD_MODE", "eager").lower()
        if self.load_mode == "none":
            self.load_mode = "eager"

    def search(self, query: str, limit: int = 10):
        query = (query or "").strip()
        if not query:
            return {"query": query, "result": []}

        page = None
        xvfb_proc = None
        profile_dir = tempfile.mkdtemp(prefix="good_crawler_profile_")

        try:
            xvfb_proc = self._start_xvfb_if_needed()
            page = self._open_page(profile_dir)
            results = self._run_search_flow(page, query, limit)
            return {"query": query, "result": results}
        except Exception as e:
            self.logger.warning("[YOUTUBE] crawl failed: %s", e)
            return {
                "query": query,
                "result": [],
                "error": "crawl_failed",
                "detail": str(e)[:1000],
            }
        finally:
            if page is not None:
                try:
                    page.quit()
                except Exception as e:
                    self.logger.debug("[YOUTUBE] page.quit failed: %s", e)
            if xvfb_proc is not None:
                self._stop_process(xvfb_proc)
            shutil.rmtree(profile_dir, ignore_errors=True)

    def _run_search_flow(self, page: ChromiumPage, query: str, limit: int):
        self.logger.info("[YOUTUBE] opening home: %s", self.HOME_URL)
        self._load_page(page, self.HOME_URL, "home")
        self._accept_consent_if_present(page)

        search_input = self._find_search_input(page)
        if not search_input:
            self._log_page_state(page, "home_input_not_found")
            raise RuntimeError("YouTube home search input not found")

        self._paste_query_and_submit(page, search_input, query)
        if not self._wait_for_results_page(page):
            self._log_page_state(page, "results_not_loaded")
            raise RuntimeError(f"YouTube results page did not load: {self._page_url(page)}")

        self._wait_for_result_items(page)
        self._log_page_state(page, "results_loaded")
        results = self._extract_results(page, limit)
        self.logger.info("[YOUTUBE] extracted %s results", len(results))
        return results

    def _open_page(self, profile_dir: str):
        co = ChromiumOptions()
        co.headless(False)
        co.new_env(True)
        chrome_path = self._find_chrome()
        if chrome_path:
            co.set_browser_path(chrome_path)

        co.set_user_data_path(profile_dir)
        co.auto_port(True)
        co.set_load_mode(self.load_mode)
        co.set_user_agent(self._build_user_agent(chrome_path))
        co.set_pref("intl.accept_languages", "ko-KR,ko,en-US,en")
        co.set_pref("profile.default_content_setting_values.notifications", 2)

        width = random.randint(1366, 1600)
        height = random.randint(768, 950)
        for arg in (
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-quic",
            "--mute-audio",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--lang=ko-KR",
            "--accept-lang=ko-KR,ko,en-US,en",
            f"--window-size={width},{height}",
        ):
            co.set_argument(arg)

        page = ChromiumPage(co)
        page.set.timeouts(base=self.page_timeout, page_load=self.page_timeout)
        self._install_stealth_scripts(page)
        self.logger.info(
            "[YOUTUBE] Chromium started chrome=%s profile=%s display=%s load_mode=%s",
            chrome_path or "default",
            profile_dir,
            os.getenv("DISPLAY", ""),
            self.load_mode,
        )
        return page

    def _install_stealth_scripts(self, page: ChromiumPage):
        script = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        window.chrome = window.chrome || {runtime: {}};
        """
        try:
            page.add_init_js(script)
            page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source=script)
        except Exception as e:
            self.logger.debug("[YOUTUBE] stealth script install failed: %s", e)

    def _load_page(self, page: ChromiumPage, url: str, label: str):
        last_error = None
        for attempt in range(1, 3):
            try:
                loaded = page.get(url, timeout=self.page_timeout, retry=0)
                self.logger.info(
                    "[YOUTUBE] %s load attempt %s returned=%s url=%s",
                    label,
                    attempt,
                    loaded,
                    self._page_url(page),
                )
            except Exception as e:
                last_error = e
                self.logger.warning("[YOUTUBE] %s load attempt %s failed: %s", label, attempt, e)
                self._stop_loading(page)

            if self._has_youtube_dom(page):
                return
            if self._is_chrome_error_page(page):
                self._log_page_state(page, f"{label}_chrome_error")
                raise RuntimeError(f"YouTube opened as Chrome error page: {label}")

            self._log_page_state(page, f"{label}_dom_empty_attempt_{attempt}")
            self._stop_loading(page)
            time.sleep(1.0)

        if last_error:
            raise RuntimeError(f"Failed to load {url}: {last_error}") from last_error
        raise RuntimeError(f"Failed to load {url}: DOM was empty")

    def _find_search_input(self, page: ChromiumPage):
        deadline = time.time() + self.input_timeout
        while time.time() < deadline:
            for selector in self.SEARCH_INPUT_SELECTORS:
                try:
                    ele = page.ele(f"css:{selector}", timeout=0.4)
                    if ele:
                        self.logger.info("[YOUTUBE] search input found selector=%s", selector)
                        return ele
                except Exception:
                    pass
            time.sleep(0.25)
        return None

    def _paste_query_and_submit(self, page: ChromiumPage, search_input, query: str):
        try:
            search_input.click()
        except Exception as e:
            self.logger.debug("[YOUTUBE] native search input click failed: %s", e)

        query_json = json.dumps(query, ensure_ascii=False)
        script = """
        const query = __QUERY__;
        const el = document.querySelector("input[name='search_query'], input#search, input.ytSearchboxComponentInput");
        if (!el) return {ok: false, reason: 'input_not_found'};
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
        el.focus();
        if (setter) setter.call(el, '');
        else el.value = '';
        el.dispatchEvent(new Event('input', {bubbles: true}));

        try {
            const data = new DataTransfer();
            data.setData('text/plain', query);
            el.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: data
            }));
        } catch (e) {}

        if (setter) setter.call(el, query);
        else el.value = query;
        el.dispatchEvent(new InputEvent('input', {
            bubbles: true,
            cancelable: true,
            inputType: 'insertFromPaste',
            data: query
        }));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        return {ok: true, value: el.value};
        """.replace("__QUERY__", query_json)
        state = page.run_js(script)
        self.logger.info("[YOUTUBE] pasted query state=%s", state)
        time.sleep(random.uniform(0.4, 0.8))

        try:
            search_input.input("\n")
            submitted = True
        except Exception:
            submitted = bool(page.run_js(
                """
                const button = document.querySelector('button#search-icon-legacy, ytd-searchbox button, yt-searchbox button');
                if (!button) return false;
                button.click();
                return true;
                """
            ))
        self.logger.info("[YOUTUBE] submitted=%s", submitted)

    def _wait_for_results_page(self, page: ChromiumPage):
        deadline = time.time() + self.results_timeout
        last_url = ""
        while time.time() < deadline:
            current_url = self._page_url(page)
            if current_url != last_url:
                self.logger.info("[YOUTUBE] waiting results url=%s", current_url)
                last_url = current_url
            if "/results" in current_url and "search_query=" in current_url:
                return True
            if self._is_chrome_error_page(page):
                raise RuntimeError("Chrome error page after search submit")
            time.sleep(0.35)
        return False

    def _wait_for_result_items(self, page: ChromiumPage):
        deadline = time.time() + 10
        while time.time() < deadline:
            if page.run_js(
                """
                return document.querySelectorAll(
                    'ytd-video-renderer, ytd-reel-item-renderer, ytm-shorts-lockup-view-model'
                ).length > 0;
                """
            ):
                return True
            time.sleep(0.35)
        return False

    def _extract_results(self, page: ChromiumPage, limit: int):
        script = """
        const limit = __LIMIT__;
        const absUrl = (href) => {
            if (!href) return '';
            try { return new URL(href, location.origin).toString(); }
            catch (e) { return href; }
        };
        const clean = (text) => (text || '').replace(/\\s+/g, ' ').trim();
        const results = [];
        const seen = new Set();
        const nodes = document.querySelectorAll(
            'ytd-video-renderer, ytd-reel-item-renderer, ytm-shorts-lockup-view-model'
        );

        for (const node of nodes) {
            let link = node.querySelector('a#video-title, a.yt-simple-endpoint[href*="/watch"], a[href*="/shorts/"]');
            if (!link) continue;
            const href = link.getAttribute('href') || '';
            const url = absUrl(href);
            if (!url || seen.has(url)) continue;

            const title =
                clean(link.getAttribute('title')) ||
                clean(link.getAttribute('aria-label')) ||
                clean(link.innerText || link.textContent);
            if (!title) continue;

            const channel = clean(
                node.querySelector('ytd-channel-name #text, #channel-name #text, .yt-lockup-metadata-view-model-wiz__metadata-row')?.textContent
            );
            const metadata = clean(
                node.querySelector('#metadata-line, .metadata, .yt-lockup-metadata-view-model-wiz__metadata')?.textContent
            );

            seen.add(url);
            results.push({
                rank: results.length + 1,
                title,
                url,
                channel,
                metadata,
            });
            if (results.length >= limit) break;
        }
        return results;
        """.replace("__LIMIT__", str(int(limit)))
        return page.run_js(script) or []

    def _has_youtube_dom(self, page: ChromiumPage):
        try:
            return bool(page.run_js(
                """
                return !!(
                    document.querySelector('ytd-app') ||
                    document.querySelector("input[name='search_query'], input#search, input.ytSearchboxComponentInput")
                );
                """
            ))
        except Exception:
            return False

    def _accept_consent_if_present(self, page: ChromiumPage):
        script = """
        const labels = ['모두 동의', '동의', 'Accept all', 'I agree'];
        const nodes = Array.from(document.querySelectorAll('button, tp-yt-paper-button, ytd-button-renderer'));
        const target = nodes.find((node) => {
            const text = (node.innerText || node.textContent || '').trim();
            return labels.some((label) => text.includes(label));
        });
        if (!target) return '';
        target.click();
        return (target.innerText || target.textContent || '').trim();
        """
        try:
            clicked = page.run_js(script)
            if clicked:
                self.logger.info("[YOUTUBE] consent clicked=%r", clicked)
                time.sleep(1.0)
        except Exception:
            pass

    def _find_chrome(self):
        candidates = (
            os.getenv("DRISSION_CHROME_PATH", ""),
            "/usr/bin/google-chrome",
            "/opt/google/chrome/google-chrome",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "google-chrome",
            "chrome",
        )
        for candidate in candidates:
            if not candidate:
                continue
            if os.path.isabs(candidate) and os.path.exists(candidate):
                return candidate
            if not os.path.isabs(candidate):
                resolved = shutil.which(candidate)
                if resolved:
                    return resolved
        return None

    def _build_user_agent(self, chrome_path: str):
        if chrome_path:
            try:
                completed = subprocess.run(
                    [chrome_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                version_text = (completed.stdout or completed.stderr or "").strip()
                match = re.search(r"(\d+)\.\d+\.\d+\.\d+", version_text)
                if match:
                    major = match.group(1)
                    return (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        f"Chrome/{major}.0.0.0 Safari/537.36"
                    )
            except Exception:
                pass
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        )

    def _start_xvfb_if_needed(self):
        if sys.platform != "linux" or os.getenv("CRAWLER_START_XVFB", "1") == "0":
            return None
        if os.getenv("DISPLAY") and os.getenv("CRAWLER_USE_EXISTING_DISPLAY", "0") == "1":
            return None
        if not shutil.which("Xvfb"):
            self.logger.warning("[YOUTUBE] Xvfb not found")
            return None

        for attempt in range(1, 4):
            display = f":{random.randint(90, 199)}"
            os.environ["DISPLAY"] = display
            proc = subprocess.Popen(
                ["Xvfb", display, "-screen", "0", "1600x950x24", "-ac", "+extension", "RANDR"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.5)
            if proc.poll() is None:
                self.logger.info("[YOUTUBE] Xvfb started display=%s attempt=%s", display, attempt)
                return proc
            self._stop_process(proc)
        raise RuntimeError("Xvfb failed to start")

    def _stop_process(self, proc):
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _page_url(self, page: ChromiumPage):
        try:
            return page.url or ""
        except Exception:
            return ""

    def _is_chrome_error_page(self, page: ChromiumPage):
        current_url = self._page_url(page)
        if current_url.startswith("chrome-error://"):
            return True
        try:
            return bool(page.run_js(
                """
                const text = (document.body && document.body.innerText || '').replace(/\\s+/g, ' ');
                return text.includes('ERR_NAME_NOT_RESOLVED') ||
                    text.includes('ERR_CONNECTION') ||
                    text.includes('사이트에 연결할 수 없음') ||
                    text.includes("This site can’t be reached");
                """
            ))
        except Exception:
            return False

    def _stop_loading(self, page: ChromiumPage):
        try:
            page.stop_loading()
        except Exception:
            pass

    def _log_page_state(self, page: ChromiumPage, label: str):
        script = """
        const body = (document.body && document.body.innerText || '').replace(/\\s+/g, ' ').trim();
        return {
            readyState: document.readyState,
            title: document.title,
            href: location.href,
            ytdApp: !!document.querySelector('ytd-app'),
            inputCount: document.querySelectorAll('input').length,
            videoCount: document.querySelectorAll('ytd-video-renderer, ytd-reel-item-renderer, ytm-shorts-lockup-view-model').length,
            bodyPreview: body.slice(0, 300)
        };
        """
        try:
            self.logger.info("[YOUTUBE_DEBUG] %s: %s", label, page.run_js(script))
        except Exception as e:
            self.logger.info("[YOUTUBE_DEBUG] %s failed: %s", label, e)
