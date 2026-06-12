"""
Slovoyad Article Evaluator - Gemini API client for structured article evaluation.
"""

import json
import time

import httpx
from google import genai
from google.genai import errors as genai_errors

from config import GEMINI_API_KEY, GEMINI_MODEL, SCORING_WEIGHTS
from config import get_db_config  # noqa: F401 – re-exported for convenience
from models import ArticleEvaluation
from prompts import build_evaluation_prompt, SYSTEM_INSTRUCTION
from domains import DomainConfig
from utils import logger


class ArticleEvaluator:
    """Evaluates articles using the Gemini API with structured JSON output."""

    MAX_RETRIES = 3
    BACKOFF_BASE = 2  # seconds

    def __init__(self, api_key=None, model=None):
        self.client = genai.Client(api_key=api_key or GEMINI_API_KEY)
        self.model = model or GEMINI_MODEL

    def evaluate(self, article_data: dict, domain_config: DomainConfig) -> ArticleEvaluation:
        """
        Evaluate an article and return a structured ArticleEvaluation.

        Args:
            article_data: Dictionary containing the article content and metadata.
            domain_config: Domain-specific configuration for evaluation criteria.

        Returns:
            ArticleEvaluation with recalculated final_overall_score.

        Raises:
            RuntimeError: If all retry attempts are exhausted.
        """
        prompt = build_evaluation_prompt(article_data, domain_config)

        response = self._call_with_retry(prompt)
        result = self._parse_response(response)
        result.final_overall_score = self._recalculate_score(result)

        return result

    def _call_with_retry(self, prompt: str):
        """
        Call the Gemini API with exponential backoff retry logic.

        Retries up to MAX_RETRIES times on API or network errors,
        respecting the free-tier 15 RPM limit.
        """
        last_exception = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_schema': ArticleEvaluation,
                        'system_instruction': SYSTEM_INSTRUCTION,
                    },
                )
                return response

            except (genai_errors.APIError, genai_errors.ClientError, genai_errors.ServerError) as e:
                last_exception = e
                wait = self.BACKOFF_BASE ** attempt
                logger.warning(
                    "Gemini API error on attempt %d/%d: %s. Retrying in %ds...",
                    attempt, self.MAX_RETRIES, e, wait,
                )
                time.sleep(wait)

            except httpx.HTTPError as e:
                last_exception = e
                wait = self.BACKOFF_BASE ** attempt
                logger.warning(
                    "HTTP error on attempt %d/%d: %s. Retrying in %ds...",
                    attempt, self.MAX_RETRIES, e, wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"Gemini API call failed after {self.MAX_RETRIES} attempts: {last_exception}"
        ) from last_exception

    def _parse_response(self, response) -> ArticleEvaluation:
        """
        Parse the Gemini response into an ArticleEvaluation.

        Falls back to manual JSON parsing + Pydantic validation if
        the SDK's structured parsing fails.
        """
        # Primary path: SDK structured output
        try:
            result = response.parsed
            if result is not None:
                logger.debug("Successfully parsed response via SDK structured output.")
                return result
        except Exception as e:
            logger.warning("SDK parsed output failed: %s. Falling back to manual parsing.", e)

        # Fallback: raw JSON text -> Pydantic
        try:
            raw = json.loads(response.text)
            result = ArticleEvaluation.model_validate(raw)
            logger.info("Fallback JSON parsing succeeded.")
            return result
        except (json.JSONDecodeError, Exception) as e:
            raise RuntimeError(
                f"Failed to parse Gemini response as ArticleEvaluation: {e}"
            ) from e

    @staticmethod
    def _recalculate_score(result: ArticleEvaluation) -> float:
        """
        Recalculate the final overall score using the canonical weights
        from config.SCORING_WEIGHTS.

        Weights: domain_specific=35%, originality=25%, trust=20%,
                 quality=10%, significance=10%
        """
        score = (
            result.domain_specific_score * SCORING_WEIGHTS['domain_specific_score']
            + result.originality * SCORING_WEIGHTS['originality']
            + result.trust_and_sources * SCORING_WEIGHTS['trust_and_sources']
            + result.quality_and_depth * SCORING_WEIGHTS['quality_and_depth']
            + result.significance_locality * SCORING_WEIGHTS['significance_locality']
        )
        return round(score, 2)


def evaluate_article(
    url: str,
    article_data: dict,
    domain_config: DomainConfig,
    model: str = None,
) -> ArticleEvaluation:
    """
    Module-level convenience function for one-shot article evaluation.

    Args:
        url: The article URL (informational, not fetched here).
        article_data: Dictionary containing the article content and metadata.
        domain_config: Domain-specific evaluation configuration.
        model: Optional Gemini model override.

    Returns:
        ArticleEvaluation with the final score recalculated from config weights.
    """
    evaluator = ArticleEvaluator(model=model)
    return evaluator.evaluate(article_data, domain_config)
