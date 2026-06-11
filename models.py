"""
Slovoyad — Pydantic Models
Defines the structured output schema that Gemini must return,
plus API response models with versioning metadata.
"""

from pydantic import BaseModel, Field
from typing import Optional


class EvaluationScores(BaseModel):
    """Individual scores from 1 to 10."""
    originality: int = Field(ge=1, le=10, description="Авторство и Уникалност (1-10)")
    significance_locality: int = Field(ge=1, le=10, description="Значимост и Локалност (1-10)")
    quality_and_depth: int = Field(ge=1, le=10, description="Качество, Дължина и Четемост (1-10)")
    trust_and_sources: int = Field(ge=1, le=10, description="Достоверност (1-10)")
    domain_specific_score: int = Field(ge=1, le=10, description="Специфична ниша (1-10)")


class Justifications(BaseModel):
    """Explanations for key scores."""
    originality_reason: str = Field(description="Обяснение за оценката за оригиналност")
    significance_reason: str = Field(description="Обяснение за оценката за значимост и локалност")
    domain_specific_reason: str = Field(description="Как статията отговаря на специфичните критерии за този уебсайт")


class ArticleEvaluation(BaseModel):
    """The complete evaluation schema that Gemini must return."""
    domain: str = Field(description="Домейнът на оценяваната статия")
    title_scraped: str = Field(description="Заглавието на статията")
    classification: str = Field(description="Класификация: Translation / Original Report / Opinion / Summary")
    scores: EvaluationScores
    final_overall_score: float = Field(ge=1.0, le=10.0, description="Претеглена обща оценка")
    justifications: Justifications
    strengths: list[str] = Field(description="Силни страни на статията")
    weaknesses: list[str] = Field(description="Слаби страни на статията")


# --- API Response Models ---

class EvaluationResponse(BaseModel):
    """Single evaluation with version metadata."""
    evaluation: ArticleEvaluation
    version: int
    evaluated_at: str
    url: str


class VersionHistoryResponse(BaseModel):
    """Full history for a URL."""
    current: EvaluationResponse
    previous_versions: list[EvaluationResponse]
    total_versions: int
    score_evolution: list[float]


class EvaluateRequest(BaseModel):
    """Request body for the /api/evaluate endpoint."""
    url: str = Field(description="URL на статията за анализ")
    model: Optional[str] = Field(default=None, description="Gemini модел (optional override)")
