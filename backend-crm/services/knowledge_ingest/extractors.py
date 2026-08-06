"""
extractors.py — Extração de texto das fontes de ingestão da base de conhecimento.

Cada fonte (arquivo ou URL) vira texto puro para o classificador LLM:
- .pdf              → pypdf (camada de texto; PDF escaneado retorna vazio)
- .txt/.csv/.xlsx   → leitura direta / pandas (compartilhado com routes/knowledge.py)
- imagem            → gpt-4o-mini vision com data URI base64 (OCR + descrição)
- URL               → scraper slim requests+BeautifulSoup (home + páginas internas relevantes)
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

MAX_CHARS_PER_SOURCE = 15_000

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
TABLE_EXTENSIONS = {".txt", ".csv", ".xlsx"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_FILE_EXTENSIONS = IMAGE_EXTENSIONS | TABLE_EXTENSIONS | PDF_EXTENSIONS

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_VISION_MODEL = "gpt-4o-mini"

_SCRAPE_MAX_PAGES = 5
_SCRAPE_TIMEOUT = 15
_SCRAPE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CRMAutoDigital/1.0)"}

# Palavras que indicam páginas internas com conteúdo útil para a base de conhecimento
_RELEVANT_LINK_HINTS = (
    "sobre", "about", "quem-somos", "servico", "servic", "service",
    "preco", "preço", "precos", "pricing", "plano", "pacote",
    "contato", "contact", "faq", "duvida", "horario", "agenda",
)


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) > MAX_CHARS_PER_SOURCE:
        return text[:MAX_CHARS_PER_SOURCE]
    return text


def _ok(text: str) -> Dict[str, Any]:
    text = _truncate(text)
    return {"status": "extracted", "text": text, "chars": len(text), "reason": None}


def _fail(reason: str) -> Dict[str, Any]:
    return {"status": "failed", "text": "", "chars": 0, "reason": reason}


# ─── Tabelas / texto simples (compartilhado com routes/knowledge.py) ──────────

def extract_text_from_table_file(fp: Path) -> str:
    """Extrai texto de .txt/.csv/.xlsx. Levanta ValueError para extensão não suportada."""
    suffix = fp.suffix.lower()

    if suffix == ".txt":
        try:
            return fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return fp.read_text(encoding="latin-1")

    if suffix == ".csv":
        df = pd.read_csv(fp)
        return df.head(200).to_csv(index=False)

    if suffix == ".xlsx":
        xls = pd.ExcelFile(fp)
        sheet = "Leads" if "Leads" in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet)
        return df.head(200).to_csv(index=False)

    raise ValueError("Extensão de arquivo não suportada")


# ─── PDF ──────────────────────────────────────────────────────────────────────

def _extract_pdf(fp: Path) -> Dict[str, Any]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(fp))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
    except Exception as exc:
        logger.warning("[knowledge_ingest] falha ao ler PDF %s: %s", fp.name, exc)
        return _fail(f"falha_leitura_pdf: {exc}")

    if not text:
        # PDF escaneado sem camada de texto — orientar envio como imagem (vision faz OCR)
        return _fail("sem_texto_extraivel")
    return _ok(text)


# ─── Imagem (vision) ──────────────────────────────────────────────────────────

_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _extract_image(fp: Path) -> Dict[str, Any]:
    if not _OPENAI_API_KEY:
        return _fail("openai_api_key_ausente")

    mime = _IMAGE_MIME.get(fp.suffix.lower(), "image/jpeg")
    try:
        b64 = base64.b64encode(fp.read_bytes()).decode("ascii")
    except Exception as exc:
        return _fail(f"falha_leitura_imagem: {exc}")

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {_OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _VISION_MODEL,
                    "max_tokens": 1500,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Extraia TODO o texto e informação desta imagem, que faz parte "
                                        "do material de um negócio (tabela de preços, cartaz, catálogo, "
                                        "print de conversa, etc.). Transcreva o texto integralmente, "
                                        "preservando valores, horários e nomes de serviços. Se houver "
                                        "elementos visuais relevantes sem texto, descreva-os brevemente."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                                },
                            ],
                        }
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as exc:
        logger.warning("[knowledge_ingest] falha vision imagem %s: %s", fp.name, exc)
        return _fail(f"falha_vision: {exc}")

    if not text:
        return _fail("sem_texto_extraivel")
    return _ok(text)


# ─── URL (scraper slim) ───────────────────────────────────────────────────────

def _page_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _find_candidate_links(html: str, base_url: str) -> list[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_netloc = urlparse(base_url).netloc
    seen: set[str] = set()
    candidates: list[str] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].split("#")[0])
        parsed = urlparse(href)
        if parsed.netloc != base_netloc or href in seen:
            continue
        seen.add(href)
        path = parsed.path.lower()
        if any(hint in path for hint in _RELEVANT_LINK_HINTS):
            candidates.append(href)
    return candidates


def _extract_url(url: str) -> Dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        with httpx.Client(
            timeout=_SCRAPE_TIMEOUT, headers=_SCRAPE_HEADERS, follow_redirects=True
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            home_html = resp.text
            parts = [f"[Página: {url}]\n{_page_text(home_html)}"]

            for link in _find_candidate_links(home_html, str(resp.url))[: _SCRAPE_MAX_PAGES - 1]:
                try:
                    sub = client.get(link)
                    sub.raise_for_status()
                    parts.append(f"[Página: {link}]\n{_page_text(sub.text)}")
                except Exception:
                    continue
                if sum(len(p) for p in parts) >= MAX_CHARS_PER_SOURCE:
                    break
    except Exception as exc:
        logger.warning("[knowledge_ingest] falha scraping url=%s: %s", url, exc)
        return _fail(f"falha_scraping: {exc}")

    text = "\n\n".join(parts).strip()
    if not text:
        return _fail("sem_texto_extraivel")
    return _ok(text)


# ─── Dispatcher ───────────────────────────────────────────────────────────────

def extract_source(source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai texto de uma fonte do payload do job knowledge.ingest.internal.

    source: {"kind": "file"|"url", "path"?: str, "url"?: str, "ext"?: str, ...}
    Retorna {"status": "extracted"|"failed", "text": str, "chars": int, "reason": str|None}
    """
    kind = source.get("kind")

    if kind == "url":
        url = (source.get("url") or "").strip()
        if not url:
            return _fail("url_vazia")
        return _extract_url(url)

    if kind == "file":
        path = source.get("path") or ""
        fp = Path(path)
        if not fp.is_file():
            return _fail("arquivo_nao_encontrado")
        ext = (source.get("ext") or fp.suffix).lower()
        if ext in PDF_EXTENSIONS:
            return _extract_pdf(fp)
        if ext in IMAGE_EXTENSIONS:
            return _extract_image(fp)
        if ext in TABLE_EXTENSIONS:
            try:
                return _ok(extract_text_from_table_file(fp))
            except Exception as exc:
                return _fail(f"falha_leitura_arquivo: {exc}")
        return _fail("extensao_nao_suportada")

    return _fail("kind_invalido")
