"""主数据管理业务仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mdm import DataMapping, MasterDataModel, MDMQualityRule


# ── 主数据模型 ──
async def get_model(session: AsyncSession, model_id: str) -> MasterDataModel | None:
    result = await session.execute(select(MasterDataModel).where(MasterDataModel.id == model_id))
    return result.scalar_one_or_none()


async def get_model_by_name(session: AsyncSession, name: str) -> MasterDataModel | None:
    result = await session.execute(select(MasterDataModel).where(MasterDataModel.name == name))
    return result.scalar_one_or_none()


async def list_models(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    domain: str | None = None, status: str | None = None,
    keyword: str | None = None,
) -> list[MasterDataModel]:
    stmt = select(MasterDataModel).order_by(MasterDataModel.created_at.desc()).limit(limit).offset(offset)
    if domain:
        stmt = stmt.where(MasterDataModel.domain == domain)
    if status:
        stmt = stmt.where(MasterDataModel.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(MasterDataModel.name.like(like), MasterDataModel.description.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_models(
    session: AsyncSession, domain: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(MasterDataModel.id))
    if domain:
        stmt = stmt.where(MasterDataModel.domain == domain)
    if status:
        stmt = stmt.where(MasterDataModel.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(MasterDataModel.name.like(like), MasterDataModel.description.like(like)))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_model(session: AsyncSession, model: MasterDataModel) -> MasterDataModel:
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model


# ── 映射规则 ──
async def get_mapping(session: AsyncSession, mapping_id: str) -> DataMapping | None:
    result = await session.execute(select(DataMapping).where(DataMapping.id == mapping_id))
    return result.scalar_one_or_none()


async def find_mapping(
    session: AsyncSession, source_system: str, name: str,
) -> DataMapping | None:
    result = await session.execute(
        select(DataMapping).where(
            DataMapping.source_system == source_system,
            DataMapping.name == name,
        )
    )
    return result.scalar_one_or_none()


async def list_mappings(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    target_model_id: str | None = None, source_system: str | None = None,
) -> list[DataMapping]:
    stmt = select(DataMapping).order_by(DataMapping.created_at.desc()).limit(limit).offset(offset)
    if target_model_id:
        stmt = stmt.where(DataMapping.target_model_id == target_model_id)
    if source_system:
        stmt = stmt.where(DataMapping.source_system == source_system)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_mappings(
    session: AsyncSession, target_model_id: str | None = None,
    source_system: str | None = None,
) -> int:
    stmt = select(func.count(DataMapping.id))
    if target_model_id:
        stmt = stmt.where(DataMapping.target_model_id == target_model_id)
    if source_system:
        stmt = stmt.where(DataMapping.source_system == source_system)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_mapping(session: AsyncSession, mapping: DataMapping) -> DataMapping:
    session.add(mapping)
    await session.commit()
    await session.refresh(mapping)
    return mapping


# ── 质量规则 ──
async def get_rule(session: AsyncSession, rule_id: str) -> MDMQualityRule | None:
    result = await session.execute(select(MDMQualityRule).where(MDMQualityRule.id == rule_id))
    return result.scalar_one_or_none()


async def list_rules(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    model_id: str | None = None, status: str | None = None,
) -> list[MDMQualityRule]:
    stmt = select(MDMQualityRule).order_by(MDMQualityRule.created_at.desc()).limit(limit).offset(offset)
    if model_id:
        stmt = stmt.where(MDMQualityRule.model_id == model_id)
    if status:
        stmt = stmt.where(MDMQualityRule.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_rules(
    session: AsyncSession, model_id: str | None = None,
    status: str | None = None,
) -> int:
    stmt = select(func.count(MDMQualityRule.id))
    if model_id:
        stmt = stmt.where(MDMQualityRule.model_id == model_id)
    if status:
        stmt = stmt.where(MDMQualityRule.status == status)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_rule(session: AsyncSession, rule: MDMQualityRule) -> MDMQualityRule:
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule
