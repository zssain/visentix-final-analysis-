"""Pydantic response/request schemas for the Visentix API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    row_counts: dict[str, int | str]
    ollama: str


class OrganizationSummary(BaseModel):
    organization_id: UUID
    name: str
    industry: str
    geography: str
    entity_type: str


class FindingOut(BaseModel):
    finding_id: UUID
    finding_type_code: str
    severity: str
    score: float | None
    confidence_score: float | None
    domain: str | None
    generated_at: datetime | None


class RecommendationOut(BaseModel):
    id: UUID
    finding_type_code: str
    severity_bucket: str
    title: str
    body_template: str
    sme_authored: bool


class ReportSnapshotOut(BaseModel):
    snapshot_id: UUID
    organization_id: UUID
    created_at: datetime
