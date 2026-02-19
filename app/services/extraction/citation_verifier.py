"""NLI-based citation verification and confidence scoring.

Uses a cross-encoder NLI model (independent from the extraction LLM) to verify
that each cited source passage actually entails the extracted claim. This is the
critical defense against citation hallucination (17-33% rate per Stanford research).

The verifier also computes combined confidence scores from three independent
signals (retrieval, LLM, NLI) and flags low-confidence extractions for human review.

Key design decisions:
- NLI cross-encoder is an INDEPENDENT model, NOT the same LLM that generated
  the extraction. This avoids self-verification bias.
- Model loads lazily on first use to avoid startup delay.
- Softmax applied to raw logits (nli-deberta-v3-xsmall outputs logits, not probs).
- Confidence weights: NLI 50%, retrieval 30%, LLM 20% (NLI most trusted).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from sentence_transformers import CrossEncoder

if TYPE_CHECKING:
    from app.schemas.extraction import Citation, ExtractedField
    from app.services.search.hybrid_search import SearchResult

logger = logging.getLogger(__name__)


class CitationVerifier:
    """Verifies LLM-generated citations using an independent NLI cross-encoder.

    The NLI model checks whether the cited source text semantically entails
    the extracted claim. Citations that fail verification are removed.
    Confidence scores combine three independent signals: NLI entailment,
    retrieval relevance, and LLM self-reported confidence.

    Args:
        model_name: HuggingFace model ID for the NLI cross-encoder.
        confidence_high: Score threshold for "high" confidence level.
        confidence_low: Score threshold for "medium" confidence level.
            Below this is "low".
        review_threshold: Score below which requires_review is set True.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
        confidence_high: float = 0.8,
        confidence_low: float = 0.5,
        review_threshold: float = 0.5,
    ) -> None:
        self._model_name = model_name
        self._confidence_high = confidence_high
        self._confidence_low = confidence_low
        self._review_threshold = review_threshold
        self._model: CrossEncoder | None = None
        logger.info("CitationVerifier initialized with model: %s", model_name)

    def _get_model(self) -> CrossEncoder:
        """Load the NLI cross-encoder model lazily on first use.

        Returns:
            The loaded CrossEncoder model instance.
        """
        if self._model is None:
            logger.info("Loading NLI model: %s", self._model_name)
            self._model = CrossEncoder(self._model_name)
            logger.info("NLI model loaded")
        return self._model

    def verify_citation(self, claim: str, source_text: str) -> float:
        """Check if source_text entails the claim. Returns entailment probability (0.0-1.0).

        Uses the NLI cross-encoder to determine whether the source text
        semantically entails (supports) the claim. The model outputs raw
        logits for [contradiction, entailment, neutral] which are converted
        to probabilities via softmax.

        Args:
            claim: The extracted claim or quoted text to verify.
            source_text: The source passage that should entail the claim.

        Returns:
            Entailment probability between 0.0 and 1.0.
        """
        try:
            model = self._get_model()
            scores = model.predict([(source_text, claim)])
            # NLI model outputs logits for [contradiction, entailment, neutral]
            logits = scores[0]  # shape: (3,)
            # Apply softmax with numerical stability
            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / exp_logits.sum()
            entailment_prob = float(probs[1])  # index 1 = entailment
            return entailment_prob
        except Exception:
            logger.warning(
                "NLI model failed for claim verification, returning 0.0",
                exc_info=True,
            )
            return 0.0

    def _find_source_chunk(
        self, citation: Citation, source_chunks: list[SearchResult]
    ) -> SearchResult | None:
        """Find the source chunk matching a citation's document and page.

        Tries exact match on filename + page_number first, then falls back
        to filename-only match (LLM may cite wrong page number).

        Args:
            citation: The citation to find a source for.
            source_chunks: Available search result chunks to match against.

        Returns:
            The matching SearchResult, or None if no match found.
        """
        # Try exact match: filename AND page number
        for chunk in source_chunks:
            if (
                chunk.filename == citation.document_name
                and chunk.page_number == citation.page_number
            ):
                return chunk

        # Fallback: match by filename only (LLM may cite wrong page)
        for chunk in source_chunks:
            if chunk.filename == citation.document_name:
                return chunk

        # No match found -- citation references non-existent source
        return None

    def verify_field(
        self,
        field: ExtractedField,
        source_chunks: list[SearchResult],
        retrieval_scores: list[float] | None = None,
    ) -> ExtractedField:
        """Verify all citations for an extracted field using NLI and compute confidence.

        Each citation is checked against its source chunk using the NLI model.
        Citations that fail verification (entailment score < 0.3) are removed.
        The field's confidence is recalculated from three independent signals.

        Args:
            field: The extracted field with citations to verify.
            source_chunks: Search result chunks used as source context.
            retrieval_scores: Optional list of retrieval relevance scores.

        Returns:
            The field with verified citations and updated confidence.
        """
        # Handle empty/null values
        if field.value is None or field.value == "":
            field.confidence = 0.0
            field.confidence_level = "low"
            field.requires_review = True
            return field

        # Handle fields with no citations
        if not field.citations:
            field.confidence = max(0.1, field.confidence * 0.3)
            field.confidence_level = "low"
            field.requires_review = True
            return field

        # Verify each citation via NLI
        verified_citations: list[Citation] = []
        entailment_scores: list[float] = []

        for citation in field.citations:
            source = self._find_source_chunk(citation, source_chunks)
            if source is None:
                # Citation references non-existent source, skip it
                logger.debug(
                    "No source chunk found for citation: %s p%s",
                    citation.document_name,
                    citation.page_number,
                )
                continue

            # Verify entailment: does source text entail the cited quote?
            score = self.verify_citation(
                claim=citation.quote, source_text=source.text
            )

            if score >= 0.3:
                # Keep citation -- score contributes to overall confidence
                verified_citations.append(citation)
                entailment_scores.append(score)
            else:
                logger.debug(
                    "Citation failed NLI verification (score=%.3f): %s p%s",
                    score,
                    citation.document_name,
                    citation.page_number,
                )

        # Replace citations with verified-only list
        field.citations = verified_citations

        # Compute best scores for confidence calculation
        best_retrieval = max(retrieval_scores) if retrieval_scores else 0.5
        best_nli = max(entailment_scores) if entailment_scores else 0.0

        # Calculate combined confidence
        score, level, requires_review = self.calculate_confidence(
            llm_confidence=field.confidence,
            retrieval_score=best_retrieval,
            nli_entailment_score=best_nli,
            has_verified_citation=len(verified_citations) > 0,
        )

        field.confidence = score
        field.confidence_level = level
        field.requires_review = requires_review
        return field

    def calculate_confidence(
        self,
        llm_confidence: float,
        retrieval_score: float,
        nli_entailment_score: float,
        has_verified_citation: bool,
    ) -> tuple[float, str, bool]:
        """Calculate combined confidence from three independent signals.

        Weighted combination: NLI (50%) + retrieval (30%) + LLM (20%).
        NLI is weighted highest because it's the most reliable independent
        signal. Fields without any verified citations are capped at 0.3.

        Args:
            llm_confidence: LLM self-reported confidence (0.0-1.0).
            retrieval_score: Best retrieval relevance score (0.0-1.0).
            nli_entailment_score: Best NLI entailment probability (0.0-1.0).
            has_verified_citation: Whether at least one citation passed NLI.

        Returns:
            Tuple of (score, level, requires_review) where:
            - score: Combined confidence (0.0-1.0)
            - level: "high", "medium", or "low"
            - requires_review: True if score < review_threshold
        """
        if not has_verified_citation:
            score = min(0.3, llm_confidence * 0.3)
            return (score, "low", True)

        # Weighted combination: NLI most important, then retrieval, then LLM
        score = (
            nli_entailment_score * 0.5
            + retrieval_score * 0.3
            + llm_confidence * 0.2
        )

        # Determine confidence level
        if score >= self._confidence_high:
            level = "high"
        elif score >= self._confidence_low:
            level = "medium"
        else:
            level = "low"

        # Flag for review if below threshold
        requires_review = score < self._review_threshold

        return (score, level, requires_review)
