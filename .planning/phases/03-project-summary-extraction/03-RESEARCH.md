# Phase 3: Project Summary Extraction - Research

**Researched:** 2026-02-19
**Domain:** LLM-powered structured extraction, citation verification, confidence scoring, Gemini API integration
**Confidence:** HIGH

## Summary

Phase 3 implements the core value proposition of BidOps AI: extracting structured project summaries from tender documents with citation-backed evidence and confidence indicators. The phase builds on Phase 2's hybrid search infrastructure (ChromaDB + BM25 + RRF fusion) to retrieve relevant document chunks per extraction field, then uses Gemini Pro for structured extraction with Pydantic-validated output schemas.

The critical technical challenge is citation hallucination -- research shows 17-33% hallucination rates in legal RAG systems (Stanford study). The recommended mitigation is a three-layer approach: (1) extractive prompting that instructs the LLM to copy exact quotes rather than paraphrase, (2) structured output enforcement via Pydantic schemas that require citation data for every extracted field, and (3) a separate citation verification step using a lightweight NLI (Natural Language Inference) cross-encoder model that checks whether each cited source passage actually entails the extracted claim. This verification is independent of the LLM that generated the extraction, avoiding self-verification bias.

The approach uses `google-genai` SDK (v1.64.0) with native Pydantic structured output support via `response_json_schema`, combined with the `instructor` library (v1.14.5) for automatic retry-on-validation-failure. The existing `HybridSearchService` from Phase 2 provides per-field context retrieval. Confidence scoring combines three signals: retrieval score (how relevant were the source chunks), extraction confidence (LLM self-reported), and citation verification score (NLI entailment probability). Fields falling below a configurable threshold are flagged for human review.

**Primary recommendation:** Build a three-plan pipeline: (1) LLM service wrapping google-genai with instructor for structured extraction with retries, (2) per-field retrieval-then-extract pipeline producing Pydantic-validated `ProjectSummary` with embedded citations, and (3) a separate citation verification service using `cross-encoder/nli-deberta-v3-xsmall` that validates each citation's source text entails the extracted value, producing calibrated confidence scores with high/medium/low thresholds.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SUM-01 | User receives extracted project name, owner, and location | Per-field retrieval from hybrid search using field-specific query hints (e.g., "project name", "owner", "employer", "location", "site address"). Gemini Pro structured extraction with Pydantic schema enforcing these fields. Field definitions with query_hints already partially exist in bidops-ai prompts/project_summary.py. |
| SUM-02 | User receives key dates (submission deadline, validity, pre-bid meeting) | Date fields extracted with dedicated query hints (e.g., "submission deadline", "closing date", "site visit date", "clarification deadline"). Date parsing handles multiple formats (DD/MM/YYYY, YYYY-MM-DD, Hijri). Existing ExtractionService has _parse_date_field() logic to reuse. |
| SUM-03 | User receives scope of work summary | Scope is typically in ITT/tender invitation sections. Hybrid search retrieves relevant chunks; LLM produces a concise scope summary. Longer field requiring multi-chunk context assembly. |
| SUM-04 | User receives contract type (lump sum, remeasured, etc.) | Enum-constrained extraction field. Pydantic schema uses Literal type or enum for valid contract types. Query hints: "contract type", "lump sum", "remeasured", "unit rate". |
| SUM-05 | User receives financial terms (tender bond, advance %, retention %, payment terms) | Multiple sub-fields requiring individual per-field retrieval. Numeric validation via Pydantic (percentage ranges, currency amounts). Query hints: "tender bond", "advance payment", "retention", "payment terms". |
| SUM-06 | User receives stakeholder list (consultants, PMC, designer) | List-type extraction field. Pydantic schema uses List[str] or List[Stakeholder]. Query hints: "consultant", "PMC", "project management", "designer", "engineer". |
| CIT-01 | Every extracted value links to source document and page number | SearchResult from HybridSearchService already carries document_id, page_number, and filename. These are passed to the LLM as labeled context ("[SOURCE:filename PAGE:N]") and required in the output schema. Citation object stores document name + page number. |
| CIT-02 | User can see exact quote from source document for each extraction | Extractive prompting instructs LLM to copy verbatim quotes from source chunks. Pydantic schema requires `quote: str` field in each citation. NLI verification validates the quote exists in and is entailed by the source text. Character offsets from DocumentChunk enable source text lookup. |
| CIT-03 | System assigns confidence scores (high/medium/low) to each extraction | Three-signal confidence: retrieval relevance score (from search), LLM self-reported confidence (0.0-1.0), and NLI entailment score (verified by cross-encoder). Combined score mapped to high (>= 0.8) / medium (0.5-0.8) / low (< 0.5). Thresholds configurable in Settings. |
| CIT-04 | System flags low-confidence items for human review | Pydantic schema includes `requires_review: bool` field computed from confidence threshold. Settings already has CONFIDENCE_THRESHOLD (0.7) and REVIEW_THRESHOLD (0.5) in bidops-ai config. Items below review threshold flagged automatically. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | 1.64.0 | Gemini API SDK | Official Google SDK (replaces deprecated google-generativeai). Native Pydantic structured output via `response_json_schema` + `response_mime_type="application/json"`. Supports Gemini 3 Pro/Flash. User-locked decision. |
| instructor | 1.14.5 | Structured output with retries | 3M+ monthly downloads. Wraps google-genai client with automatic Pydantic validation, retry-on-validation-failure (max_retries), and response_model parameter. Eliminates manual JSON parsing and cleanup. |
| cross-encoder/nli-deberta-v3-xsmall | - | NLI citation verification | Lightweight DeBERTa cross-encoder (~22MB) trained on SNLI+MultiNLI. Outputs entailment/contradiction/neutral scores for premise-hypothesis pairs. Used to verify citations independently from LLM. Runs locally via sentence-transformers (already installed). |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sentence-transformers | (already installed) | Load NLI cross-encoder model | CrossEncoder class loads nli-deberta-v3-xsmall for citation verification. Already in requirements from Phase 2. |
| tenacity | 8.x | Retry logic for API calls | Exponential backoff for Gemini API rate limits and transient failures. Standard retry pattern for external API calls. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| instructor + google-genai | Native google-genai response_json_schema only | Simpler (no instructor dependency), but no automatic retry-on-validation-failure. Manual JSON parsing needed for error recovery. Instructor adds ~100KB dependency but saves significant error handling code. **Recommendation: Use instructor for robustness.** |
| instructor + google-genai | pydantic-ai framework | Full agent framework by Pydantic team. More opinionated, adds larger dependency tree. Overkill for structured extraction without agentic workflows. Consider for Phase 4+ if agent patterns needed. |
| cross-encoder/nli-deberta-v3-xsmall | cross-encoder/nli-deberta-v3-base | Higher accuracy (~86% vs ~83% on MNLI) but 4x larger model (~180MB vs ~22MB). xsmall is sufficient for binary entailment checking (does source support claim?). Use base if xsmall accuracy proves insufficient on tender domain. |
| cross-encoder NLI verification | LLM-based self-verification | Using Gemini to verify its own citations is self-verification bias. Research (FACTUM paper) shows hallucination occurs in Feed-Forward pathways; same model will make same errors verifying. Independent NLI model breaks this cycle. **Never use self-verification.** |
| cross-encoder NLI verification | Fuzzy string matching only | Simple substring/fuzzy match catches exact-copy citations but misses paraphrased or partial citations. NLI understands semantic entailment. Use fuzzy matching as first-pass filter, NLI for semantic verification. |
| Per-field retrieval | Full-document-to-LLM | Sending entire documents exceeds context window, triggers "lost in the middle" degradation. Per-field retrieval keeps context focused (~2000-4000 tokens per field). Research shows staying under 80% of practical context limit is critical. |

