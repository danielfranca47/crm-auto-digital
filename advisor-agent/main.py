import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

load_dotenv(Path(__file__).parent / ".env")

# Readers/services are in subdirectories — add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from services import analyzer, cache  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("advisor")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_scheduler = BackgroundScheduler()

_is_running = False


def _run_analysis():
    global _is_running
    if _is_running:
        log.info("Analysis already running, skipping.")
        return
    _is_running = True
    try:
        log.info("Starting daily analysis...")
        report = analyzer.run_analysis()
        cache.save(report)
        log.info("Analysis complete and cached.")
    except Exception as e:
        log.error(f"Analysis failed: {e}")
    finally:
        _is_running = False


def _maybe_run_on_startup():
    if cache.is_stale():
        log.info("Cache is stale or missing — running analysis on startup.")
        _run_analysis()
    else:
        log.info("Cache is fresh, skipping startup analysis.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule daily analysis
    daily_time = os.getenv("DAILY_ANALYSIS_TIME", "08:00")
    hour, minute = map(int, daily_time.split(":"))
    _scheduler.add_job(_run_analysis, "cron", hour=hour, minute=minute, id="daily")
    _scheduler.start()

    import threading
    t = threading.Thread(target=_maybe_run_on_startup, daemon=True)
    t.start()

    yield

    _scheduler.shutdown(wait=False)


app = FastAPI(title="CRM Advisor", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    report = cache.load()
    status = "loading" if _is_running else ("ready" if report else "empty")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "report": report, "status": status, "is_running": _is_running},
    )


@app.post("/refresh")
async def refresh():
    if _is_running:
        return JSONResponse({"ok": False, "message": "Análise já em curso, aguarda."})

    import threading
    t = threading.Thread(target=_run_analysis, daemon=True)
    t.start()

    return RedirectResponse("/", status_code=303)


@app.get("/api/report")
async def api_report():
    report = cache.load()
    if not report:
        return JSONResponse({"ok": False, "message": "Sem análise disponível."}, status_code=404)
    return JSONResponse({"ok": True, "report": report})


@app.get("/api/status")
async def api_status():
    return {
        "is_running": _is_running,
        "cache_stale": cache.is_stale(),
        "cached_at": (cache.load() or {}).get("cached_at"),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8005"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
