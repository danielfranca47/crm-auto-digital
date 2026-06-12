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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
        options.add_argument("--window-size=1280,900")
        options.add_argument("--lang=pt-BR")
        # Suprime popup "Restaurar páginas?" de sessão anterior crashada
        options.add_argument("--disable-session-crashed-bubble")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-infobars")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # Não restaurar sessão anterior
        options.add_experimental_option("prefs", {"profile.exit_type": "Normal"})
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
        """
        Fecha diferentes variantes do banner/iframe de consentimento do Google.

        O consentimento aparece em diferentes formatos (iframe, modal ou full-page)
        e com textos traduzidos. Mantemos uma lista de seletores resilientes e
        tentamos cada um em sequência. Essa rotina é defensiva para evitar que o
        banner esconda o campo/botão de pesquisa e cause timeouts.
        """

        wait = WebDriverWait(driver, 25)

        # Alguns flows usam iframe de consentimento; tentamos entrar nele, mas
        # sempre voltamos para o contexto principal depois dos cliques.
        try:
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='consent']")
            if iframes:
                driver.switch_to.frame(iframes[0])
        except Exception:
            pass

        candidates = [
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Accept') or contains(@aria-label,'Accept'))]"),
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Aceitar') or contains(@aria-label,'Aceitar'))]"),
            (By.XPATH, "//button[@id='L2AGLb' or @id='W0wltc']"),
            (By.XPATH, "//button[normalize-space()='Accept all' or .//span[normalize-space()='Accept all']]"),
            (By.XPATH, "//button[normalize-space()='Aceitar tudo' or .//span[normalize-space()='Aceitar tudo']]"),
            (By.XPATH, "//button[normalize-space()='Aceitar' or .//span[normalize-space()='Aceitar']]"),
            (By.CSS_SELECTOR, "button[aria-label*='Aceitar'], button[aria-label*='Accept']"),
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
            WebDriverWait(driver, 6).until(lambda d: "consent.google" not in d.current_url.lower())
        except TimeoutException:
            pass

    def _wait_for_first(self, wait: WebDriverWait, locators, *, clickable: bool = False):
        """Tenta múltiplos seletores e devolve o primeiro que aparecer.

        Cada seletor tem um timeout curto (3s) para não bloquear os seguintes.
        O `wait` passado é usado apenas como referência do driver — o timeout
        real por seletor é fixo em 3s. Após todos os seletores curtos, tenta
        uma última vez com o timeout total do `wait` passado.
        """
        driver = wait._driver
        short_wait = WebDriverWait(driver, 3)

        for by, sel in locators:
            try:
                if clickable:
                    return short_wait.until(EC.element_to_be_clickable((by, sel)))
                return short_wait.until(EC.presence_of_element_located((by, sel)))
            except Exception:
                continue

        # Segunda ronda com o timeout completo (30s) — página pode ainda estar a carregar
        for by, sel in locators:
            try:
                if clickable:
                    return wait.until(EC.element_to_be_clickable((by, sel)))
                return wait.until(EC.presence_of_element_located((by, sel)))
            except Exception:
                continue

        raise TimeoutException("Elemento não encontrado para os seletores fornecidos")

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

    # JS que atravessa Shadow DOM recursivamente à procura de um seletor
    _SHADOW_SEARCH_JS = """
(function deepFind(root, selector) {
    var found = root.querySelector(selector);
    if (found) return found;
    var all = root.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
        if (all[i].shadowRoot) {
            found = deepFind(all[i].shadowRoot, selector);
            if (found) return found;
        }
    }
    return null;
})(document, arguments[0]);
"""

    def _find_in_shadow(self, driver: Chrome, selector: str):
        """Procura um elemento através de shadow roots via JavaScript."""
        return driver.execute_script(self._SHADOW_SEARCH_JS, selector)

    def _get_search_input(self, driver: Chrome, wait: WebDriverWait):
        """
        Obtém o input de pesquisa do Google Maps.
        Google Maps usa Shadow DOM — o #searchboxinput não é acessível via seletores CSS normais.
        Estratégia:
          1. Tentar CSS normal (compatibilidade com versões antigas)
          2. Procurar via JavaScript recursivo no Shadow DOM
          3. Fallback: usar tecla '/' para focar a pesquisa + body como proxy
        """
        # ActionChains importado no topo do módulo

        # 1. Tentar CSS normal (pode funcionar em alguns ambientes)
        for selector in ["#searchboxinput", "input[aria-label*='Pesquis']", "input[aria-label*='Search']"]:
            try:
                el = WebDriverWait(driver, 4).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if el:
                    return el
            except Exception:
                pass

        # 2. Procurar no Shadow DOM via JavaScript
        for selector in [
            "#searchboxinput",
            "input[aria-label*='Pesquise']",
            "input[aria-label*='Pesquisar']",
            "input[aria-label*='Search']",
            "input[placeholder*='Pesquis']",
            "input[placeholder*='Search']",
            "input[jsaction*='search']",
        ]:
            try:
                el = self._find_in_shadow(driver, selector)
                if el:
                    logger.info("Search input encontrado via Shadow DOM: %s", selector)
                    return el
            except Exception:
                pass

        # 3. Fallback: usar atalho de teclado '/' do Google Maps para focar a pesquisa
        logger.info("CSS/Shadow DOM não encontraram o input — usando atalho '/' do Maps")
        try:
            WebDriverWait(driver, 10).until(
                lambda d: "maps.google" in d.current_url or "google.com/maps" in d.current_url
            )
            # Clicar no corpo do mapa e usar '/' para activar a pesquisa
            body = driver.find_element(By.TAG_NAME, "body")
            body.click()
            time.sleep(0.5)
            ActionChains(driver).send_keys("/").perform()
            time.sleep(1.0)
            # Após '/', o input activo deverá ser o de pesquisa
            active = driver.execute_script("return document.activeElement")
            if active and active.tag_name == "input":
                return active
            # Tentar novamente Shadow DOM
            for selector in ["#searchboxinput", "input[aria-label*='Pesquis']"]:
                el = self._find_in_shadow(driver, selector)
                if el:
                    return el
        except Exception as e:
            logger.error("Fallback teclado falhou: %s", e)

        raise TimeoutException("Search input não encontrado (DOM normal nem Shadow DOM)")

    def _maps_ui_search(self, driver: Chrome, wait: WebDriverWait, location: str | None, term: str):
        # Coordenadas neutras (0,0) para não centrar o mapa na localização do utilizador
        driver.get("https://www.google.com/maps/@0,0,3z?hl=pt-BR&gl=BR")
        time.sleep(2.5)  # aguardar redirect inicial do Google antes de verificar consent
        if "consent.google" in driver.current_url.lower():
            self._handle_google_consent(driver)
            time.sleep(1.5)
            if "consent.google" in driver.current_url.lower():
                driver.get("https://www.google.com/maps?hl=pt-BR&gl=BR")
                time.sleep(2.5)

        # Combinar localização e termo numa única pesquisa — mais fiável do que
        # duas pesquisas sequenciais (evita mudança de estado do Maps entre chamadas)
        full_query = f"{term} em {location}" if location else term
        search_input = self._get_search_input(driver, wait)

        # Limpar conteúdo existente com Ctrl+A + Delete (compatível com Shadow DOM)
        try:
            search_input.click()
            time.sleep(0.2)
        except Exception:
            pass
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        time.sleep(0.1)
        ActionChains(driver).send_keys(Keys.DELETE).perform()
        time.sleep(0.1)
        search_input.send_keys(full_query)
        search_input.send_keys(Keys.ENTER)

        try:
            wait.until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "div[role='article']")) >= 1
                or d.find_elements(By.CSS_SELECTOR, "div[role='feed']")
            )
        except Exception:
            pass
        time.sleep(0.8)

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
            # fecha a aba de trabalho (se ainda existir) e depois o driver inteiro
            try:
                self._cleanup_tab(driver, tab)
            except Exception:
                logger.debug("Falha ao limpar aba temporária de pesquisa", exc_info=True)

            # garante que nenhuma janela de Chrome usada para Maps fique aberta
            self.close()

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
            try:
                self._cleanup_tab(driver, tab)
            except Exception:
                logger.debug("Falha ao limpar aba temporária de enriquecimento", exc_info=True)

            self.close()