**Installation:**
```bash
pip install google-genai instructor tenacity
```

Note: `sentence-transformers` and `chromadb` already installed from Phase 2. The NLI cross-encoder model (~22MB) downloads automatically on first use via sentence-transformers.

## Architecture Patterns

### Recommended Project Structure

New files for Phase 3 (within existing `app/` directory):

```
app/
├── services/
│   ├── llm/                        # NEW: LLM integration layer
│   │   ├── __init__.py
│   │   ├── gemini_service.py       # google-genai + instructor wrapper
│   │   └── context_builder.py      # Assemble retrieval context for prompts
│   ├── extraction/                 # NEW: Extraction pipeline
│   │   ├── __init__.py
│   │   ├── extraction_service.py   # Orchestrates per-field extract
│   │   ├── field_definitions.py    # Field schemas with query hints
│   │   └── citation_verifier.py   # NLI-based citation verification
│   ├── search/                     # EXISTING (Phase 2)
│   │   ├── hybrid_search.py        # Used by extraction pipeline
│   │   └── ...
│   └── indexing/                   # EXISTING (Phase 2)
│       ├── embedding_service.py    # Used for collection access
│       └── ...
├── schemas/
│   ├── extraction.py               # NEW: Pydantic output schemas
│   └── search.py                   # EXISTING
├── models/
│   ├── project.py                  # MODIFY: Add summary_json column
│   └── ...
├── api/
│   ├── extraction.py               # NEW: POST /api/projects/{id}/extract
│   └── ...
└── config.py                       # MODIFY: Add Gemini API key settings
```

### Pattern 1: Per-Field Retrieval-Then-Extract

**What:** For each extraction field (project_name, owner, dates, etc.), issue a targeted hybrid search query, assemble the top-k chunks as context, then extract that specific field using the LLM with a structured output schema.

