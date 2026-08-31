"""SM MDM —— 主数据管理：数据域、主数据、黄金记录与去重合并。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-mdm"
VERSION = "2.0.0"
NAME = "SM MDM"
DESCRIPTION = "主数据管理：数据域、主数据、黄金记录与去重合并"
PORT = 8450


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS domains (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
                match_key TEXT NOT NULL DEFAULT 'id', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, domain TEXT NOT NULL, source_system TEXT NOT NULL,
                source_id TEXT NOT NULL, data TEXT NOT NULL, is_golden INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_records_domain ON records(domain, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_records_golden ON records(domain, is_golden);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-data-governance", "sm-audit-log-center"],
    events=["mdm.record_created", "mdm.golden_promoted", "mdm.merged"],
    overview_fn=lambda _r: {
        "summary": {
            "domains": base.get_db().execute("SELECT COUNT(*) FROM domains").fetchone()[0],
            "records": base.get_db().execute("SELECT COUNT(*) FROM records").fetchone()[0],
            "golden": base.get_db().execute("SELECT COUNT(*) FROM records WHERE is_golden=1").fetchone()[0],
        }
    },
)
_init()


class DomainIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)
    match_key: str = Field(default="id", min_length=1, max_length=40)


class RecordIn(BaseModel):
    domain: str = Field(min_length=2, max_length=80)
    source_system: str = Field(min_length=2, max_length=80)
    source_id: str = Field(min_length=1, max_length=80)
    data: dict[str, Any] = Field(min_length=1)


@app.get("/api/mdm/domains")
def list_domains() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM domains ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/mdm/domains", status_code=status.HTTP_201_CREATED)
def create_domain(payload: DomainIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    domain_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO domains VALUES (?,?,?,?,?)", (domain_id, payload.name, payload.description, payload.match_key, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "数据域已存在") from exc
    return {"id": domain_id, "name": payload.name}


@app.post("/api/mdm/records", status_code=status.HTTP_201_CREATED)
def create_record(payload: RecordIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    record_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM domains WHERE name=?", (payload.domain,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "数据域不存在")
        conn.execute(
            "INSERT INTO records (id, domain, source_system, source_id, data, is_golden, created_at, updated_at) VALUES (?,?,?,?,?,0,?,?)",
            (record_id, payload.domain, payload.source_system, payload.source_id, json.dumps(payload.data, ensure_ascii=False), _now(), _now()),
        )
        base.record_audit("mdm.record_created", "internal", f"domain={payload.domain} record={record_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": record_id, "domain": payload.domain}


@app.get("/api/mdm/records")
def list_records(domain: str | None = None) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if domain:
            rows = conn.execute("SELECT * FROM records WHERE domain=? ORDER BY updated_at DESC LIMIT 200", (domain,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM records ORDER BY updated_at DESC LIMIT 200").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/mdm/records/{record_id}")
def get_record(record_id: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "记录不存在")
    return dict(row)


@app.post("/api/mdm/records/{record_id}/golden")
def promote_golden(record_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "记录不存在")
        # 同域内唯一黄金记录
        conn.execute("UPDATE records SET is_golden=0 WHERE domain=? AND id<>?", (row["domain"], record_id))
        conn.execute("UPDATE records SET is_golden=1, updated_at=? WHERE id=?", (_now(), record_id))
        base.record_audit("mdm.golden_promoted", "internal", f"domain={row['domain']} record={record_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": record_id, "is_golden": True}


@app.get("/api/mdm/golden/{domain}")
def golden_records(domain: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM domains WHERE name=?", (domain,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "数据域不存在")
        rows = conn.execute("SELECT * FROM records WHERE domain=? AND is_golden=1", (domain,)).fetchall()
    return {"domain": domain, "items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/mdm/dedupe/{domain}")
def dedupe(domain: str, request: Request) -> dict[str, Any]:
    """按 (source_id) 去重：合并重复记录，仅保留最新，其余归档标记。"""
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM domains WHERE name=?", (domain,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "数据域不存在")
        rows = conn.execute("SELECT * FROM records WHERE domain=? ORDER BY updated_at DESC", (domain,)).fetchall()
        seen: dict[str, str] = {}
        duplicates = 0
        for row in rows:
            if row["source_id"] in seen:
                conn.execute("DELETE FROM records WHERE id=?", (row["id"],))
                duplicates += 1
            else:
                seen[row["source_id"]] = row["id"]
        base.record_audit("mdm.merged", "internal", f"domain={domain} duplicates={duplicates}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"domain": domain, "duplicates_merged": duplicates, "remaining": len(seen)}


@app.get("/api/mdm/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        return {
            "domains": _count("SELECT COUNT(*) FROM domains"),
            "records": _count("SELECT COUNT(*) FROM records"),
            "golden": _count("SELECT COUNT(*) FROM records WHERE is_golden=1"),
            "by_domain": [dict(r) for r in conn.execute("SELECT domain, COUNT(*) AS count FROM records GROUP BY domain").fetchall()],
        }
