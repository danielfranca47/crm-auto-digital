import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional

import httpx


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


def get_messages(
    crm_base: str,
    lead_id: int,
    bearer_token: str,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    url = f"{crm_base.rstrip('/')}/messages/{lead_id}"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = httpx.get(url, headers=headers, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code != 200:
        raise RuntimeError(f"Get messages failed {response.status_code}: {data}")
    return data


def register_outbound(
    crm_base: str,
    crm_service_token: str,
    payload: Dict[str, Any],
    timeout: float = 20.0,
) -> Dict[str, Any]:
    url = f"{crm_base.rstrip('/')}/api/whatsapp/outbound"
    headers = {"X-Service-Token": crm_service_token}
    response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code != 200:
        raise RuntimeError(f"Register outbound failed {response.status_code}: {data}")
    return data


def run_executor(job_id: int, extra_env: Dict[str, str]) -> str:
    cmd = [sys.executable, "-m", "app.runners.whatsapp", "--job-id", str(job_id)]
    env = os.environ.copy()
    env.update({k: str(v) for k, v in extra_env.items()})
    process = subprocess.run(cmd, capture_output=True, text=True, env=env)
    output = (process.stdout or "") + "\n" + (process.stderr or "")
    if process.returncode != 0:
        raise RuntimeError(f"Executor failed rc={process.returncode}\n{output}")
    return output


def assert_contains(haystack: str, needle: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Expected to find '{needle}' in output.\n--- output ---\n{haystack}")


def main() -> int:
    crm_base = os.getenv("CRM_API_BASE", "http://localhost:8000")
    core_base = os.getenv("CORE_API_BASE", "http://localhost:8001")

    webhook_secret = require_env("CRM_WEBHOOK_SECRET")
    crm_service_token = require_env("CRM_SERVICE_TOKEN")
    core_service_token = require_env("CORE_SERVICE_TOKEN")

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = {
        "instance_id": os.getenv("TEST_INSTANCE_ID", "stub-instance"),
        "from": os.getenv("TEST_FROM", "+5511999999999"),
        "message_text": os.getenv("TEST_MESSAGE", "Olá, quero saber mais (stub)"),
        "message_id": os.getenv("TEST_MESSAGE_ID", f"msg-stub-{int(time.time())}"),
        "timestamp": now_iso,
        "provider": "uazapi",
    }

    print("\n[A1] Creating inbound job via CRM webhook...")
    resp = post_inbound(crm_base, webhook_secret, payload)
    print("Inbound response:", resp)

    status = resp.get("status")
    if status not in {"accepted", "duplicate"}:
        raise RuntimeError(f"Unexpected inbound status: {status}")
    if status == "duplicate":
        raise RuntimeError("Inbound returned duplicate. Change TEST_MESSAGE_ID or let it auto-generate.")

    lead_id = int(resp["lead_id"])
    job_id = int(resp["job_id"])

    executor_env = {
        "CRM_API_BASE": crm_base,
        "CORE_API_BASE": core_base,
        "CRM_SERVICE_TOKEN": crm_service_token,
        "CORE_SERVICE_TOKEN": core_service_token,
    }

    print(f"\n[A2] Running executor for job_id={job_id} ...")
    out1 = run_executor(job_id, executor_env)
    print(out1)
    assert_contains(out1, "/api/whatsapp/outbound")
    assert_contains(out1, "/whatsapp/send")
    assert_contains(out1, "mark-sent")

    print("\n[A3] Fetching job result from CRM...")
    job_payload = get_job(crm_base, job_id, crm_service_token)
    print("Job response:", job_payload)
    job = job_payload.get("job") or {}
    result = job.get("result") or {}
    outbound_status = result.get("outbound_status")
    if outbound_status not in {"sent", "already_sent"}:
        raise AssertionError(f"Unexpected outbound_status in job result: {outbound_status}")

    bearer_token = os.getenv("CRM_BEARER_TOKEN")
    if bearer_token:
        print("\n[A4] Checking messages for lead (should include outbound)...")
        msgs = get_messages(crm_base, lead_id, bearer_token)
        print("Messages response:", msgs)
        messages = msgs.get("messages") or []
        has_outbound = any(isinstance(m, dict) and m.get("model") == "outbound" for m in messages)
        if not has_outbound:
            raise AssertionError("No outbound message found in /messages/{lead_id}")
    else:
        print("\n[A4] CRM_BEARER_TOKEN not set; skipping /messages validation.")

    print("\n[A5] Idempotency check via /api/whatsapp/outbound (expect already_sent)...")
    job_payload = job.get("payload") or {}
    lead_id_payload = result.get("lead_id") or job_payload.get("lead_id")
    user_id_payload = result.get("user_id") or job_payload.get("user_id")
    phone_payload = result.get("phone") or job_payload.get("phone")
    in_reply_to_message_id = job_payload.get("message_id")

    if not lead_id_payload or not user_id_payload or not phone_payload or not in_reply_to_message_id:
        raise AssertionError(
            "Missing required data for idempotency check. "
            f"lead_id={lead_id_payload} user_id={user_id_payload} "
            f"phone={phone_payload} message_id={in_reply_to_message_id}"
        )

    outbound_payload = {
        "job_id": job_id,
        "lead_id": int(lead_id_payload),
        "user_id": int(user_id_payload),
        "phone": str(phone_payload),
        "body": result.get("outbound_body") or "stub",
        "provider": job_payload.get("provider") or "uazapi",
        "in_reply_to_message_id": str(in_reply_to_message_id),
    }
    outbound_response = register_outbound(crm_base, crm_service_token, outbound_payload)
    print("Outbound idempotency response:", outbound_response)
    if outbound_response.get("status") != "already_sent":
        raise AssertionError(
            f"Expected already_sent, got {outbound_response.get('status')}"
        )

    print("\n✅ Cenário A concluído com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