**When to use:** Always for project summary extraction. This ensures each field gets the most relevant context, avoids context window overflow, and enables per-field confidence scoring.

**Why not extract all fields at once:** A single mega-prompt with all fields (a) requires more context (risk of exceeding window), (b) produces lower per-field accuracy (diluted attention), (c) makes it impossible to assign per-field citations, and (d) any single extraction failure causes total failure.

**Example:**

```python
from app.services.search.hybrid_search import HybridSearchService, SearchResult
from app.schemas.extraction import ExtractedField, Citation
from app.services.llm.gemini_service import GeminiService

class ExtractionService:
    def __init__(
        self,
        search_service: HybridSearchService,
        llm_service: GeminiService,
        citation_verifier: CitationVerifier,
    ):
        self._search = search_service
        self._llm = llm_service
        self._verifier = citation_verifier

    async def extract_project_summary(
        self, project_id: int
    ) -> ProjectSummary:
        results = {}
        for field_def in FIELD_DEFINITIONS:
            # 1. Retrieve relevant chunks for this field
            chunks = self._search.search(
                project_id=project_id,
                query=field_def.query,
                top_k=field_def.top_k,
                mode="hybrid",
            )

            # 2. Build labeled context from chunks
            context = self._build_context(chunks)

            # 3. Extract field with structured output
            extracted = await self._llm.extract_field(
                field_def=field_def,
                context=context,
            )

            # 4. Verify citations independently
            verified = self._verifier.verify_citations(
                extracted=extracted,
                source_chunks=chunks,
            )

            results[field_def.name] = verified

        return ProjectSummary(**results)
```

### Pattern 2: Labeled Context Assembly

**What:** Format retrieved chunks with explicit source labels so the LLM can reference them in citations. Each chunk is tagged with `[SOURCE:filename | PAGE:N]` prefix.

**When to use:** Always when building LLM context from retrieved chunks.

**Why:** The LLM needs unambiguous source identifiers to produce accurate citations. Without labels, it cannot attribute extractions to specific documents/pages.

**Example:**

```python
def build_labeled_context(chunks: list[SearchResult]) -> str:
    """Build context string with labeled source chunks.

    Each chunk is prefixed with source metadata that the LLM
    can reference in citation output.
    """
    parts = []
    for i, chunk in enumerate(chunks):
        label = f"[SOURCE:{chunk.filename} | PAGE:{chunk.page_number}]"
        parts.append(f"{label}\n{chunk.text}")
    return "\n\n---\n\n".join(parts)
```

### Pattern 3: Pydantic Schema for Structured Extraction

**What:** Define Pydantic models that enforce the LLM output structure, including nested citation objects with required fields.

**When to use:** For every LLM extraction call. The schema is both the instruction to the LLM (via response_json_schema) and the validation layer for the response.

**Example:**

```python
from pydantic import BaseModel, Field
from typing import Literal

class Citation(BaseModel):
    """A citation linking an extracted value to its source."""
    document_name: str = Field(
        description="Filename of the source document"
    )
    page_number: int = Field(
        description="1-based page number where the value was found"
    )
    quote: str = Field(
        description="Exact verbatim quote from the source supporting this value"
    )

class ExtractedField(BaseModel):
    """A single extracted field with citation and confidence."""
    value: str | None = Field(
        description="The extracted value, or null if not found"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score from 0.0 to 1.0"
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source citations supporting this extraction"
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of how the value was determined"
    )

class ProjectSummary(BaseModel):
    """Complete project summary with all extracted fields."""
    project_name: ExtractedField
    project_owner: ExtractedField
    location: ExtractedField
    submission_deadline: ExtractedField
    bid_validity_period: ExtractedField
    pre_bid_meeting_date: ExtractedField
    scope_of_work: ExtractedField
    contract_type: ExtractedField
    tender_bond: ExtractedField
    advance_payment: ExtractedField
    retention_percentage: ExtractedField
    payment_terms: ExtractedField
    stakeholders: ExtractedField
```

### Pattern 4: Instructor-Wrapped Gemini Service

**What:** Use instructor library to patch the google-genai client, adding automatic Pydantic validation and retry-on-failure.

**When to use:** For all structured extraction LLM calls. Instructor handles JSON parsing, validation, and retries transparently.

**Example:**

