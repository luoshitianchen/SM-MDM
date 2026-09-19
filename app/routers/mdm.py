"""主数据管理业务路由：主数据模型 / 映射规则 / 质量规则。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.mdm import (
    MappingCreate,
    MappingStatusUpdate,
    ModelCreate,
    ModelStatusUpdate,
    ModelUpdate,
    QualityRuleCreate,
    QualityRuleStatusUpdate,
)
from app.services.mdm import MDMService

router = APIRouter(prefix="/api/mdm", tags=["mdm"])


# ── 主数据模型 ──
@router.get("/models")
async def list_models(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    domain: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.list_models(session, limit=limit, offset=offset, domain=domain,
                                        status_filter=status_filter, keyword=keyword)


@router.post("/models", status_code=status.HTTP_201_CREATED)
async def create_model(
    payload: ModelCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.create_model(session, payload, request)


@router.get("/models/{model_id}")
async def get_model(
    model_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.get_model(session, model_id)


@router.patch("/models/{model_id}")
async def update_model(
    model_id: str, payload: ModelUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.update_model(session, model_id, payload, request)


@router.patch("/models/{model_id}/status")
async def update_model_status(
    model_id: str, payload: ModelStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.update_model_status(session, model_id, payload, request)


# ── 映射规则 ──
@router.get("/mappings")
async def list_mappings(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    target_model_id: str | None = Query(default=None),
    source_system: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.list_mappings(session, limit=limit, offset=offset,
                                          target_model_id=target_model_id,
                                          source_system=source_system)


@router.post("/mappings", status_code=status.HTTP_201_CREATED)
async def create_mapping(
    payload: MappingCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.create_mapping(session, payload, request)


@router.patch("/mappings/{mapping_id}/status")
async def update_mapping_status(
    mapping_id: str, payload: MappingStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.update_mapping_status(session, mapping_id, payload, request)


# ── 质量规则 ──
@router.get("/rules")
async def list_rules(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    model_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.list_rules(session, limit=limit, offset=offset,
                                      model_id=model_id, status_filter=status_filter)


@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: QualityRuleCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.create_rule(session, payload, request)


@router.patch("/rules/{rule_id}/status")
async def update_rule_status(
    rule_id: str, payload: QualityRuleStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MDMService.update_rule_status(session, rule_id, payload, request)
