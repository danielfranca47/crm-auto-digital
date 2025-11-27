# modules/maps_searcher.py
import time
import random
from urllib.parse import quote_plus

import googlemaps
from . import config

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException


class MapsSearcher:
    def __init__(self):
        self.gmaps_client = None
        self.api_quota_available = True
        api_key = getattr(config, "GOOGLE_MAPS_API_KEY", "")
        if api_key:
            self.gmaps_client = googlemaps.Client(key=api_key)

    def search_businesses(self, query: str, limit: int = 50):
        """
        Busca híbrida: tenta API (Places/legacy); se falhar ou não houver chave, usa Selenium.
        Retorna lista de dicts com campos básicos.
        """
        if self.gmaps_client and self.api_quota_available:
            try:
                return self._search_via_api(query, limit)
            except Exception as e:
                print(f"[MapsSearcher] API falhou: {e}. Usando Selenium...")
                self.api_quota_available = False

        return self._search_via_selenium(query, limit)

    def _search_via_api(self, query: str, limit: int):
        """Busca usando Google Maps API (Places Text Search legacy)."""
        results = []
        resp = self.gmaps_client.places(query=query, type="establishment")
        results.extend(resp.get("results", []))
        while "next_page_token" in resp and len(results) < limit:
            time.sleep(2)
            resp = self.gmaps_client.places(page_token=resp["next_page_token"])
            results.extend(resp.get("results", []))
        businesses = []
        for place in results[:limit]:
            pid = place.get("place_id", "")
            businesses.append({
                "place_id": pid,
                "name": place.get("name", ""),
                "rating": place.get("rating", 0),
                "address": place.get("formatted_address", ""),
                "types": place.get("types", []),
                # maps_url canônica pelo place_id (boa para abrir/testar)
                "maps_url": f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else "",
            })
        return businesses

    def _build_driver(self):
        """Chrome headless com ajustes de estabilidade."""
        opts = Options()
        # opts.add_argument("--headless=new") (Coloca como comentário este trecho abaixo para ver a tela)
        opts.add_argument("--headless=new")

        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--window-size=1280,1800")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--lang=en-US")
        ua_list = getattr(config, "USER_AGENTS", [])
        ua = ua_list[0] if ua_list else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        opts.add_argument(f"--user-agent={ua}")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=opts)


    def _dismiss_banners(self, driver):
        """Tenta dispensar banners de consentimento."""
        try:
            selectors = [
                "button[aria-label*='Accept']",
                "button[aria-label*='I agree']",
                "button[aria-label*='Aceitar']",
                "button[aria-label*='Concordo']",
                "button[aria-label*='Accept all']",
            ]
            for sel in selectors:
                btns = driver.find_elements(By.CSS_SELECTOR, sel)
                if btns:
                    btns[0].click()
                    time.sleep(0.8)
                    break
        except Exception:
            pass

    def _search_via_selenium(self, query: str, limit: int):
        """
        Fallback Selenium: usa explicit waits para o painel lateral e os cards.
        Coleta (name, maps_url) e deixa detalhes para a Fase 3.
        """
        print("[MapsSearcher] Usando fallback Selenium...")
        driver = self._build_driver()
        try:
            wait = WebDriverWait(driver, 30)

            # 1) Separar termo e localização e usar a UI do Maps para ancorar na cidade
            term, loc = self._split_query_term_location(query)
            self._maps_ui_search(driver, wait, loc, term)

            # 2) Achar o painel lateral (feed) ou usar a página como escopo
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
                    feed = driver  # fallback: usa a página inteira

            seen = {}  # href -> label
            attempts = 0
            max_scrolls = max(8, getattr(config, "MAX_SCROLL_ATTEMPTS", 5))

            def harvest():
                """Coleta href/título a partir dos cards do painel."""
                scope = feed if feed is not None else driver
                cards = scope.find_elements(By.CSS_SELECTOR, "div[role='article']")
                if not cards:
                    # fallback: tenta links diretamente
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
                    # tenta achar o link principal dentro do card
                    anchor = None
                    try:
                        anchor = card.find_element(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
                    except Exception:
                        # pega qualquer <a> e filtra
                        for a in card.find_elements(By.TAG_NAME, "a"):
                            h = a.get_attribute("href") or ""
                            if "/maps/place/" in h:
                                anchor = a
                                break
                    if anchor:
                        href = anchor.get_attribute("href") or ""

                    if not label:
                        # pega o título visível do card
                        try:
                            t = card.find_element(By.CSS_SELECTOR, "[role='heading'], .fontHeadlineSmall, .qBF1Pd")
                            label = t.text.strip()
                        except Exception:
                            label = ""

                    if href and href not in seen:
                        seen[href] = label

            # 3) Primeira coleta + loop de rolagem (no feed quando existir)
            harvest()
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
                harvest()
                if len(seen) == prev:
                    time.sleep(0.8)
                    harvest()
                attempts += 1

            # 4) Normaliza saída
            businesses = []
            for href, label in list(seen.items())[:limit]:
                name = label or ""
                if not name:
                    try:
                        name = href.split("/maps/place/")[1].split("/")[0].replace("+", " ")
                    except Exception:
                        name = ""
                businesses.append({
                    "place_id": "",
                    "name": name,
                    "rating": 0,
                    "address": "",
                    "types": [],
                    "maps_url": href,
                })
            return businesses
        finally:
            driver.quit()

    
    def _handle_google_consent(self, driver):
        """Resolve a página de consentimento (full page ou iframe)."""
        wait = WebDriverWait(driver, 20)

        # entra no iframe de consent (quando existir)
        try:
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='consent']")
            if iframes:
                driver.switch_to.frame(iframes[0])
        except Exception:
            pass

        def try_click(by, sel):
            try:
                el = wait.until(EC.element_to_be_clickable((by, sel)))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(1.0)
                # volta ao contexto principal, caso tenha entrado em iframe
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
                # tenta confirmar que saiu da página de consent
                try:
                    WebDriverWait(driver, 10).until(lambda d: "consent.google" not in d.current_url.lower())
                except TimeoutException:
                    pass
                return True
            except Exception:
                return False

        # candidatos (XPATH) — inclui <input type="submit"> e <button> em EN/PT
        candidates = [
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Accept') or contains(@aria-label,'Accept'))]"),
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Aceitar') or contains(@aria-label,'Aceitar'))]"),
            (By.XPATH, "//input[contains(@class,'searchButton') and @type='submit']"),
            (By.XPATH, "//button[@id='L2AGLb']"),
            (By.XPATH, "//button[normalize-space()='Accept all' or .//span[normalize-space()='Accept all']]"),
            (By.XPATH, "//button[normalize-space()='Aceitar tudo' or .//span[normalize-space()='Aceitar tudo']]"),
            # teu XPATH absoluto (último recurso)
            (By.XPATH, "/html/body/div/div[2]/div[1]/div[3]/form[2]/input[14]"),
        ]
        for by, sel in candidates:
            if try_click(by, sel):
                return

        # fallback: injeta cookie CONSENT e recarrega
        try:
            if "google.com" not in driver.current_url:
                driver.get("https://www.google.com/?hl=en")
            driver.add_cookie({"name": "CONSENT", "value": "YES+", "domain": ".google.com", "path": "/"})
            driver.refresh()
            time.sleep(0.8)
        except Exception:
            pass

    def _split_query_term_location(self, query: str):
        """Tenta separar o 'termo' da 'localização' a partir do texto (ex.: 'imobiliárias em São Paulo')."""
        q_low = query.lower()
        seps = [" em ", " no ", " na ", " in ", " at ", " de "]
        for sep in seps:
            if sep in q_low:
                i = q_low.rfind(sep)
                term = query[:i].strip()
                loc = query[i + len(sep):].strip()
                return term, loc
        return query.strip(), None

    def _maps_ui_search(self, driver, wait, location: str | None, term: str):
        """Usa a própria UI do Google Maps: abre Maps, vai até a localização e depois busca o termo."""
        # Abre o Maps “limpo”
        driver.get("https://www.google.com/maps?hl=pt-BR&gl=BR")
        # se aparecer consentimento, trata:
        if "consent.google" in driver.current_url.lower():
            self._handle_google_consent(driver)
            if "consent.google" in driver.current_url.lower():
                driver.get("https://www.google.com/maps?hl=pt-BR&gl=BR")
                time.sleep(0.8)

        # Espera a barra de busca
        search_input = wait.until(EC.presence_of_element_located((By.ID, "searchboxinput")))
        search_btn = wait.until(EC.element_to_be_clickable((By.ID, "searchbox-searchbutton")))

        def do_search(text: str):
            search_input.clear()
            search_input.send_keys(text)
            search_btn.click()
            # espera aparecer algo (um card ou o feed)
            try:
                wait.until(
                    lambda d: len(d.find_elements(By.CSS_SELECTOR, "div[role='article']")) >= 1
                    or d.find_elements(By.CSS_SELECTOR, "div[role='feed']")
                )
            except Exception:
                pass
            time.sleep(0.8)

        # 1) Primeiro centraliza na cidade (se existir na query)
        if location:
            do_search(location)

        # 2) Depois busca só o termo (ex.: “imobiliárias”)
        do_search(term)