```python
import instructor
from google import genai
from pydantic import BaseModel

class GeminiService:
    """Gemini LLM service with structured output via instructor."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        self._client = instructor.from_provider(
            f"google/{model}",
            api_key=api_key,
        )
        self._model = model

    async def extract_field(
        self,
        field_def: FieldDefinition,
        context: str,
    ) -> ExtractedField:
        """Extract a single field with structured output."""
        prompt = self._build_prompt(field_def, context)

        response = self._client.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=ExtractedField,
            max_retries=3,
        )
        return response

    def _build_prompt(
        self, field_def: FieldDefinition, context: str
    ) -> str:
        return f"""Extract the following field from the tender documents.

FIELD: {field_def.name}
DESCRIPTION: {field_def.description}
EXPECTED TYPE: {field_def.field_type}

INSTRUCTIONS:
1. Find the {field_def.name} in the provided document excerpts.
2. Copy the EXACT value as it appears in the source.
3. For the quote field, copy the EXACT sentence(s) containing this value.
4. If the value is not found, set value to null and confidence to 0.0.
5. NEVER fabricate or infer values not explicitly stated in the documents.

DOCUMENT EXCERPTS:
{context}"""
```

### Pattern 5: NLI Citation Verification (Separate from Generation)

**What:** After the LLM extracts a value with citations, independently verify each citation using a cross-encoder NLI model that checks whether the cited source text entails the extracted claim.

**When to use:** For every extracted field. This is the critical defense against citation hallucination.

**Why separate:** Research (FACTUM paper, Stanford Legal RAG study) shows LLMs hallucinate citations due to "coordination failure between Attention and Feed-Forward pathways." Using the same LLM to verify its own citations does NOT catch these failures. An independent NLI model breaks the self-verification cycle.

**Example:**

```python
from sentence_transformers import CrossEncoder

class CitationVerifier:
    """Verifies citations using NLI cross-encoder model."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-xsmall"):
        self._model = None
        self._model_name = model_name

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self._model_name)
        return self._model

    def verify_citation(
        self,
        claim: str,
        source_text: str,
    ) -> float:
        """Check if source_text entails the claim.

        Returns entailment probability (0.0-1.0).
        Labels: [contradiction, entailment, neutral]
        """
        model = self._get_model()
        scores = model.predict([(source_text, claim)])
        # scores shape: (1, 3) for [contradiction, entailment, neutral]
        entailment_score = float(scores[0][1])
        return entailment_score

    def verify_extracted_field(
        self,
        field: ExtractedField,
        source_chunks: list[SearchResult],
    ) -> ExtractedField:
        """Verify all citations for an extracted field."""
        if not field.value or not field.citations:
            field.confidence = 0.0
            return field

        verified_citations = []
        for citation in field.citations:
            # Find the matching source chunk
            source = self._find_source_chunk(
                citation, source_chunks
            )
            if source is None:
                continue  # Citation references non-existent source

            # Build claim from extracted value + quote
            claim = f"The {field.value}"
            entailment = self.verify_citation(
                claim=citation.quote,
                source_text=source.text,
            )

            if entailment >= 0.5:  # Passes entailment threshold
                verified_citations.append(citation)

        field.citations = verified_citations
        # Recalculate confidence based on verification
        if verified_citations:
            field.confidence = min(field.confidence, max(
                self.verify_citation(c.quote, ...) for c in verified_citations
            ))
        else:
            field.confidence = max(0.1, field.confidence * 0.3)

        return field
```

### Anti-Patterns to Avoid

- **Self-verification (LLM verifying its own citations):** The same model that hallucinated a citation will confirm it when asked to verify. Always use an independent verification model.
- **Full-document-to-LLM extraction:** Sending entire documents instead of retrieved chunks exceeds context limits and triggers "lost in the middle" degradation. Always use per-field retrieval.
- **Single mega-prompt for all fields:** Extracting all fields in one call dilutes attention, prevents per-field citation, and causes total failure if any field extraction fails.
- **Trusting LLM confidence scores at face value:** Research shows LLM verbal confidence is poorly calibrated (ECE > 0.4). Always combine with independent signals (retrieval score, NLI score).
- **Paraphrased citations:** Instructing the LLM to "summarize" the source text for citations. Always require exact verbatim quotes. Paraphrased text cannot be verified against source.
- **Skipping Pydantic validation:** Using raw JSON parsing without schema validation. The LLM may return structurally valid JSON that violates field constraints (e.g., confidence > 1.0, missing required fields).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output with retries | Custom JSON parsing + retry loop | instructor library | Handles validation, retries, JSON cleanup, schema enforcement. Proven at 3M+ monthly downloads. Eliminates ~200 lines of error-handling code. |
| NLI entailment checking | Custom text similarity scoring | cross-encoder/nli-deberta-v3-xsmall | Trained on SNLI+MultiNLI, understands semantic entailment. Custom similarity (cosine, fuzzy) misses paraphrase and negation patterns. |
| Gemini API integration | Custom HTTP client for Gemini REST API | google-genai SDK | Official SDK handles auth, retries, streaming, model selection, structured output. Custom client would miss edge cases. |
| Date format parsing | Custom regex-based date parser | dateutil.parser + manual Hijri handling | dateutil handles dozens of date formats. Only add custom Hijri conversion on top. |

