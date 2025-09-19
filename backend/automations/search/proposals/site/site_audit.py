# modules/site_audit.py
import os
import re
import json
import unicodedata
from typing import List, Dict, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

def _strip_acc(s: str) -> str:
    try:
        return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    except Exception:
        return s or ""

def _norm(s: str) -> str:
    s = _strip_acc((s or "").strip().lower())
    s = re.sub(r"\s{2,}", " ", s)
    return s

def _domain(url: str) -> str:
    if not url: return ""
    u = urlparse(url if "://" in url else "http://" + url)
    host = (u.netloc or "").lower()
    if host.startswith("www."): host = host[4:]
    return host

def _https_ok(url: str) -> bool:
    try:
        return urlparse(url).scheme == "https"
    except Exception:
        return False

def _count_imgs_alt(soup: BeautifulSoup) -> Tuple[int,int]:
    imgs = soup.find_all("img")
    if not imgs: return 0,0
    ok = sum(1 for i in imgs if (i.has_attr("alt") and i["alt"].strip()))
    return ok, len(imgs)

def _detect_cms(html: str) -> str:
    h = html.lower()
    if "wp-content" in h or "wp-json" in h: return "WordPress"
    if "wix-" in h or "x-wix" in h or "wixstatic.com" in h: return "Wix"
    if "biosites" in h: return "biosites"
    if "squarespace.com" in h: return "Squarespace"
    if "shopify" in h: return "Shopify"
    return ""

def _jquery_version(html: str) -> str:
    m = re.search(r"jquery[-\.](\d+\.\d+(?:\.\d+)?)", html.lower())
    return m.group(1) if m else ""

def _bootstrap_version(html: str) -> str:
    m = re.search(r"bootstrap[-\.](\d+\.\d+(?:\.\d+)?)", html.lower())
    return m.group(1) if m else ""

