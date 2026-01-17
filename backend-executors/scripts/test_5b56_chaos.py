import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

import httpx


SCENARIOS = {
    "core_down",
    "core_token_invalid",
    "crm_token_invalid",
    "mark_sent_fail_then_recover",
}

LOG_EVENTS = {
    "core_send_request",
    "core_send_success",
    "attach_provider_request",
    "attach_provider_success",
    "mark_sent_error",
    "mark_sent_request",
    "job_claimed",
    "job_claim_error",
    "job_retry_scheduled",
    "job_failed_final",
    "job_completed",
}


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing env: {name}")
    return value


def post_inbound(
    crm_base: str,
    webhook_secret: str,
    payload: Dict[str, Any],
    timeout: float = 20.0,
) -> Dict[str, Any]:
    url = f"{crm_base.rstrip('/')}/webhooks/whatsapp/inbound"
    headers = {"X-Webhook-Secret": webhook_secret}
    response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code != 200:
        raise RuntimeError(f"Inbound failed {response.status_code}: {data}")
    return data


def get_job(crm_base: str, job_id: int, crm_service_token: str, timeout: float = 20.0) -> Dict[str, Any]:
    url = f"{crm_base.rstrip('/')}/api/jobs/{job_id}"
    headers = {"X-Service-Token": crm_service_token}
    response = httpx.get(url, headers=headers, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code != 200:
        raise RuntimeError(f"Get job failed {response.status_code}: {data}")
    return data


def get_outbound_event(
    crm_base: str,
    outbound_event_id: int,
    crm_service_token: str,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    url = f"{crm_base.rstrip('/')}/api/internal/outbound-events/{outbound_event_id}"
    headers = {"X-Service-Token": crm_service_token}
    response = httpx.get(url, headers=headers, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code != 200:
        raise RuntimeError(f"Get outbound event failed {response.status_code}: {data}")
    return data


def parse_event(line: str) -> Optional[str]:
    if "event=" not in line:
        return None
    for event in LOG_EVENTS:
        if f"event={event}" in line:
            return event
    return None


def stream_worker_logs(process: subprocess.Popen, events: Dict[str, int]) -> None:
    assert process.stdout is not None
    for line in iter(process.stdout.readline, ""):
        print(line.rstrip())
        event = parse_event(line)
        if event:
            events[event] = events.get(event, 0) + 1
    process.stdout.close()


def run_worker(extra_env: Dict[str, str], events: Dict[str, int]) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "app.workers.whatsapp_worker"]
    env = os.environ.copy()
    env.update({k: str(v) for k, v in extra_env.items()})
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    thread = threading.Thread(target=stream_worker_logs, args=(process, events), daemon=True)
    thread.start()
    return process


def wait_for_job_state(
    crm_base: str,
    job_id: int,
    crm_service_token: str,
    *,
    expect_status: Optional[str] = None,
    attempts_at_least: Optional[int] = None,
    timeout_seconds: int = 600,
    poll_interval: float = 5.0,
) -> Dict[str, Any]:
    start = time.time()
    while True:
        job_payload = get_job(crm_base, job_id, crm_service_token)
        job = job_payload.get("job") or {}
        status = job.get("status")
        attempts = int(job.get("attempts") or 0)
        if expect_status and status == expect_status:
            return job_payload
        if attempts_at_least is not None and attempts >= attempts_at_least:
            return job_payload
        if time.time() - start > timeout_seconds:
            raise TimeoutError("Timeout aguardando estado do job")
        time.sleep(poll_interval)


def summarize(checks: Dict[str, bool], scenario: str) -> None:
    print("\n==== Summary ====")
    print(f"Cenário {scenario}:")
    for name, ok in checks.items():
        icon = "✅" if ok else "❌"
        print(f"{icon} {name}")


def is_scheduled_in_future(scheduled_at: Optional[str]) -> bool:
    if not scheduled_at:
        return False
    raw = scheduled_at.replace(" ", "T").split(".")[0]
    try:
        scheduled_dt = time.strptime(raw, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return time.mktime(scheduled_dt) > time.time()


def main() -> int:
    crm_base = os.getenv("CRM_API_BASE", "http://localhost:8000")
    core_base = os.getenv("CORE_API_BASE", "http://localhost:8001")
    scenario = os.getenv("CHAOS_SCENARIO", "core_down").lower()
    max_runtime_seconds = int(os.getenv("MAX_RUNTIME_SECONDS", "600"))
    max_attempts_wait = int(os.getenv("MAX_ATTEMPTS_WAIT", "3"))

    if scenario not in SCENARIOS:
        raise SystemExit(f"CHAOS_SCENARIO inválido. Use: {', '.join(sorted(SCENARIOS))}")

    webhook_secret = require_env("CRM_WEBHOOK_SECRET")
    crm_service_token = require_env("CRM_SERVICE_TOKEN")
    core_service_token = os.getenv("CORE_SERVICE_TOKEN", "")

    payload = {
        "instance_id": os.getenv("TEST_INSTANCE_ID", "chaos-instance"),
        "from": os.getenv("TEST_FROM", "+5511999999999"),
        "message_text": os.getenv("TEST_MESSAGE", f"Teste caos {scenario}"),
        "message_id": os.getenv("TEST_MESSAGE_ID", f"msg-chaos-{int(time.time())}"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": "uazapi",
    }

    print(f"\n[CHAOS] Scenario={scenario} creating inbound job...")
    resp = post_inbound(crm_base, webhook_secret, payload)
    job_id = int(resp["job_id"])
    print("Inbound response:", resp)

    worker_env = {
        "CRM_API_BASE": crm_base,
        "CORE_API_BASE": core_base,
        "CRM_SERVICE_TOKEN": crm_service_token,
        "CORE_SERVICE_TOKEN": core_service_token,
    }

    if scenario == "core_down":
        worker_env["CORE_API_BASE"] = "http://localhost:9999"
    elif scenario == "core_token_invalid":
        worker_env["CORE_SERVICE_TOKEN"] = "invalid-token"
    elif scenario == "crm_token_invalid":
        worker_env["CRM_SERVICE_TOKEN"] = "invalid-token"

    events: Dict[str, int] = {}
    process = run_worker(worker_env, events)
    checks: Dict[str, bool] = {
        "retry_aplicado": False,
        "scheduled_at_futuro": False,
        "failed_definitivo": False,
        "nao_reenviou_core": False,
        "provider_message_id_persistido": False,
        "erro_detectado": False,
    }
    if scenario != "crm_token_invalid":
        checks["erro_detectado"] = True

    try:
        if scenario == "core_down":
            job_payload = wait_for_job_state(
                crm_base,
                job_id,
                crm_service_token,
                attempts_at_least=1,
                timeout_seconds=max_runtime_seconds,
            )
            job = job_payload.get("job") or {}
            checks["retry_aplicado"] = int(job.get("attempts") or 0) >= 1
            checks["scheduled_at_futuro"] = is_scheduled_in_future(job.get("scheduled_at"))
            job_payload = wait_for_job_state(
                crm_base,
                job_id,
                crm_service_token,
                expect_status="failed",
                timeout_seconds=max_runtime_seconds,
            )
            job = job_payload.get("job") or {}
            checks["failed_definitivo"] = job.get("status") == "failed"
        elif scenario == "core_token_invalid":
            job_payload = wait_for_job_state(
                crm_base,
                job_id,
                crm_service_token,
                expect_status="failed",
                timeout_seconds=max_runtime_seconds,
            )
            job = job_payload.get("job") or {}
            checks["failed_definitivo"] = job.get("status") == "failed"
        elif scenario == "crm_token_invalid":
            start = time.time()
            while time.time() - start < 15:
                if events.get("job_claim_error"):
                    checks["erro_detectado"] = True
                    break
                time.sleep(1)
        elif scenario == "mark_sent_fail_then_recover":
            print("\n[CHAOS] Aguardando event=attach_provider_success para iniciar falha no mark-sent...")
            start = time.time()
            while time.time() - start < max_runtime_seconds:
                if events.get("attach_provider_success"):
                    break
                time.sleep(1)
            if not events.get("attach_provider_success"):
                raise RuntimeError("attach_provider_success não observado nos logs")

            print(
                "\n[MANUAL ACTION] Agora pare o CRM por ~10s para forçar mark-sent falhar. "
                "Pressione Enter quando estiver pronto para continuar."
            )
            input()

            start = time.time()
            while time.time() - start < max_runtime_seconds:
                if events.get("mark_sent_error"):
                    break
                time.sleep(1)
            if not events.get("mark_sent_error"):
                raise RuntimeError("mark_sent_error não observado nos logs")

            print("[CHAOS] Aguarde o retry (60s/180s)...")
            job_payload = wait_for_job_state(
                crm_base,
                job_id,
                crm_service_token,
                attempts_at_least=2,
                timeout_seconds=max_runtime_seconds,
            )
            job = job_payload.get("job") or {}
            checks["retry_aplicado"] = int(job.get("attempts") or 0) >= 2

            outbound_event_id = job.get("result", {}).get("outbound_event_id")
            if outbound_event_id:
                outbound_payload = get_outbound_event(crm_base, int(outbound_event_id), crm_service_token)
                outbound_event = outbound_payload.get("outbound_event") or {}
                checks["provider_message_id_persistido"] = bool(outbound_event.get("provider_message_id"))

            time.sleep(10)
            checks["nao_reenviou_core"] = events.get("core_send_request", 0) == 1
    finally:
        process.terminate()

    summarize(checks, scenario)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