**Key insight:** The extraction pipeline's value comes from orchestrating well-tested components (search, LLM, NLI), not from building custom versions of any individual component. Focus engineering effort on the glue: field definitions, context assembly, and confidence calibration.

## Common Pitfalls

### Pitfall 1: Citation Hallucination (17-33% Rate)

**What goes wrong:** LLM generates plausible citations that reference real documents but the cited text doesn't actually support the extracted value. The LLM "coordinates" a citation from a real source to a value it recalled from training data.
**Why it happens:** "Coordination failure between Attention (reading) and Feed-Forward Network (recalling) pathways" in transformer architecture (FACTUM paper). The LLM sees source documents and generates seemingly grounded output, but the FFN pathway overwrites retrieved information.
**How to avoid:**
- NEVER rely on LLM self-verification. Always use independent NLI model.
- Require exact verbatim quotes in citations (extractive, not generative).
- Verify each citation against source chunk text using entailment scoring.
- Flag citations where NLI entailment score < 0.5 for human review.
- Test with adversarial cases where correct answer is NOT in the documents.
**Warning signs:** High extraction "accuracy" but low citation verification rate. Users reporting citations that don't match when they check the source document.

### Pitfall 2: Context Window Degradation ("Lost in the Middle")

**What goes wrong:** When too many chunks are assembled as context, information in the middle is missed. Extraction accuracy drops on fields whose relevant text lands in the middle of the context.
**Why it happens:** Attention mechanism favors tokens at the beginning and end of context. "Models become unreliable around 130K tokens with sudden performance drops."
**How to avoid:**
- Per-field retrieval limits context to top-k relevant chunks (typically 5-10 chunks, ~2000-4000 tokens per field).
- Place the most relevant chunk first in context assembly (chunks sorted by search score).
- Stay under 80% of practical context limit.
- Monitor token count per extraction call.
**Warning signs:** Fields that should be found are returning null. Accuracy varies based on which chunks happen to be retrieved.

### Pitfall 3: Pydantic Nested Model Limitation with google-genai

