from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib import error, request

import asyncpg
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL = "http://127.0.0.1:8010/api/v1"
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/ai_sales")


def http_json(method: str, url: str, payload: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=25) as resp:
            return resp.status, resp.read().decode("utf-8")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def http_multipart_upload(url: str, tenant_id: str, file_path: Path) -> tuple[int, str]:
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = file_path.name
    content = file_path.read_bytes()

    body = []
    body.append(f"--{boundary}\r\n".encode())
    body.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    body.append(b"Content-Type: application/octet-stream\r\n\r\n")
    body.append(content)
    body.append(b"\r\n")
    body.append(f"--{boundary}--\r\n".encode())
    data = b"".join(body)

    req = request.Request(
        f"{url}?tenant_id={tenant_id}",
        data=data,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


async def fetch_seed_ids() -> tuple[str, str, str]:
    dsn = DB_URL.replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn=dsn)
    try:
        tenant = await conn.fetchval("select tenant_id::text from tenants where slug='demo-tenant' limit 1")
        resource = await conn.fetchval(
            "select id::text from resources where tenant_id=$1::uuid order by created_at desc limit 1", tenant
        )
        service = await conn.fetchval(
            "select id::text from services where tenant_id=$1::uuid order by created_at desc limit 1", tenant
        )
    finally:
        await conn.close()

    if not tenant or not resource or not service:
        raise RuntimeError("No hay datos sembrados suficientes en Postgres")
    return tenant, resource, service


async def main() -> None:
    tenant_id, resource_id, service_id = await fetch_seed_ids()

    start_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")

    tests: list[tuple[str, int, str]] = []

    st, body = http_json(
        "POST",
        f"{BASE_URL}/appointments/availability",
        {
            "tenant_id": tenant_id,
            "resource_id": resource_id,
            "service_id": service_id,
            "start_date": start_date,
            "end_date": end_date,
            "slot_granularity_minutes": 30,
        },
    )
    tests.append(("POST /appointments/availability", st, body))

    start_at = (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    st, body = http_json(
        "POST",
        f"{BASE_URL}/appointments",
        {
            "tenant_id": tenant_id,
            "resource_id": resource_id,
            "service_id": service_id,
            "customer_name": "Test API Script",
            "customer_phone": "+18888888888",
            "start_at": start_at.isoformat(),
            "notes": "script endpoint test",
        },
    )
    tests.append(("POST /appointments", st, body))

    appointment_id = None
    payment_intent_id = None
    if st == 201:
        appt = json.loads(body)
        appointment_id = appt.get("id")

    if appointment_id:
        st, body = http_json("GET", f"{BASE_URL}/appointments/{appointment_id}/payment-intent")
        tests.append(("GET /appointments/{id}/payment-intent", st, body))
        if st == 200:
            pi = json.loads(body)
            payment_intent_id = pi.get("payment_intent_id")

    if payment_intent_id:
        st, body = http_json(
            "POST",
            f"{BASE_URL}/payments/webhook",
            {
                "tenant_id": tenant_id,
                "payment_intent_id": payment_intent_id,
                "status": "SUCCEEDED",
                "paid_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "raw_payload": {"source": "scripts/test_endpoints.py"},
            },
        )
        tests.append(("POST /payments/webhook", st, body))

    st, body = http_json(
        "POST",
        f"{BASE_URL}/ai/reply",
        {"tenant_id": tenant_id, "message": "Quiero agendar una consulta para manana"},
    )
    tests.append(("POST /ai/reply", st, body))

    sample_file = Path("media") / "sample.jpg"
    if sample_file.exists():
        st, body = http_multipart_upload(f"{BASE_URL}/media/upload", tenant_id, sample_file)
        tests.append(("POST /media/upload", st, body))
        if st in (200, 201):
            upload = json.loads(body)
            filename = Path(upload.get("url", "")).name
            st2, body2 = http_json("GET", f"{BASE_URL}/media/files/{filename}")
            tests.append(("GET /media/files/{filename}", st2, body2))

    print("== Endpoint Test Results ==")
    for name, status, response in tests:
        print(f"{name}: {status}")
        print(response)
        print("---")


if __name__ == "__main__":
    asyncio.run(main())
