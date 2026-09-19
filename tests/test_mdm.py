"""主数据管理业务深化测试：模型/映射/质量规则。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


async def _make_model(client, name: str = "mdm-base-01") -> str:
    resp = await client.post("/api/mdm/models", json={
        "name": name, "domain": "customer", "version": "1.0.0",
        "description": "客户主数据",
    }, headers=H)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ═══════════════════════════════════════════════════════════
# 主数据模型
# ═══════════════════════════════════════════════════════════
class TestMasterDataModel:
    async def test_create_model_success(self, client):
        resp = await client.post("/api/mdm/models", json={
            "name": "mdm-biz-01", "domain": "product", "version": "2.0.0",
            "description": "产品主数据",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "mdm-biz-01"
        assert data["status"] == "draft"
        assert data["domain"] == "product"

    async def test_create_model_requires_token(self, client):
        resp = await client.post("/api/mdm/models", json={
            "name": "mdm-no-token", "domain": "customer",
        })
        assert resp.status_code in (401, 403)

    async def test_create_model_duplicate(self, client):
        await _make_model(client, "mdm-dup-01")
        resp = await client.post("/api/mdm/models", json={
            "name": "mdm-dup-01", "domain": "customer",
        }, headers=H)
        assert resp.status_code == 409

    async def test_list_models(self, client):
        await _make_model(client, "mdm-list-01")
        resp = await client.get("/api/mdm/models", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_list_models_domain_filter(self, client):
        await client.post("/api/mdm/models", json={
            "name": "mdm-domain-emp", "domain": "employee",
        }, headers=H)
        resp = await client.get("/api/mdm/models?domain=employee", headers=H)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["domain"] == "employee"

    async def test_list_models_keyword(self, client):
        await client.post("/api/mdm/models", json={
            "name": "mdm-kw-unique", "domain": "supplier", "description": "供应商专属描述",
        }, headers=H)
        resp = await client.get("/api/mdm/models?keyword=" + "供应商专属", headers=H)
        assert resp.status_code == 200
        names = [i["name"] for i in resp.json()["items"]]
        assert "mdm-kw-unique" in names

    async def test_get_model(self, client):
        mid = await _make_model(client, "mdm-get-01")
        resp = await client.get(f"/api/mdm/models/{mid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == mid

    async def test_get_model_not_found(self, client):
        resp = await client.get("/api/mdm/models/no-such", headers=H)
        assert resp.status_code == 404

    async def test_update_model(self, client):
        mid = await _make_model(client, "mdm-upd-01")
        resp = await client.patch(f"/api/mdm/models/{mid}", json={
            "description": "更新后的描述", "version": "1.1.0",
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["description"] == "更新后的描述"
        assert resp.json()["version"] == "1.1.0"

    async def test_model_publish_flow(self, client):
        mid = await _make_model(client, "mdm-pub-01")
        r1 = await client.patch(f"/api/mdm/models/{mid}/status",
                                json={"status": "published"}, headers=H)
        assert r1.status_code == 200
        assert r1.json()["status"] == "published"
        r2 = await client.patch(f"/api/mdm/models/{mid}/status",
                                json={"status": "deprecated"}, headers=H)
        assert r2.status_code == 200
        assert r2.json()["status"] == "deprecated"

    async def test_model_invalid_transition(self, client):
        mid = await _make_model(client, "mdm-bad-01")
        # draft -> published -> deprecated；deprecated 不能回到 draft
        await client.patch(f"/api/mdm/models/{mid}/status",
                           json={"status": "published"}, headers=H)
        await client.patch(f"/api/mdm/models/{mid}/status",
                           json={"status": "deprecated"}, headers=H)
        resp = await client.patch(f"/api/mdm/models/{mid}/status",
                                  json={"status": "draft"}, headers=H)
        assert resp.status_code == 400

    async def test_deprecated_model_immutable(self, client):
        mid = await _make_model(client, "mdm-imm-01")
        await client.patch(f"/api/mdm/models/{mid}/status",
                           json={"status": "deprecated"}, headers=H)
        resp = await client.patch(f"/api/mdm/models/{mid}",
                                  json={"description": "尝试修改"}, headers=H)
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════
# 映射规则
# ═══════════════════════════════════════════════════════════
class TestDataMapping:
    async def test_create_mapping_success(self, client):
        mid = await _make_model(client, "map-model-01")
        resp = await client.post("/api/mdm/mappings", json={
            "name": "crm映射", "source_system": "CRM", "target_model_id": mid,
            "mapping_type": "direct", "field_mapping": '{"crm_id":"id"}',
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_system"] == "CRM"
        assert data["status"] == "active"

    async def test_mapping_missing_model(self, client):
        resp = await client.post("/api/mdm/mappings", json={
            "name": "孤儿映射", "source_system": "ERP", "target_model_id": "no-such-model",
        }, headers=H)
        assert resp.status_code == 400

    async def test_mapping_duplicate(self, client):
        mid = await _make_model(client, "map-model-dup")
        await client.post("/api/mdm/mappings", json={
            "name": "重复映射", "source_system": "SRC", "target_model_id": mid,
        }, headers=H)
        resp = await client.post("/api/mdm/mappings", json={
            "name": "重复映射", "source_system": "SRC", "target_model_id": mid,
        }, headers=H)
        assert resp.status_code == 409

    async def test_list_mappings_filter(self, client):
        mid = await _make_model(client, "map-model-list")
        await client.post("/api/mdm/mappings", json={
            "name": "列表映射", "source_system": "ERP2", "target_model_id": mid,
        }, headers=H)
        resp = await client.get(f"/api/mdm/mappings?target_model_id={mid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_mapping_disable(self, client):
        mid = await _make_model(client, "map-model-dis")
        created = await client.post("/api/mdm/mappings", json={
            "name": "停用映射", "source_system": "DIS", "target_model_id": mid,
        }, headers=H)
        mid_id = created.json()["id"]
        resp = await client.patch(f"/api/mdm/mappings/{mid_id}/status",
                                  json={"status": "inactive"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

    async def test_mapping_requires_token(self, client):
        resp = await client.post("/api/mdm/mappings", json={
            "name": "无令牌映射", "source_system": "X", "target_model_id": "y",
        })
        assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════
# 质量规则
# ═══════════════════════════════════════════════════════════
class TestMDMQualityRule:
    async def test_create_rule_success(self, client):
        mid = await _make_model(client, "rule-model-01")
        resp = await client.post("/api/mdm/rules", json={
            "name": "非空校验", "model_id": mid, "rule_type": "not_null",
            "expression": "customer_id", "severity": "error",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_type"] == "not_null"
        assert data["severity"] == "error"

    async def test_rule_missing_model(self, client):
        resp = await client.post("/api/mdm/rules", json={
            "name": "幽灵规则", "model_id": "no-such", "rule_type": "unique",
            "expression": "id",
        }, headers=H)
        assert resp.status_code == 400

    async def test_rule_empty_expression_rejected(self, client):
        mid = await _make_model(client, "rule-model-empty")
        resp = await client.post("/api/mdm/rules", json={
            "name": "空表达式", "model_id": mid, "rule_type": "regex", "expression": "",
        }, headers=H)
        assert resp.status_code == 422

    async def test_list_rules_filter(self, client):
        mid = await _make_model(client, "rule-model-list")
        await client.post("/api/mdm/rules", json={
            "name": "列表规则", "model_id": mid, "rule_type": "range",
            "expression": "age>=0",
        }, headers=H)
        resp = await client.get(f"/api/mdm/rules?model_id={mid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_rule_disable(self, client):
        mid = await _make_model(client, "rule-model-dis")
        created = await client.post("/api/mdm/rules", json={
            "name": "停用规则", "model_id": mid, "rule_type": "unique",
            "expression": "phone",
        }, headers=H)
        rid = created.json()["id"]
        resp = await client.patch(f"/api/mdm/rules/{rid}/status",
                                  json={"status": "disabled"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    async def test_rule_requires_token(self, client):
        resp = await client.post("/api/mdm/rules", json={
            "name": "无令牌规则", "model_id": "x", "rule_type": "not_null",
            "expression": "a",
        })
        assert resp.status_code in (401, 403)