**What goes wrong:** Passing deeply nested Pydantic models to google-genai `response_json_schema` fails because the SDK's automatic schema conversion doesn't resolve `$ref` references in nested models.
**Why it happens:** Known issue (googleapis/python-genai#60). The SDK converts Pydantic models to JSON Schema but doesn't flatten `$ref` references for nested models.
**How to avoid:**
- Use `Model.model_json_schema()` and manually resolve `$ref` references, OR
- Use instructor library which handles this automatically, OR
- Define flat extraction schemas (ExtractedField with Citation list) rather than deeply nested hierarchies.
**Warning signs:** API errors about invalid schema. "Schema validation failed" responses.

### Pitfall 4: Gemini API Rate Limits on Per-Field Extraction

**What goes wrong:** Extracting 15+ fields with individual LLM calls (one per field) hits Gemini API rate limits, causing failures or significant latency.
**Why it happens:** Free tier has low RPM (requests per minute) limits. Even paid tiers may throttle during bursts.
**How to avoid:**
- Group related fields into extraction batches (e.g., all identification fields together, all date fields together, all financial fields together) -- 3-5 batches instead of 15+ individual calls.
- Add exponential backoff with tenacity for rate limit retries.
- Cache extraction results per project to avoid re-extraction.
- Add configurable delay between LLM calls if needed.
**Warning signs:** HTTP 429 errors. Extraction taking > 2 minutes due to retries.

### Pitfall 5: Incorrect Confidence Score Calibration

**What goes wrong:** Confidence scores are not meaningful to users. "High confidence" extractions turn out wrong, or "low confidence" extractions are actually correct. Users lose trust.
**Why it happens:** LLM verbal confidence is poorly calibrated (ECE > 0.4). Using only LLM self-reported confidence produces unreliable scores.
**How to avoid:**
- Combine three independent signals: (1) retrieval score from hybrid search, (2) LLM self-reported confidence, (3) NLI entailment score.
- Use conservative thresholds: high >= 0.8, medium 0.5-0.8, low < 0.5.
- When any signal is low, the overall confidence should be low (min aggregation for safety-critical extractions).
- Calibrate thresholds against real tender documents before production.
**Warning signs:** High false-positive rate (users frequently disagreeing with "high confidence" extractions).

## Code Examples

### Example 1: Field Definition Schema

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class FieldDefinition:
    """Definition of an extraction field with retrieval hints."""
    name: str
    description: str
    field_type: Literal["text", "date", "number", "currency", "list", "enum"]
    query: str  # Primary search query for retrieval
    query_hints: list[str] = field(default_factory=list)  # Additional search terms
    top_k: int = 5  # Number of chunks to retrieve
    required: bool = True
    enum_values: list[str] | None = None  # For enum fields
    examples: list[str] | None = None  # Example values

# Project summary field definitions
SUMMARY_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="project_name",
        description="Official name or title of the construction project",
        field_type="text",
        query="project name title tender",
        query_hints=["project name", "tender for", "project title"],
        top_k=5,
    ),
    FieldDefinition(
        name="project_owner",
        description="Client or entity issuing the tender (employer/owner)",
        field_type="text",
        query="project owner client employer authority",
        query_hints=["owner", "client", "employer", "authority", "issued by"],
        top_k=5,
    ),
    FieldDefinition(
        name="location",
        description="Geographic location or site address of the project",
        field_type="text",
        query="project location site address area city",
        query_hints=["location", "site", "address", "located at", "project site"],
        top_k=3,
    ),
    FieldDefinition(
        name="submission_deadline",
        description="Final date and time for tender submission",
        field_type="date",
        query="submission deadline closing date due date",
        query_hints=["deadline", "submission date", "due date", "closing date", "last date"],
        top_k=5,
    ),
    FieldDefinition(
        name="bid_validity_period",
        description="Period for which the bid must remain valid",
        field_type="text",
        query="bid validity period tender validity",
        query_hints=["validity", "valid for", "bid validity"],
        top_k=3,
    ),
    FieldDefinition(
        name="pre_bid_meeting_date",
        description="Date and details of pre-bid meeting or site visit",
        field_type="date",
        query="pre-bid meeting site visit mandatory site inspection",
        query_hints=["pre-bid", "site visit", "meeting", "inspection"],
        top_k=3,
    ),
    FieldDefinition(
        name="scope_of_work",
        description="Summary of the works included in the tender",
        field_type="text",
        query="scope of work description of works project scope",
        query_hints=["scope", "works", "description of works", "scope of work"],
        top_k=8,  # Scope may span more chunks
    ),
    FieldDefinition(
        name="contract_type",
        description="Type of contract (lump sum, remeasured, unit rate, etc.)",
        field_type="enum",
        query="contract type lump sum remeasured unit rate",
        query_hints=["lump sum", "remeasured", "unit rate", "contract type", "type of contract"],
        enum_values=["lump_sum", "remeasured", "unit_rate", "cost_plus", "design_build", "other"],
        top_k=3,
    ),
    FieldDefinition(
        name="tender_bond",
        description="Required tender bond or bid security amount and form",
        field_type="currency",
        query="tender bond bid security bid bond guarantee",
        query_hints=["tender bond", "bid security", "bid bond", "bank guarantee"],
        top_k=3,
    ),
    FieldDefinition(
        name="advance_payment",
        description="Advance payment percentage or amount",
        field_type="text",
        query="advance payment mobilization advance",
        query_hints=["advance payment", "mobilization", "advance"],
        top_k=3,
    ),
    FieldDefinition(
        name="retention_percentage",
        description="Retention percentage held from payments",
        field_type="text",
        query="retention percentage withheld payment",
        query_hints=["retention", "withheld", "retention percentage"],
        top_k=3,
    ),
    FieldDefinition(
        name="payment_terms",
        description="Payment cycle, terms, and conditions",
        field_type="text",
        query="payment terms cycle interim payment monthly",
        query_hints=["payment terms", "interim payment", "monthly payment", "payment cycle"],
        top_k=5,
    ),
    FieldDefinition(
        name="stakeholders",
        description="List of stakeholders: consultants, PMC, designer, engineer",
        field_type="list",
        query="consultant PMC project management designer engineer",
        query_hints=["consultant", "PMC", "project management", "designer", "engineer", "supervisor"],
        top_k=5,
    ),
]
```

### Example 2: Instructor + google-genai Integration

```python
import instructor
from google import genai
from pydantic import BaseModel, Field

