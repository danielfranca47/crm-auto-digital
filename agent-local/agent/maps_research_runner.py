from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .config import AgentConfig

logger = logging.getLogger(__name__)


class MapsResearchRunner:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._driver: Optional[Chrome] = None
        self._main_handle: Optional[str] = None

    # ---------- driver helpers ----------
    def _build_driver(self) -> Chrome:
        options = ChromeOptions()
        options.add_argument(f"--user-data-dir={self.config.user_data_dir}")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1280,1800")
        options.add_argument("--lang=pt-BR")
        if self.config.headless:
            options.add_argument("--headless=new")
        if self.config.chrome_binary:
            options.binary_location = self.config.chrome_binary

        Path(self.config.user_data_dir).mkdir(parents=True, exist_ok=True)
        driver_path = ChromeDriverManager().install()
        driver = Chrome(service=Service(driver_path), options=options)
        self._main_handle = driver.current_window_handle
        return driver

    def _ensure_driver(self) -> Chrome:
        if self._driver is None:
            self._driver = self._build_driver()
        return self._driver

    def _open_isolated_tab(self, driver: Chrome) -> str:
        main_handle = self._main_handle or driver.current_window_handle
        driver.switch_to.new_window("tab")
        handle = driver.current_window_handle
        return handle if handle else main_handle

    def _cleanup_tab(self, driver: Chrome, handle: str) -> None:
        try:
            driver.close()
        except Exception:
            logger.debug("Não foi possível fechar aba temporária")
        try:
            remaining = driver.window_handles
            if self._main_handle and self._main_handle in remaining:
                driver.switch_to.window(self._main_handle)
            elif remaining:
                self._main_handle = remaining[0]
                driver.switch_to.window(self._main_handle)
        except Exception:
            logger.debug("Erro ao restaurar aba principal", exc_info=True)

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    # ---------- helpers ----------
    def _handle_google_consent(self, driver: Chrome) -> None:
        wait = WebDriverWait(driver, 20)
        try:
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='consent']")
            if iframes:
                driver.switch_to.frame(iframes[0])
        except Exception:
            pass

        candidates = [
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Accept') or contains(@aria-label,'Accept'))]"),
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Aceitar') or contains(@aria-label,'Aceitar'))]"),
            (By.XPATH, "//button[@id='L2AGLb']"),
            (By.XPATH, "//button[normalize-space()='Accept all' or .//span[normalize-space()='Accept all']]"),
            (By.XPATH, "//button[normalize-space()='Aceitar tudo' or .//span[normalize-space()='Aceitar tudo']]"),
        ]

        for by, sel in candidates:
            try:
                el = wait.until(EC.element_to_be_clickable((by, sel)))
                el.click()
                time.sleep(1.0)
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                break
            except Exception:
                continue

        try:
            WebDriverWait(driver, 5).until(lambda d: "consent.google" not in d.current_url.lower())
        except TimeoutException:
            pass

    def _split_query_term_location(self, query: str):
        q_low = query.lower()
        seps = [" em ", " no ", " na ", " in ", " at ", " de "]
        for sep in seps:
            if sep in q_low:
                i = q_low.rfind(sep)
                term = query[:i].strip()
                loc = query[i + len(sep):].strip()
                return term, loc
        return query.strip(), None

    def _maps_ui_search(self, driver: Chrome, wait: WebDriverWait, location: str | None, term: str):
        driver.get("https://www.google.com/maps?hl=pt-BR&gl=BR")
        if "consent.google" in driver.current_url.lower():
            self._handle_google_consent(driver)
            if "consent.google" in driver.current_url.lower():
                driver.get("https://www.google.com/maps?hl=pt-BR&gl=BR")
                time.sleep(0.8)

        search_input = wait.until(EC.presence_of_element_located((By.ID, "searchboxinput")))
        search_btn = wait.until(EC.element_to_be_clickable((By.ID, "searchbox-searchbutton")))

        def do_search(text: str):
            search_input.clear()
            search_input.send_keys(text)
            search_btn.click()
            try:
                wait.until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, "div[role='article']")) >= 1
                    or d.find_elements(By.CSS_SELECTOR, "div[role='feed']")
                )
            except Exception:
                pass
            time.sleep(0.8)

        if location:
            do_search(location)
        do_search(term)

    def _harvest_cards(self, driver: Chrome, feed, seen: Dict[str, str]):
        scope = feed if feed is not None else driver
        cards = scope.find_elements(By.CSS_SELECTOR, "div[role='article']")
        if not cards:
            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
            for a in links:
                href = a.get_attribute("href") or ""
                label = a.get_attribute("aria-label") or a.text or ""
                if href and "/maps/place/" in href and href not in seen:
                    seen[href] = label
            return

        for card in cards:
            label = card.get_attribute("aria-label") or ""
            href = ""
            anchor = None
            try:
                anchor = card.find_element(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
            except Exception:
                for a in card.find_elements(By.TAG_NAME, "a"):
                    h = a.get_attribute("href") or ""
                    if "/maps/place/" in h:
                        anchor = a
                        break
            if anchor:
                href = anchor.get_attribute("href") or ""

            if not label:
                try:
                    t = card.find_element(By.CSS_SELECTOR, "[role='heading'], .fontHeadlineSmall, .qBF1Pd")
                    label = t.text.strip()
                except Exception:
                    label = ""

            if href and href not in seen:
                seen[href] = label

    def run_search_fallback(self, payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        query = payload.get("query") or ""
        limit = int(payload.get("limit") or 50)

        driver = self._ensure_driver()
        tab = self._open_isolated_tab(driver)
        try:
            wait = WebDriverWait(driver, 30)
            term, loc = self._split_query_term_location(query)
            self._maps_ui_search(driver, wait, loc, term)

            try:
                feed = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
                )
            except Exception:
                try:
                    feed = WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div[aria-label*='Results'], div[aria-label*='Resultados']")
                        )
                    )
                except Exception:
                    feed = driver

            seen: Dict[str, str] = {}
            attempts = 0
            max_scrolls = 8

            self._harvest_cards(driver, feed, seen)
            while len(seen) < limit and attempts < max_scrolls:
                try:
                    if feed is not None:
                        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed)
                    else:
                        driver.execute_script("window.scrollBy(0, 1000)")
                except Exception:
                    driver.execute_script("window.scrollBy(0, 1000)")
                prev = len(seen)
                time.sleep(random.uniform(1.2, 2.2))
                self._harvest_cards(driver, feed, seen)
                if len(seen) == prev:
                    time.sleep(0.8)
                    self._harvest_cards(driver, feed, seen)
                attempts += 1

            businesses = []
            for href, label in list(seen.items())[:limit]:
                name = label or ""
                if not name:
                    try:
                        name = href.split("/maps/place/")[1].split("/")[0].replace("+", " ")
                    except Exception:
                        name = ""
                businesses.append(
                    {
                        "place_id": "",
                        "name": name,
                        "rating": 0,
                        "address": "",
                        "types": [],
                        "maps_url": href,
                    }
                )

            return {"items": businesses}
        finally:
            self._cleanup_tab(driver, tab)

    # ---------- enrichment ----------
    def _get_text(self, driver: Chrome, wait: WebDriverWait, selectors) -> str:
        for css in selectors:
            try:
                el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
                txt = el.text.strip()
                if txt:
                    return txt
            except Exception:
                continue
        return ""

    def _get_href(self, driver: Chrome, wait: WebDriverWait, selectors) -> str:
        for css in selectors:
            try:
                el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
                href = el.get_attribute("href") or ""
                if href:
                    return href
            except Exception:
                continue
        return ""

    def _norm_rating(self, txt: str) -> float | str:
        if not txt:
            return ""
        try:
            txt2 = txt.strip().replace(",", ".")
            m = re.search(r"\d+(?:[.,]\d+)?", txt2)
            return float(m.group(0).replace(",", ".")) if m else ""
        except Exception:
            return ""

    def _norm_reviews(self, txt: str) -> int | str:
        if not txt:
            return ""
        try:
            m = re.search(r"\d+", txt.replace(".", ""))
            return int(m.group(0)) if m else ""
        except Exception:
            return ""

    def _norm_phone(self, txt: str) -> str:
        if not txt:
            return ""
        digits = re.sub(r"\D+", "", txt)
        return digits or txt

    def _clean_google_redirect(self, url: str) -> str:
        if not url:
            return ""
        try:
            if "google.com" in url and "/url?" in url:
                parts = url.split("q=", 1)
                if len(parts) > 1:
                    return parts[1].split("&")[0]
        except Exception:
            pass
        return url

    def _enrich_single_url(self, driver: Chrome, maps_url: str) -> Dict[str, Any]:
        driver.get(maps_url)
        if "consent.google" in driver.current_url.lower():
            self._handle_google_consent(driver)
            if "consent.google" in driver.current_url.lower():
                driver.get(maps_url)
                time.sleep(0.8)

        wait = WebDriverWait(driver, 25)

        name = self._get_text(driver, wait, [
            "h1.DUwDvf",
            "[role='heading'].DUwDvf",
        ])
        address = self._get_text(driver, wait, [
            "button[data-item-id='address']",
            "button[aria-label^='Endereço:']",
            "button[aria-label^='Address:']",
        ])
        phone = self._get_text(driver, wait, [
            "button[data-item-id^='phone']",
            "button[aria-label^='Telefone:']",
            "button[aria-label^='Phone:']",
            "a[href^='tel:']",
        ])
        website = self._get_href(driver, wait, [
            "a[data-item-id='authority']",
            "a[aria-label^='Website']",
            "a[aria-label^='Site']",
        ])
        rating = self._get_text(driver, wait, [
            "div.F7nice",
            "span[aria-label*='stars']",
        ])
        reviews_count = self._get_text(driver, wait, [
            "button[jsaction*='moreReviews']",
            "a[href^='https://www.google.com/maps/place/'][data-item-id*='review']",
        ])

        return {
            "name": name,
            "address": address,
            "phone": self._norm_phone(phone),
            "website": self._clean_google_redirect(website),
            "rating": self._norm_rating(rating),
            "reviews_count": self._norm_reviews(reviews_count),
            "maps_url": maps_url,
        }

    def run_enrich_fallback(self, payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        urls = payload.get("maps_urls") or []
        driver = self._ensure_driver()
        tab = self._open_isolated_tab(driver)
        items: List[Dict[str, Any]] = []
        try:
            for maps_url in urls:
                try:
                    items.append(self._enrich_single_url(driver, maps_url))
                except Exception as exc:
                    logger.warning("Falha ao enriquecer %s: %s", maps_url, exc)
            return {"items": items}
        finally:
            self._cleanup_tab(driver, tab)