class SiteAuditor:
    def _analyze_page(self, html: str, page: str, base_url: str) -> Tuple[List[Dict], Dict]:
        issues: List[Dict] = []
        soup = BeautifulSoup(html, "html.parser")

        def add(sev, cat, msg, evidence="", fix=""):
            issues.append({
                "severity": sev, "category": cat, "message": msg,
                "evidence": evidence, "fix": fix, "page": page
            })

        # HEAD checks
        title = (soup.title.string.strip() if soup.title and soup.title.string else "")
        if not title:
            add("Major", "SEO", "Sem <title>", fix="Adicionar um título único (10–60 caracteres).")
        else:
            if not (10 <= len(title) <= 60):
                add("Minor", "SEO", f"<title> fora de faixa ({len(title)} char).",
                    evidence=title, fix="Deixar entre 10 e 60 caracteres.")

        desc = soup.find("meta", attrs={"name": "description"})
        if not desc or not desc.get("content"):
            add("Minor", "SEO", "Sem meta description.",
                fix="Adicionar descrição de 50–160 caracteres com benefício e CTA.")

        canon = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
        if not canon or not canon.get("href"):
            add("Minor", "SEO", "Sem rel=canonical.")
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            add("Major", "UX", "Sem meta viewport (provável não responsivo).",
                fix="Adicionar <meta name='viewport' content='width=device-width, initial-scale=1'>.")

        # headings
        h1s = soup.find_all("h1")
        if len(h1s) == 0:
            add("Minor", "SEO", "Sem H1.")
        elif len(h1s) > 1:
            add("Minor", "SEO", f"Múltiplos H1 ({len(h1s)}).", fix="Usar apenas um H1 por página.")

        # accessibility
        ok_alt, total_img = _count_imgs_alt(soup)
        if total_img >= 5 and ok_alt/total_img < 0.6:
            add("Minor", "A11y", f"Baixa cobertura de alt em imagens ({ok_alt}/{total_img}).",
                fix="Adicionar atributo alt descritivo nas imagens.")

        # perf (sinais estáticos)
        scripts = soup.find_all("script")
        links_css = soup.find_all("link", rel=lambda v: v and "stylesheet" in v.lower())
        if len(scripts) > 30:
            add("Minor", "Perf", f"Muitos scripts ({len(scripts)}).")
        if len(links_css) > 10:
            add("Minor", "Perf", f"Muitas folhas de estilo ({len(links_css)}).")

        jver = _jquery_version(html)
        if jver:
            try:
                major = int(jver.split(".")[0])
                if major < 3:
                    add("Major", "Tech", f"jQuery antigo ({jver}).",
                        fix="Atualizar jQuery >= 3.5 ou remover dependência.")
            except Exception:
                pass

        bver = _bootstrap_version(html)
        if bver:
            try:
                major = int(bver.split(".")[0])
                if major <= 3:
                    add("Major", "Tech", f"Bootstrap antigo ({bver}).",
                        fix="Migrar para Bootstrap 5 ou layout moderno.")
            except Exception:
                pass

        # conteúdo/CTA
        txt = soup.get_text(" ", strip=True)
        if "fale conosco" not in _norm(txt) and "contato" not in _norm(txt) and "whatsapp" not in _norm(txt):
            add("Minor", "Content", "Falta CTA claro (contato/WhatsApp).")

        # dados estruturados
        if not soup.find("script", type="application/ld+json"):
            add("Minor", "SEO", "Sem JSON-LD (LocalBusiness/PostalAddress).")

        # sinais agregados rápidos
        cms = _detect_cms(html)
        flags = {
            "has_viewport": bool(viewport),
            "cms_guess": cms,
        }
        return issues, flags

    def audit(self, items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Retorna:
        - items_enriched: adiciona campos agregados do site (ssl_ok, mobile_ready, cms_guess, issues_count)
        - issues_rows: lista de dicts por página (lead_name, page, severity, category, message, evidence, fix)
        """
        out_items = []
        issues_rows: List[Dict] = []

        for it in items:
            snap_dir = it.get("snapshot_dir")
            website = it.get("website") or it.get("website_canonical") or ""

            # ⛔ Sem domínio próprio: pula auditoria e cria 1 issue sintética
            if it.get("no_own_site") is True:
                out_items.append({
                    **it,
                    "ssl_ok": False,
                    "mobile_ready": False,
                    "cms_guess": "",
                    "issues_count": 1,  # conta a issue sintética
                })
                issues_rows.append({
                    "lead_name": it.get("name",""),
                    "website": website,
                    "page": "n/a",
                    "severity": "Critical",
                    "category": "Site",
                    "message": "Sem site próprio",
                    "evidence": it.get("skip_reason",""),  # ex: social_link, whatsapp, builder_subdomain
                    "fix": "Propor criação de site com domínio próprio (ex.: .com.br) e páginas básicas (Home, Sobre, Serviços, Contato).",
                })
                continue

            if not snap_dir or not os.path.isdir(snap_dir):
                out_items.append({
                    **it,
                    "ssl_ok": _https_ok(website),
                    "mobile_ready": False,
                    "cms_guess": "",
                    "issues_count": 0
                })
                continue

            has_viewport_any = False
            cms_guess = ""
            total_issues = 0

            for f in os.listdir(snap_dir):
                if not f.endswith(".html"): 
                    continue
                page = f.replace(".html", "")
                path = os.path.join(snap_dir, f)
                try:
                    html = open(path, "r", encoding="utf-8").read()
                except Exception:
                    continue

                issues, flags = self._analyze_page(html, page, website)
                total_issues += len(issues)
                has_viewport_any = has_viewport_any or bool(flags.get("has_viewport"))
                if not cms_guess and flags.get("cms_guess"):
                    cms_guess = flags["cms_guess"]

                for iss in issues:
                    issues_rows.append({
                        "lead_name": it.get("name",""),
                        "website": website,
                        "page": iss["page"],
                        "severity": iss["severity"],
                        "category": iss["category"],
                        "message": iss["message"],
                        "evidence": iss.get("evidence",""),
                        "fix": iss.get("fix",""),
                    })

            enriched = {
                **it,
                "ssl_ok": _https_ok(website),
                "mobile_ready": has_viewport_any,
                "cms_guess": cms_guess,
                "issues_count": total_issues,
            }

            # salva issues.json no diretório do snapshot (útil para CRM)
            try:
                by_this = [r for r in issues_rows if r["website"] == website]
                if by_this:
                    with open(os.path.join(snap_dir, "issues.json"), "w", encoding="utf-8") as f:
                        json.dump(by_this, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

            out_items.append(enriched)

        return out_items, issues_rows
