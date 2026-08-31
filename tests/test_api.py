"""SM MDM 领域测试：数据域、记录、黄金记录与去重。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _domain(client, name="customer"):
    return client.post("/api/mdm/domains", json={"name": name, "description": "客户主数据"}).json()["id"]


def _record(client, domain="customer", sid="c-1", name="张三"):
    return client.post("/api/mdm/records", json={"domain": domain, "source_system": "erp", "source_id": sid, "data": {"name": name}}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_domain_lifecycle(client):
    _domain(client)
    assert client.post("/api/mdm/domains", json={"name": "customer"}).status_code == 409
    assert client.get("/api/mdm/domains").json()["total"] == 1


def test_record_and_golden(client):
    _domain(client)
    r1 = _record(client, sid="c-1")
    r2 = _record(client, sid="c-2")
    assert client.get("/api/mdm/records").json()["total"] == 2
    assert client.post(f"/api/mdm/records/{r1}/golden").json()["is_golden"] is True
    # 同域仅一条黄金记录
    assert client.post(f"/api/mdm/records/{r2}/golden").json()["is_golden"] is True
    assert client.get("/api/mdm/golden/customer").json()["total"] == 1
    golden = client.get("/api/mdm/golden/customer").json()["items"][0]
    assert golden["id"] == r2


def test_dedupe(client):
    _domain(client)
    _record(client, sid="dup")
    _record(client, sid="dup")
    _record(client, sid="unique")
    result = client.post("/api/mdm/dedupe/customer").json()
    assert result["duplicates_merged"] == 1
    assert result["remaining"] == 2


def test_missing(client):
    assert client.post("/api/mdm/records", json={"domain": "ghost", "source_system": "erp", "source_id": "1", "data": {"a": 1}}).status_code == 404
    assert client.get("/api/mdm/records/nope").status_code == 404
    assert client.get("/api/mdm/golden/ghost").status_code == 404


def test_stats(client):
    _domain(client)
    _record(client)
    stats = client.get("/api/mdm/stats").json()
    assert stats["domains"] == 1
    assert stats["records"] == 1


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/mdm/domains", json={"name": "d"}).status_code == 401
