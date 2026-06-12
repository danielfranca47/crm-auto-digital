import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from services import analyzer, cache, history           # noqa: E402
from services import metrics as metrics_svc             # noqa: E402
from services import pattern_detector                   # noqa: E402
from services import quota                              # noqa: E402
from readers.transcript_reader import get_recent_sessions  # noqa: E402
from readers.session_parser import summarize_session       # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("advisor")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_scheduler    = BackgroundScheduler()
_is_running   = False
_briefing_running = False


def _run_analysis(force: bool = False):
    global _is_running
    if _is_running:
        log.info("Analysis already running, skipping.")
        return

    allowed, reason = quota.can_run()
    if not allowed and not force:
        log.warning(f"Quota reached — skipping analysis. {reason}")
        return

    _is_running = True
    try:
        log.info("Starting analysis...")
        report = analyzer.run_analysis()
        cache.save(report)
        history.save(report)
        quota.record_call("analysis")
        log.info("Analysis complete.")
    except Exception as e:
        log.error(f"Analysis failed: {e}")
    finally:
        _is_running = False


def _maybe_run_on_startup():
    if cache.is_stale():
        log.info("Cache stale — running analysis on startup.")
        _run_analysis()
    else:
        log.info("Cache fresh, skipping startup analysis.")


def _compute_dashboard_extras():
    sessions_raw = get_recent_sessions(days=7)
    met    = metrics_svc.compute(sessions_raw)
    past   = history.load_recent(n=4)
    alerts = pattern_detector.detect(sessions_raw, met, past)
    return met, alerts


@asynccontextmanager
async def lifespan(app: FastAPI):
    daily_time = os.getenv("DAILY_ANALYSIS_TIME", "08:00")
    hour, minute = map(int, daily_time.split(":"))
    _scheduler.add_job(_run_analysis, "cron", hour=hour, minute=minute, id="daily")
    _scheduler.start()

    threading.Thread(target=_maybe_run_on_startup, daemon=True).start()
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(title="CRM Advisor", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    report        = cache.load()
    met, alerts   = _compute_dashboard_extras()
    quota_info    = quota.get_quota_info()
    allowed, _    = quota.can_run()
    status        = "loading" if _is_running else ("ready" if report else "empty")
    return templates.TemplateResponse("index.html", {
        "request":    request,
        "report":     report,
        "status":     status,
        "is_running": _is_running,
        "metrics":    met,
        "alerts":     alerts,
        "quota":      quota_info,
        "can_run":    allowed,
    })


@app.post("/refresh")
async def refresh():
    if _is_running:
        return JSONResponse({"ok": False, "message": "Análise já em curso, aguarda."})

    allowed, reason = quota.can_run()
    if not allowed:
        # Redireciona de volta com aviso via query param
        return RedirectResponse(f"/?quota_blocked=1", status_code=303)

    threading.Thread(target=_run_analysis, daemon=True).start()
    return RedirectResponse("/", status_code=303)


@app.get("/briefing", response_class=HTMLResponse)
async def briefing_page(request: Request):
    global _briefing_running
    briefing_data = None
    error         = None

    allowed, reason = quota.can_run()
    if not allowed:
        error = reason
    elif not _briefing_running:
        _briefing_running = True
        try:
            briefing_data = analyzer.run_briefing()
            quota.record_call("briefing")
        except Exception as e:
            error = str(e)
            log.error(f"Briefing failed: {e}")
        finally:
            _briefing_running = False

    quota_info = quota.get_quota_info()
    return templates.TemplateResponse("briefing.html", {
        "request":    request,
        "briefing":   briefing_data,
        "error":      error,
        "now":        datetime.now().strftime("%A, %d de %B de %Y"),
        "quota":      quota_info,
    })


@app.post("/settings")
async def save_settings(max_calls_per_week: int = Form(...)):
    quota.save_settings(max_calls_per_week)
    return RedirectResponse("/", status_code=303)


@app.get("/api/quota")
async def api_quota():
    return JSONResponse({"ok": True, "quota": quota.get_quota_info()})


@app.get("/api/report")
async def api_report():
    report = cache.load()
    if not report:
        return JSONResponse({"ok": False, "message": "Sem análise disponível."}, status_code=404)
    return JSONResponse({"ok": True, "report": report})


@app.get("/api/metrics")
async def api_metrics():
    met, alerts = _compute_dashboard_extras()
    return JSONResponse({"ok": True, "metrics": met, "alerts": alerts})


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
