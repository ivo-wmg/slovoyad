"""
Slovoyad — Pydantic Models
Defines the structured output schema that Gemini must return,
plus API response models with versioning metadata.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List


class ArticleEvaluation(BaseModel):
    """The complete evaluation schema that Gemini must return.
    
    Field order follows Chain of Thought: reasoning first, then scores.
    This helps LLMs produce more accurate evaluations.
    """
    domain: str = Field(description="Домейнът на оценяваната статия")
    title_scraped: str = Field(description="Заглавието на статията")
    classification: str = Field(description="Класификация: Translation / Original Report / Opinion / Summary / Interview")

    # --- Reasoning FIRST, then scores (Chain of Thought) ---
    originality_reason: str = Field(description="Обяснение за оценката за оригиналност")
    originality: int = Field(ge=1, le=10, description="Авторство и Уникалност (1-10)")

    significance_reason: str = Field(description="Обяснение за оценката за значимост и локалност")
    significance_locality: int = Field(ge=1, le=10, description="Значимост и Локалност (1-10)")

    quality_reason: str = Field(description="Обяснение за оценката за качество и дълбочина")
    quality_and_depth: int = Field(ge=1, le=10, description="Качество, Дължина и Четемост (1-10)")

    trust_reason: str = Field(description="Обяснение за оценката за доверие и източници")
    trust_and_sources: int = Field(ge=1, le=10, description="Достоверност (1-10)")

    domain_specific_reason: str = Field(description="Как статията отговаря на специфичните критерии за този уебсайт")
    domain_specific_score: int = Field(ge=1, le=10, description="Специфична ниша (1-10)")

    # --- Lists ---
    strengths: List[str] = Field(description="Силни страни на статията")
    weaknesses: List[str] = Field(description="Слаби страни на статията")
    recommendations: List[str] = Field(default_factory=list, description="До 3 конкретни препоръки за подобряване на текста")

    # --- AI Detection ---
    ai_probability: int = Field(ge=0, le=100, description="Стилистични AI маркери (0-100%)")
    ai_reasoning: str = Field(description="Обяснение за наличието на AI стилистични маркери")
    spelling_errors: List[str] = Field(default_factory=list, description="Конкретни правописни грешки (макс. 5)")

    # --- Confidence ---
    confidence: int = Field(ge=0, le=100, description="Увереност на оценителя (0-100)")

    # --- Final score LAST (Chain of Thought) ---
    final_overall_score: float = Field(ge=1.0, le=10.0, description="Претеглена обща оценка")


# --- API Response Models ---

class EvaluationResponse(BaseModel):
    """Single evaluation with version metadata."""
    evaluation: ArticleEvaluation
    version: int
    evaluated_at: str
    url: str
    id: Optional[int] = None


class VersionHistoryResponse(BaseModel):
    """Full history for a URL."""
    current: EvaluationResponse
    previous_versions: List[EvaluationResponse]
    total_versions: int
    score_evolution: List[float]


class EvaluateRequest(BaseModel):
    """Request body for the /api/evaluate endpoint."""
    url: str = Field(description="URL на статията за анализ")
    model: Optional[str] = Field(default=None, description="Gemini модел (optional override)")
