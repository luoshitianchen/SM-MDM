"""主数据管理业务模型：主数据模型、映射规则、质量规则。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class MasterDataModel(Base):
    """主数据模型：定义一类主数据的结构与版本。"""

    __tablename__ = "master_data_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(32), default="customer", index=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DataMapping(Base):
    """映射规则：源系统字段到主数据模型的映射。"""

    __tablename__ = "data_mappings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mapping_type: Mapped[str] = mapped_column(String(16), default="direct")
    field_mapping: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MDMQualityRule(Base):
    """数据质量规则：对主数据模型施加的校验约束。"""

    __tablename__ = "mdm_quality_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(16), default="not_null")
    expression: Mapped[str] = mapped_column(String(512), default="")
    severity: Mapped[str] = mapped_column(String(16), default="error")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
