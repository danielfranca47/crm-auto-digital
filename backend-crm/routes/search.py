# routes/search.py
from pathlib import Path
from typing import Optional, Literal, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
import json

from automations.search.proposals.site.runner import run_site_search
from automations.search.proposals.site import config  # OUTPUT_DIR
from security_core import CurrentUser, get_current_user

router = APIRouter()

class SearchRequest(BaseModel):
    proposal: Literal["site"] = Field(default="site")
    country: str
    state: str
    city: str
    neighborhood: Optional[str] = ""
    sector: str
    quantity: int = Field(default=20, ge=5, le=50)

# ---------- helpers ----------
def _manifest_path(run_id: str) -> Path:
    return config.OUTPUT_DIR / "search" / run_id / "manifest.json"

def _load_manifest(run_id: str) -> Dict[str, Any]:
    mp = _manifest_path(run_id)
    if not mp.is_file():
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro lendo manifest: {e}")

def _validated_path_from_manifest(man: Dict[str, Any]) -> Path:
    fpath = man.get("files", {}).get("xlsx_validado")
    if not fpath:
        raise HTTPException(status_code=404, detail="Arquivo validado não disponível.")
    p = Path(fpath)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Arquivo validado não encontrado no disco.")
    return p

# ---------- endpoints ----------
@router.post("/executar")
def executar_pesquisa(req: SearchRequest, current_user: CurrentUser = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Dispara a automação e retorna o manifest + link do validado.
    """
    try:
        manifest = run_site_search(req.dict(), user_id=current_user.id)
        run_id = manifest.get("run_id")
        download_url = f"/api/pesquisa/baixar/{run_id}"  # sempre o validado
        return {"ok": True, "run_id": run_id, "download_url": download_url, "manifest": manifest}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar: {e}")

@router.get("/baixar/{run_id}")
def baixar_validado(run_id: str, current_user: CurrentUser = Depends(get_current_user)):
    """
    Atalho: sempre baixa o XLSX validado desta execução.
    """
    man = _load_manifest(run_id)
    xlsxv = _validated_path_from_manifest(man)
    return FileResponse(
        path=str(xlsxv),
        filename=xlsxv.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# (opcional) manter compatibilidade com a rota antiga
@router.get("/baixar/{run_id}/{kind}")
def baixar_arquivo(run_id: str, kind: Literal["csv", "xlsx", "xlsx_validado"], current_user: CurrentUser = Depends(get_current_user)):
    man = _load_manifest(run_id)
    fpath = man.get("files", {}).get(kind)
    if not fpath:
        raise HTTPException(status_code=404, detail="Arquivo não disponível.")
    p = Path(fpath)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no disco.")
    media = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if kind != "csv" else
        "text/csv"
    )
    return FileResponse(path=str(p), filename=p.name, media_type=media)

@router.get("/runs")
def listar_runs(current_user: CurrentUser = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """
    Lista execuções focando no link do validado (para o frontend).
    """
    base = config.OUTPUT_DIR / "search"
    if not base.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for d in sorted(base.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        mp = d / "manifest.json"
        if not mp.is_file():
            continue
        try:
            man = json.loads(mp.read_text(encoding="utf-8"))
            run_id = man.get("run_id", d.name)
            # só expõe o validado
            has_valid = bool(man.get("files", {}).get("xlsx_validado"))
            out.append({
                "run_id": run_id,
                "query": man.get("query", ""),
                "created_at": run_id.split("-")[-1] if "-" in run_id else "",
                "download_url": f"/api/pesquisa/baixar/{run_id}" if has_valid else None,
                "counts": man.get("counts", {}),
            })
        except Exception:
            continue
    return out

@router.get("/status/{run_id}")
def status(run_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Retorna se a execução existe e se o validado está pronto.
    """
    mp = _manifest_path(run_id)
    exists = mp.is_file()
    ready = False
    if exists:
        try:
            man = json.loads(mp.read_text(encoding="utf-8"))
            p = _validated_path_from_manifest(man)
            ready = p.is_file()
        except Exception:
            ready = False
    return {"run_id": run_id, "exists": exists, "ready": ready}
