"""主数据管理业务服务层：模型/映射/质量规则全生命周期。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.mdm import DataMapping, MasterDataModel, MDMQualityRule
from app.repositories import mdm as repo
from app.schemas.mdm import (
    MappingCreate,
    MappingStatusUpdate,
    ModelCreate,
    ModelStatusUpdate,
    ModelUpdate,
    QualityRuleCreate,
    QualityRuleStatusUpdate,
)
from app.services.audit import record_audit

# 主数据模型状态机
_MODEL_TRANSITIONS = {
    "draft": {"published", "deprecated"},
    "published": {"deprecated"},
    "deprecated": set(),
}


def _model_to_dict(m: MasterDataModel) -> dict:
    return {
        "id": m.id, "name": m.name, "domain": m.domain, "version": m.version,
        "description": m.description, "status": m.status,
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else "",
    }


def _mapping_to_dict(m: DataMapping) -> dict:
    return {
        "id": m.id, "name": m.name, "source_system": m.source_system,
        "target_model_id": m.target_model_id, "mapping_type": m.mapping_type,
        "field_mapping": m.field_mapping, "status": m.status,
        "created_at": m.created_at.isoformat() if m.created_at else "",
    }


def _rule_to_dict(r: MDMQualityRule) -> dict:
    return {
        "id": r.id, "name": r.name, "model_id": r.model_id,
        "rule_type": r.rule_type, "expression": r.expression,
        "severity": r.severity, "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


class MDMService:
    """主数据管理领域服务。"""

    @staticmethod
    def _require_write(request: Request) -> None:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")

    # ── 主数据模型 ──
    @staticmethod
    async def list_models(session: AsyncSession, limit: int = 100, offset: int = 0,
                          domain: str | None = None, status_filter: str | None = None,
                          keyword: str | None = None) -> dict:
        items = await repo.list_models(session, limit=limit, offset=offset, domain=domain,
                                       status=status_filter, keyword=keyword)
        total = await repo.count_models(session, domain=domain, status=status_filter,
                                        keyword=keyword)
        return {"total": total, "items": [_model_to_dict(m) for m in items]}

    @staticmethod
    async def get_model(session: AsyncSession, model_id: str) -> dict:
        model = await repo.get_model(session, model_id)
        if not model:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "主数据模型不存在")
        return _model_to_dict(model)

    @staticmethod
    async def create_model(session: AsyncSession, payload: ModelCreate, request: Request) -> dict:
        MDMService._require_write(request)
        if await repo.get_model_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "主数据模型名称已存在")
        model = MasterDataModel(
            id=str(uuid.uuid4()), name=payload.name, domain=payload.domain,
            version=payload.version, description=payload.description, status="draft",
        )
        model = await repo.save_model(session, model)
        await record_audit(session, "mdm.model.created", "internal",
                           f"model_id={model.id} name={payload.name}", request)
        return _model_to_dict(model)

    @staticmethod
    async def update_model(session: AsyncSession, model_id: str,
                           payload: ModelUpdate, request: Request) -> dict:
        MDMService._require_write(request)
        model = await repo.get_model(session, model_id)
        if not model:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "主数据模型不存在")
        if model.status == "deprecated":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "已废弃的模型不可修改")
        if payload.description is not None:
            model.description = payload.description
        if payload.version is not None:
            model.version = payload.version
        model = await repo.save_model(session, model)
        await record_audit(session, "mdm.model.updated", "internal",
                           f"model_id={model_id}", request)
        return _model_to_dict(model)

    @staticmethod
    async def update_model_status(session: AsyncSession, model_id: str,
                                  payload: ModelStatusUpdate, request: Request) -> dict:
        MDMService._require_write(request)
        model = await repo.get_model(session, model_id)
        if not model:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "主数据模型不存在")
        new_status = payload.status
        if new_status == model.status:
            return _model_to_dict(model)
        if new_status not in _MODEL_TRANSITIONS.get(model.status, set()):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"非法状态迁移: {model.status} -> {new_status}")
        model.status = new_status
        model = await repo.save_model(session, model)
        await record_audit(session, "mdm.model.status_changed", "internal",
                           f"model_id={model_id} status={new_status}", request)
        return _model_to_dict(model)

    # ── 映射规则 ──
    @staticmethod
    async def list_mappings(session: AsyncSession, limit: int = 100, offset: int = 0,
                            target_model_id: str | None = None,
                            source_system: str | None = None) -> dict:
        items = await repo.list_mappings(session, limit=limit, offset=offset,
                                         target_model_id=target_model_id,
                                         source_system=source_system)
        total = await repo.count_mappings(session, target_model_id=target_model_id,
                                          source_system=source_system)
        return {"total": total, "items": [_mapping_to_dict(m) for m in items]}

    @staticmethod
    async def create_mapping(session: AsyncSession, payload: MappingCreate,
                             request: Request) -> dict:
        MDMService._require_write(request)
        if not await repo.get_model(session, payload.target_model_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "目标主数据模型不存在")
        if await repo.find_mapping(session, payload.source_system, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "同名源系统映射已存在")
        mapping = DataMapping(
            id=str(uuid.uuid4()), name=payload.name, source_system=payload.source_system,
            target_model_id=payload.target_model_id, mapping_type=payload.mapping_type,
            field_mapping=payload.field_mapping, status="active",
        )
        mapping = await repo.save_mapping(session, mapping)
        await record_audit(session, "mdm.mapping.created", "internal",
                           f"mapping_id={mapping.id} name={payload.name}", request)
        return _mapping_to_dict(mapping)

    @staticmethod
    async def update_mapping_status(session: AsyncSession, mapping_id: str,
                                    payload: MappingStatusUpdate, request: Request) -> dict:
        MDMService._require_write(request)
        mapping = await repo.get_mapping(session, mapping_id)
        if not mapping:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "映射规则不存在")
        mapping.status = payload.status
        mapping = await repo.save_mapping(session, mapping)
        await record_audit(session, "mdm.mapping.status_changed", "internal",
                           f"mapping_id={mapping_id} status={payload.status}", request)
        return _mapping_to_dict(mapping)

    # ── 质量规则 ──
    @staticmethod
    async def list_rules(session: AsyncSession, limit: int = 100, offset: int = 0,
                         model_id: str | None = None,
                         status_filter: str | None = None) -> dict:
        items = await repo.list_rules(session, limit=limit, offset=offset,
                                      model_id=model_id, status=status_filter)
        total = await repo.count_rules(session, model_id=model_id, status=status_filter)
        return {"total": total, "items": [_rule_to_dict(r) for r in items]}

    @staticmethod
    async def create_rule(session: AsyncSession, payload: QualityRuleCreate,
                          request: Request) -> dict:
        MDMService._require_write(request)
        if not await repo.get_model(session, payload.model_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "关联的主数据模型不存在")
        rule = MDMQualityRule(
            id=str(uuid.uuid4()), name=payload.name, model_id=payload.model_id,
            rule_type=payload.rule_type, expression=payload.expression,
            severity=payload.severity, status="active",
        )
        rule = await repo.save_rule(session, rule)
        await record_audit(session, "mdm.rule.created", "internal",
                           f"rule_id={rule.id} name={payload.name}", request)
        return _rule_to_dict(rule)

    @staticmethod
    async def update_rule_status(session: AsyncSession, rule_id: str,
                                 payload: QualityRuleStatusUpdate, request: Request) -> dict:
        MDMService._require_write(request)
        rule = await repo.get_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "质量规则不存在")
        rule.status = payload.status
        rule = await repo.save_rule(session, rule)
        await record_audit(session, "mdm.rule.status_changed", "internal",
                           f"rule_id={rule_id} status={payload.status}", request)
        return _rule_to_dict(rule)
