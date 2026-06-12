# modules/website_scraper.py
import re
import os
import time
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from . import config


class WebsiteScraper:
    def __init__(self):
        # parâmetros com defaults caso não existam no config.py
        self.timeout = getattr(config, "REQUEST_TIMEOUT", 12)
        self.delay = getattr(config, "REQUEST_DELAY", 1.0)
        self.max_pages = getattr(config, "MAX_PAGES_PER_SITE", 6)
        self.ua_list = getattr(config, "USER_AGENTS", []) or [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ]

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.ua_list[0]})

        # palavras para identificar páginas úteis
        self.contact_words = ["contato", "contact", "fale-conosco", "faleconosco", "contate", "contacter"]
        self.about_words = ["sobre", "quem-somos", "quemsomos", "about", "empresa"]
        self.services_words = ["servicos", "serviços", "services", "imoveis", "imóveis"]

    # ---------- utilidades ----------

    def _sleep(self):
        if self.delay and self.delay > 0:
            time.sleep(self.delay)

    def _abs(self, base: str, href: str) -> str:
        try:
            return urljoin(base, href)
        except Exception:
            return href

    def _is_same_host(self, base: str, url: str) -> bool:
        try:
            b = urlparse(base).netloc.lower()
            u = urlparse(url).netloc.lower()
            if b.startswith("www."):
                b = b[4:]
            if u.startswith("www."):
                u = u[4:]
            return b == u or (u.endswith("." + b) or b.endswith("." + u))
        except Exception:
            return False

    def _clean_google_redirect(self, url: str) -> str:
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

    # ---------- requisição ----------

    def _get(self, url: str) -> str:
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            if 200 <= resp.status_code < 300 and "text/html" in (resp.headers.get("Content-Type", "")):
                return resp.text
        except Exception:
            return ""
        return ""

    # ---------- extração ----------

    def _extract_emails(self, text: str) -> List[str]:
        if not text:
            return []
        cand = set(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text))
        return sorted(cand)

    def _extract_phones(self, text: str) -> tuple[list[str], str]:
        if not text:
            return [], ""
        phones = set(re.findall(r"(?:\+\d{1,3}\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[\s\-.]?\d{4}", text))
        phones = {p.strip() for p in phones}
        def only_digits(s): return re.sub(r"\D+", "", s)
        main_norm = only_digits(next(iter(phones))) if phones else ""
        return sorted(phones), main_norm

    def _extract_socials(self, soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
        out = {}
        for a in soup.find_all("a", href=True):
            href = self._abs(base_url, a["href"]).lower()
            if "facebook.com" in href and "facebook" not in out:
                out["facebook"] = href
            elif "instagram.com" in href and "instagram" not in out:
                out["instagram"] = href
            elif "linkedin.com" in href and "linkedin" not in out:
                out["linkedin"] = href
            elif "youtube.com" in href and "youtube" not in out:
                out["youtube"] = href
            elif "tiktok.com" in href and "tiktok" not in out:
                out["tiktok"] = href
            elif "wa.me/" in href or "api.whatsapp.com" in href:
                if "whatsapp" not in out and "whatsapp_link" not in out:
                    out["whatsapp"] = href          # compatibilidade com colunas antigas
                    out["whatsapp_link"] = href     # coluna nova mais semântica
        return out

    def _extract_jsonld_address_phone(self, soup: BeautifulSoup) -> Dict[str, str]:
        out = {}
        try:
            for s in soup.find_all("script", type="application/ld+json"):
                txt = (s.string or s.text or "").strip()
                if not txt:
                    continue
                import json
                data = json.loads(txt)
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    tel = it.get("telephone") or it.get("tel") or ""
                    if tel and not out.get("phone"):
                        out["phone"] = tel
                    addr = it.get("address") or {}
                    if isinstance(addr, dict):
                        parts = [
                            addr.get("streetAddress", ""),
                            addr.get("addressLocality", ""),
                            addr.get("addressRegion", ""),
                            addr.get("postalCode", ""),
                            addr.get("addressCountry", ""),
                        ]
                        cand = ", ".join([p for p in parts if p])
                        if cand and not out.get("address"):
                            out["address"] = cand
        except Exception:
            pass
        return out

    def _guess_services(self, text: str) -> List[str]:
        if not text:
            return []
        kws = [
            "aluguel", "locação", "compra", "venda", "avaliação", "financiamento",
            "imóveis", "apartamentos", "casas", "condomínios", "corretor", "administração"
        ]
        counts = {}
        low = text.lower()
        for w in kws:
            c = low.count(w)
            if c > 0:
                counts[w] = c
        return [k for k, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]]

    def _find_candidate_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        cand = []
        for a in soup.find_all("a", href=True):
            label = (a.get_text(" ") or "").strip().lower()
            href = a["href"].strip()
            absu = self._abs(base_url, href)
            score = 0
            if any(w in label for w in self.contact_words): score += 5
            if any(w in label for w in self.about_words): score += 3
            if any(w in label for w in self.services_words): score += 2
            if self._is_same_host(base_url, absu): score += 1
            if score > 0 and absu not in cand:
                cand.append(absu)
        seen = set()
        out = []
        for u in cand:
            if u not in seen:
                out.append(u); seen.add(u)
        return out

    # ---------- fluxo por site ----------

    def _scrape_one_site(self, url: str) -> Dict:
        if not url:
            return {}
        url = self._clean_google_redirect(url)
        if not urlparse(url).scheme:
            url = "http://" + url

        # onde salvar snapshots
        root = getattr(config, "SNAPSHOTS_DIR", "data/snapshots")
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        snapshot_dir = os.path.join(root, host)
        os.makedirs(snapshot_dir, exist_ok=True)

        visited: Set[str] = set()
        queue: List[str] = [url]

        emails_all: Set[str] = set()
        phones_all: Set[str] = set()
        phone_norm_main = ""
        address_best = ""
        socials = {}
        services = []
        pages = 0
        canonical = ""
        saved_files = []  # [{page, url, path}]

        def guess_page_label(cur: str, is_first: bool) -> str:
            curl = cur.lower()
            if is_first:
                return "home"
            for w in self.contact_words:
                if f"/{w}" in curl:
                    return "contato"
            for w in self.about_words:
                if f"/{w}" in curl:
                    return "sobre"
            for w in self.services_words:
                if f"/{w}" in curl:
                    return "servicos"
            return f"page{pages+1}"

        while queue and pages < self.max_pages:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            self._sleep()

            html = self._get(cur)
            if not html:
                continue
            pages += 1

            soup = BeautifulSoup(html, "html.parser")

            # salva snapshot HTML (e texto da home)
            label = guess_page_label(cur, is_first=(pages == 1))
            fname_html = os.path.join(snapshot_dir, f"{label}.html")
            with open(fname_html, "w", encoding="utf-8") as f:
                f.write(html)
            if pages == 1:
                fname_txt = os.path.join(snapshot_dir, "home.txt")
                with open(fname_txt, "w", encoding="utf-8") as f:
                    f.write(soup.get_text(" ", strip=True))
            saved_files.append({"page": label, "url": cur, "path": fname_html})

            # canonical
            if not canonical:
                link = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
                if link and link.get("href"):
                    canonical = self._abs(cur, link["href"]).strip()

            # JSON-LD address/phone
            j = self._extract_jsonld_address_phone(soup)
            if j.get("address") and len(j["address"]) > len(address_best):
                address_best = j["address"]
            if j.get("phone") and not phone_norm_main:
                phones_all.add(j["phone"])

            # emails / phones
            text = soup.get_text(" ", strip=True)
            emails = self._extract_emails(text)
            for e in emails: emails_all.add(e)
            phones, norm = self._extract_phones(text)
            for p in phones: phones_all.add(p)
            if norm and not phone_norm_main:
                phone_norm_main = norm

            # socials (primeiras ocorrências)
            s = self._extract_socials(soup, cur)
            socials = {**s, **socials} if socials else s

            # services (heurística simples)
            if not services:
                services = self._guess_services(text)

            # fila de páginas internas relevantes (só a partir da home)
            if pages == 1:
                queue.extend(self._find_candidate_links(soup, cur))

        return {
            "website_canonical": canonical or url,
            "emails": sorted(emails_all),
            "phones_site": sorted(phones_all),
            "phone_site_norm": phone_norm_main,
            "address_site": address_best,
            "services_keywords": services,
            "pages_crawled": pages,
            "snapshot_dir": snapshot_dir,
            "pages_saved": saved_files,  # [{page,url,path}]
            **socials,
        }

    # ---------- público ----------

    def enrich(self, items: List[Dict]) -> List[Dict]:
        """Para cada item com website, varre algumas páginas e anexa dados do site."""
        out = []
        for it in items:
            website = (it.get("website") or "").strip()

            # ⛔️ Pula scraping se NÃO for domínio próprio
            if it.get("no_own_site") is True:
                out.append({
                    **it,
                    "website_canonical": it.get("website") or it.get("website_canonical") or "",
                    "emails": [],
                    "phones_site": [],
                    "phone_site_norm": "",
                    "address_site": "",
                    "services_keywords": [],
                    "pages_crawled": 0,
                    "pages_saved": [],
                    # NÃO cria snapshot_dir; auditoria irá pular pelo flag no_own_site
                    "skip_reason": it.get("skip_reason", "") or it.get("website_kind", ""),
                })
                continue

            extra = {}
            if website:
                try:
                    extra = self._scrape_one_site(website)
                except Exception as e:
                    print(f"[WebsiteScraper] erro em {website}: {e}")
            merged = {**it, **extra}
            out.append(merged)
        return out