class GeminiService:
    """Gemini LLM service with instructor for structured extraction."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        """Lazy-initialize instructor-patched client."""
        if self._client is None:
            self._client = instructor.from_provider(
                f"google/{self._model}",
                api_key=self._api_key,
            )
        return self._client

    def extract_field(
        self,
        prompt: str,
        response_model: type[BaseModel],
        max_retries: int = 3,
    ) -> BaseModel:
        """Extract structured data from prompt.

        instructor handles:
        - Pydantic schema -> JSON schema conversion
        - Response parsing and validation
        - Automatic retry on validation failure
        """
        client = self._get_client()
        return client.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=response_model,
            max_retries=max_retries,
        )
```

### Example 3: Confidence Score Calculation

```python
def calculate_confidence(
    llm_confidence: float,
    retrieval_score: float,
    nli_entailment_score: float,
    has_verified_citation: bool,
) -> tuple[float, str]:
    """Calculate combined confidence from three independent signals.

    Args:
        llm_confidence: LLM self-reported confidence (0.0-1.0).
        retrieval_score: Best retrieval score from hybrid search (0.0-1.0).
        nli_entailment_score: NLI entailment probability (0.0-1.0).
        has_verified_citation: Whether at least one citation passed NLI.

    Returns:
        Tuple of (score, level) where level is "high"/"medium"/"low".
    """
    if not has_verified_citation:
        # No verified citation -> cap at low confidence
        score = min(0.3, llm_confidence * 0.3)
        return score, "low"

    # Weighted combination: NLI most important, then retrieval, then LLM
    score = (
        nli_entailment_score * 0.5    # NLI verification (most reliable)
        + retrieval_score * 0.3        # Retrieval relevance
        + llm_confidence * 0.2         # LLM self-report (least reliable)
    )

    if score >= 0.8:
        return score, "high"
    elif score >= 0.5:
        return score, "medium"
    else:
        return score, "low"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| google-generativeai SDK | google-genai SDK | 2025 (GA) | Old SDK deprecated. New unified SDK supports both Gemini Developer API and Vertex AI. Must use `google-genai`, not `google-generativeai`. |
| JSON mode + manual parsing | response_json_schema + Pydantic | 2025 | Native structured output support. No more regex/cleanup of JSON from LLM responses. |
| LLM self-verification of citations | Independent NLI verification | 2025 (VeriCite, FACTUM) | Research proved self-verification doesn't catch hallucinations. Separate verification model required. |
| Single-pass full-document extraction | Per-field retrieval-then-extract | 2024-2025 | Context window degradation research showed focused retrieval outperforms full-document processing. |
| langchain-google-genai | google-genai direct (or instructor) | 2025 | LangChain's Google integration now wraps google-genai internally. Using google-genai directly (or via instructor) reduces dependency chain. |

**Deprecated/outdated:**
- `google-generativeai` package: Replaced by `google-genai`. Do not install.
- `langchain-google-genai` pre-4.0: Older versions used deprecated SDK internally. Version 4.0.0 consolidates on google-genai.
- ChatGoogleGenerativeAI from langchain: Still works but adds unnecessary LangChain dependency for structured extraction. Use instructor + google-genai directly.

## Integration Points with Existing Code

### Phase 2 Services (Dependencies)

| Existing Service | Location | How Phase 3 Uses It |
|-----------------|----------|---------------------|
| `HybridSearchService` | `app/services/search/hybrid_search.py` | Per-field retrieval. Call `search(project_id, query, top_k, mode="hybrid")` to get relevant chunks for each extraction field. Returns `SearchResult` with text, document_id, page_number, filename. |
| `EmbeddingService` | `app/services/indexing/embedding_service.py` | Needed to initialize HybridSearchService. Also provides `get_collection(project_id)` for direct ChromaDB access if needed. |
| `SearchResult` dataclass | `app/services/search/hybrid_search.py` | Each result has: chunk_id, text, score, document_id, page_number, language, filename, chunk_type, section_name. All citation metadata comes from here. |

### Existing Models (Modifications Needed)

| Model | Location | Modification |
|-------|----------|--------------|
| `Project` | `app/models/project.py` | Add `summary_json: Mapped[str \| None]` column (Text) to store the extracted ProjectSummary as JSON. Add `extraction_status: Mapped[str]` column for tracking extraction progress. |
| `Settings` | `app/config.py` | Add `gemini_api_key: str`, `gemini_model: str = "gemini-2.5-pro"`, `nli_model: str = "cross-encoder/nli-deberta-v3-xsmall"`, confidence thresholds. |

### Existing bidops-ai Code (Reference, Do Not Import)

The `bidops-ai/backend/` directory contains an older codebase with partially implemented extraction. Key observations:
- `bidops-ai/backend/app/services/llm_service.py` uses LangChain's ChatGoogleGenerativeAI. Phase 3 should use google-genai + instructor directly instead (simpler, more control).
- `bidops-ai/backend/app/prompts/project_summary.py` has useful field definitions and prompt structure to reference, but the prompt pattern needs updating for extractive citation approach.
- `bidops-ai/backend/app/services/extraction_service.py` sends full document text to LLM (anti-pattern). Phase 3 uses per-field retrieval instead.
- `bidops-ai/backend/app/config.py` has `CONFIDENCE_THRESHOLD` and `REVIEW_THRESHOLD` settings to reuse.

## Open Questions

1. **Field batching granularity**
   - What we know: Per-field extraction gives best citation accuracy but costs more API calls. Full-document extraction is cheaper but less accurate.
   - What's unclear: Optimal batch size -- should we group identification fields (name, owner, location) into one call, or keep strictly per-field?
   - Recommendation: Start with 4-5 batches grouped by category (identification, dates, scope, financial, stakeholders). Measure accuracy, then split further if any batch shows low accuracy. This balances API costs (~5 calls) with citation precision.

2. **Arabic-specific extraction prompts**
   - What we know: Tender documents may be in Arabic, English, or mixed. The LLM (Gemini) handles Arabic natively.
   - What's unclear: Whether the same extraction prompt works equally well for Arabic-language tenders, or if Arabic-specific query hints and prompt templates are needed.
   - Recommendation: Start with bilingual prompts (English instructions + Arabic field name variants in query_hints). Test with Arabic tenders early. Add dedicated Arabic prompt templates only if accuracy is measurably lower.

3. **NLI model performance on construction domain**
   - What we know: cross-encoder/nli-deberta-v3-xsmall is trained on general NLI benchmarks (SNLI, MultiNLI). Construction tender language is domain-specific.
   - What's unclear: Whether the xsmall model maintains adequate entailment accuracy on construction-specific text (e.g., "The retention percentage shall be 10% of each interim payment certificate").
   - Recommendation: Test with representative construction tender text pairs. If accuracy < 80% on domain-specific citations, upgrade to nli-deberta-v3-base (4x larger but still local). Do NOT switch to LLM-based verification.

4. **Extraction result storage format**
   - What we know: Need to store ProjectSummary with citations in the Project model.
   - What's unclear: Whether to use a JSON column (simple, flexible) or normalize into separate tables (citations table, extracted_fields table).
   - Recommendation: Use JSON column for v1 (single-user, simpler queries). The ProjectSummary Pydantic model serializes cleanly to JSON. Normalize into tables only if query patterns require it (e.g., "show all low-confidence fields across projects").

## Sources

### Primary (HIGH confidence)

- [google-genai 1.64.0 on PyPI](https://pypi.org/project/google-genai/) - Latest version confirmed Feb 19, 2026. Requires Python >= 3.10.
- [Gemini API Structured Outputs Documentation](https://ai.google.dev/gemini-api/docs/structured-output) - Official docs for response_json_schema + Pydantic integration. Confirmed support for Gemini 2.5 Pro/Flash and Gemini 3 Pro/Flash Preview.
- [instructor 1.14.5 on PyPI](https://pypi.org/project/instructor/) - Latest version confirmed Jan 29, 2026. 3M+ monthly downloads.
- [Instructor google-genai Integration Guide](https://python.useinstructor.com/integrations/genai/) - Official instructor docs for from_provider("google/...") pattern with validation and retries.
- [cross-encoder/nli-deberta-v3-xsmall on HuggingFace](https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall) - NLI cross-encoder model, outputs [contradiction, entailment, neutral] scores.
- [FACTUM: Citation Hallucination in RAG](https://arxiv.org/pdf/2601.05866) - Mechanistic explanation of citation hallucination (Attention vs FFN pathway coordination failure).
- [Stanford Legal RAG Hallucinations Study](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf) - 17-33% hallucination rate in legal RAG systems.

### Secondary (MEDIUM confidence)

- [VeriCite: Citation Verification Framework](https://arxiv.org/html/2510.11394v1) - Three-stage citation verification: generate, select evidence, refine. Uses TRUE NLI model. Published Oct 2025.
- [Gemini 2.0 vs Agentic RAG for Structured Extraction](https://unstructured.io/blog/gemini-2-0-vs-agentic-rag-who-wins-at-structured-information-extraction) - Comparison of extraction approaches with Gemini.
- [NAACL: Confidence Calibration for LLMs in RAG](https://arxiv.org/html/2601.11004) - Shows verbal confidence poorly calibrated (ECE > 0.4). Multiple signals needed.
- [Chroma Research: Context Rot](https://research.trychroma.com/context-rot) - Context window degradation patterns, "lost in the middle" effect.
- [googleapis/python-genai Issue #60](https://github.com/googleapis/python-genai/issues/60) - Nested Pydantic model schema resolution issue with response_schema.

### Tertiary (LOW confidence)

- [Adding Confidence Scores in RAG (Medium)](https://medium.com/@johnpaulthermadomthomas/adding-confidence-score-for-lll-results-in-rag-chain-scenarios-7ccbaf6b74b6) - Practical confidence scoring patterns (single source, needs validation).
- [Gemini API File Search Tool](https://blog.google/innovation-and-ai/technology/developers-tools/file-search-gemini-api/) - Google's managed RAG with automatic citations. Not used here (requires cloud, reduces control over verification), but worth monitoring for future.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - google-genai version confirmed on PyPI (Feb 2026), instructor integration documented in official instructor docs, cross-encoder model available on HuggingFace with sentence-transformers.
- Architecture: HIGH - Per-field retrieval pattern well-established in RAG literature. VeriCite framework provides academic backing for separate NLI verification. Integration points with Phase 2 services verified by reading actual code.
- Pitfalls: HIGH - Citation hallucination backed by multiple research papers (FACTUM, Stanford Legal RAG). Context window degradation confirmed by Chroma Research. Pydantic nested model issue confirmed by GitHub issue.

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days -- google-genai SDK and instructor update frequently but patterns are stable)
