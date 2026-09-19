"""主数据管理业务 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── 主数据模型 ──
class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    domain: Literal["customer", "product", "supplier", "employee"] = "customer"
    version: str = Field(default="1.0.0", max_length=32)
    description: str = Field(default="", max_length=2000)


class ModelUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    version: str | None = Field(default=None, max_length=32)


class ModelStatusUpdate(BaseModel):
    status: Literal["draft", "published", "deprecated"]


# ── 映射规则 ──
class MappingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    source_system: str = Field(min_length=1, max_length=128)
    target_model_id: str = Field(min_length=1, max_length=64)
    mapping_type: Literal["direct", "transform", "lookup"] = "direct"
    field_mapping: str = Field(default="{}", max_length=8000)


class MappingStatusUpdate(BaseModel):
    status: Literal["active", "inactive"]


# ── 质量规则 ──
class QualityRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=64)
    rule_type: Literal["not_null", "unique", "regex", "range"] = "not_null"
    expression: str = Field(min_length=1, max_length=512)
    severity: Literal["error", "warning"] = "error"


class QualityRuleStatusUpdate(BaseModel):
    status: Literal["active", "disabled"]
