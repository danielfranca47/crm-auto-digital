# automations/search/proposals/site/config.py
import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path


# Isto acha o .env mais próximo subindo a árvore de pastas (raiz do backend)
load_dotenv(find_dotenv())

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

#Tuning
REQUEST_TIMEOUT     = int(os.getenv("REQUEST_TIMEOUT", 12))
REQUEST_DELAY       = float(os.getenv("REQUEST_DELAY", 1.0))
MAX_PAGES_PER_SITE  = int(os.getenv("MAX_PAGES_PER_SITE", 6))
MAX_SCROLL_ATTEMPTS = int(os.getenv("MAX_SCROLL_ATTEMPTS", 8))

# User-Agent
UA = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
USER_AGENTS = [UA]

# Raiz do módulo "search" (site -> proposals -> search)
SEARCH_ROOT = Path(__file__).resolve().parents[2]

# Endereços "fixos" para saídas
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data/output")).resolve()
SNAPSHOTS_DIR = Path(os.getenv("SNAPSHOTS_DIR", "data/snapshots")).resolve()
OUTPUT_DIR = Path("data/output")