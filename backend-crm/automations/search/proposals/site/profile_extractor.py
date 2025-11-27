# modules/profile_extractor.py
import time
from typing import List, Dict

import googlemaps
from . import config

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

from urllib.parse import urlparse, parse_qs
import re


class ProfileExtractor:
    def __init__(self):
        self.gmaps_client = None
        api_key = getattr(config, "GOOGLE_MAPS_API_KEY", "")
        if api_key:
            self.gmaps_client = googlemaps.Client(key=api_key)

    # ---------- API (Places Details) ----------

    def _enrich_via_api(self, place_id: str) -> Dict:
        """Busca detalhes do lugar pela Places Details (legacy)."""
        if not self.gmaps_client or not place_id:
            return {}
        fields = [
            "name",
            "formatted_address",
            "formatted_phone_number",
            "international_phone_number",
            "website",
            "rating",
            "user_ratings_total",
            "url",
            #"type" opcional ; geralmente não precisa
        ]
        resp = self.gmaps_client.place(place_id=place_id, fields=fields)
        result = resp.get("result", {}) if resp else {}
        phone = (
            result.get("formatted_phone_number")
            or result.get("international_phone_number")
            or ""
        )

        website = self._clean_google_redirect(result.get("website", ""))
        rating = self._norm_rating(str(result.get("rating", "")))
        reviews = self._norm_reviews(str(result.get("user_ratings_total", "")))

        return {
            "name": result.get("name", ""),
            "address": result.get("formatted_address", ""),
            "phone": phone,
            "website": result.get("website", ""),
            "rating": result.get("rating", 0),
            "reviews_count": result.get("user_ratings_total", 0),
            "types": result.get("types", []),  # se vier, ótimo
            "maps_url": result.get("url", ""),
        }

    # ---------- Selenium (página do lugar) ----------

    def _build_driver(self):
        opts = Options()
        # descomente para rodar sem abrir janela:
        # opts.add_argument("--headless=new")

        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--window-size=1280,1800")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--lang=pt-BR")
        ua_list = getattr(config, "USER_AGENTS", [])
        ua = ua_list[0] if ua_list else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        opts.add_argument(f"--user-agent={ua}")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=opts)

    def _handle_google_consent(self, driver):
        """Resolve página de consentimento (full page/iframe)."""
        wait = WebDriverWait(driver, 20)
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
                try: driver.switch_to.default_content()
                except Exception: pass
                try: WebDriverWait(driver, 8).until(lambda d: "consent.google" not in d.current_url.lower())
                except TimeoutException: pass
                return True
            except Exception:
                return False

        candidates = [
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Accept') or contains(@aria-label,'Accept'))]"),
            (By.XPATH, "//input[@type='submit' and (contains(@value,'Aceitar') or contains(@aria-label,'Aceitar'))]"),
            (By.XPATH, "//button[@id='L2AGLb']"),
            (By.XPATH, "//button[normalize-space()='Accept all' or .//span[normalize-space()='Accept all']]"),
            (By.XPATH, "//button[normalize-space()='Aceitar tudo' or .//span[normalize-space()='Aceitar tudo']]"),
        ]
        for by, sel in candidates:
            if try_click(by, sel):
                return

        # fallback: CONSENT cookie
        try:
            if "google.com" not in driver.current_url:
                driver.get("https://www.google.com/?hl=en")
            driver.add_cookie({"name": "CONSENT", "value": "YES+", "domain": ".google.com", "path": "/"})
            driver.refresh(); time.sleep(0.8)
        except Exception:
            pass

    def _get_text(self, driver, wait, selectors) -> str:
        for css in selectors:
            try:
                el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
                txt = el.text.strip()
                if txt:
                    return txt
            except Exception:
                continue
        return ""

    def _get_href(self, driver, wait, selectors) -> str:
        for css in selectors:
            try:
                el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
                href = el.get_attribute("href") or ""
                if href:
                    return href
            except Exception:
                continue
        return ""

    def _enrich_via_selenium(self, maps_url: str) -> Dict:
        """Abre a página do lugar e extrai campos principais com waits robustos."""
        if not maps_url:
            return {}
        driver = self._build_driver()
        try:
            driver.get(maps_url)
            if "consent.google" in driver.current_url.lower():
                self._handle_google_consent(driver)
                if "consent.google" in driver.current_url.lower():
                    driver.get(maps_url); time.sleep(0.8)

            wait = WebDriverWait(driver, 25)

            name = self._get_text(driver, wait, [
                "h1.DUwDvf",                   # título padrão
                "[role='heading'].DUwDvf",     # variação
            ])
            address = self._get_text(driver, wait, [
                "button[data-item-id='address']",                 # botão de endereço
                "button[aria-label^='Endereço:']",
                "button[aria-label^='Address:']",
            ])
            phone = self._get_text(driver, wait, [
                "button[data-item-id^='phone']",                 # phone:* varia
                "button[aria-label^='Telefone:']",
                "button[aria-label^='Phone:']",
                "a[href^='tel:']",
            ])
            website = self._get_href(driver, wait, [
                "a[data-item-id='authority']",                   # website
                "a[aria-label^='Website']",
                "a[aria-label^='Site']",
            ])
            rating = self._get_text(driver, wait, [
                "div.F7nice",                                    # nota visível
                "span[aria-label*='stars']",                     # aria fallback
            ])
            reviews_count = self._get_text(driver, wait, [
                "button[jsaction*='moreReviews']",               # botão que abre reviews
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

        finally:
            driver.quit()

    # ---------- Orquestração ----------

    def enrich(self, items: List[Dict]) -> List[Dict]:
        """Enriquece cada item, preferindo API quando houver place_id; caso contrário, Selenium."""
        enriched = []
        for it in items:
            details = {}
            pid = it.get("place_id") or ""
            if pid and self.gmaps_client:
                try:
                    details = self._enrich_via_api(pid)
                except Exception as e:
                    print(f"[ProfileExtractor] API details falhou ({pid}): {e}")
            if not details:
                try:
                    details = self._enrich_via_selenium(it.get("maps_url", ""))
                except Exception as e:
                    print(f"[ProfileExtractor] Selenium details falhou: {e}")
            # merge: detalhes sobrescrevem campos vazios do item
            merged = {**it, **{k: v for k, v in details.items() if v}}
            enriched.append(merged)
        return enriched

    #Limpeza dos dados vindos do Selenium (site/rating/reviews/telefone)
    def _clean_google_redirect(self, url: str) -> str:
        """Tira o wrapper do Google (https://www.google.com/url?q=...) e devolve o destino real."""
        if not url:
            return ""
        try:
            u = urlparse(url)
            if u.netloc.endswith("google.com") and u.path.startswith("/url"):
                q = parse_qs(u.query)
                real = q.get("q", [""])[0]
                return real or url
        except Exception:
            pass
        return url

    def _norm_rating(self, txt: str) -> float | str:
        """Converte '4,7' -> 4.7 ; mantém vazio se não deu."""
        if not txt:
            return ""
        try:
            txt2 = txt.strip().replace(",", ".")
            # pega primeiro número com ponto opcional
            m = re.search(r"\d+(?:[.,]\d+)?", txt2)
            return float(m.group(0).replace(",", ".")) if m else ""
        except Exception:
            return ""

    def _norm_reviews(self, txt: str) -> int | str:
        """Extrai número de reviews de coisas como '(239)', '239 avaliações', '1.323' etc."""
        if not txt:
            return ""
        try:
            # pega o maior bloco de dígitos (com . como separador de milhar)
            m = re.search(r"(\d[\d\.]*)", txt.replace(",", "."))
            if not m:
                return ""
            val = m.group(1).replace(".", "")
            return int(val)
        except Exception:
            return ""

    def _norm_phone(self, txt: str) -> str:
        """Limpa artefatos e quebra de linha; mantém formatação simples do telefone."""
        if not txt:
            return ""
        t = txt.replace("\n", " ").strip()
        # remove símbolos não ASCII comuns dos ícones
        t = re.sub(r"[^\+\d\-\(\)\s\.]", "", t)
        # compacta espaços
        t = re.sub(r"\s{2,}", " ", t)
        return t.strip()