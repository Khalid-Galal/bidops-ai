# Phase 4: Requirements Checklist Extraction - Research

**Researched:** 2026-02-19
**Domain:** LLM-powered multi-item extraction, requirements categorization, obligation detection from construction tender documents
**Confidence:** HIGH

## Summary

Phase 4 transforms the single-field extraction pattern from Phase 3 into a multi-item list extraction pipeline. Instead of extracting one value per field (e.g., "project_name"), this phase extracts an unbounded list of requirements from tender documents, each categorized by type (Technical, Commercial, Legal, HSE) with embedded citations and confidence scores. This is fundamentally different from Phase 3: Phase 3 answers "What is the project name?" while Phase 4 answers "What are ALL the requirements in this tender?"

The key architectural insight comes from recent extraction MVP research (Forgent AI, May 2025): Gemini 2.5 Pro is uniquely capable of extracting hundreds of requirements from full document context without chunking, achieving ~98% recall. However, since our documents are already chunked and indexed (Phase 2), and we need per-requirement citation verification (Phase 3 infrastructure), we should use a **category-based retrieval-then-extract approach** -- one extraction call per requirement category (Technical, Commercial, Legal, HSE, Submission Documents, Eligibility). This gives us 6 focused LLM calls instead of trying to extract everything at once, and naturally deduplicates since each category targets different document sections. Each call retrieves category-relevant chunks via hybrid search (more chunks than Phase 3, typically 15-20), then extracts a list of requirements with citations using instructor's `Iterable[RequirementItem]` or a wrapper model pattern.

The existing Phase 3 infrastructure (GeminiService, CitationVerifier, ExtractionService, context_builder) provides the foundation. The main new work is: (1) defining category-specific extraction schemas and field definitions, (2) adapting the extraction pipeline for list output instead of single-field output, (3) adding deduplication logic for requirements that appear across category boundaries, (4) creating new Pydantic schemas for RequirementItem and RequirementsChecklist, (5) new database storage for checklist results, and (6) new API endpoints.

**Primary recommendation:** Build a category-based extraction pipeline that makes 6 LLM calls (one per requirement category), each retrieving 15-20 relevant chunks via hybrid search, extracting a list of `RequirementItem` objects with citations using a wrapper Pydantic model, verifying citations with NLI, and assembling results into a `RequirementsChecklist`. Reuse GeminiService, CitationVerifier, and context_builder from Phase 3.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CHK-01 | System extracts technical requirements from tender documents | Category-based extraction with dedicated "Technical" query retrieving specs, standards, material requirements, testing, and workmanship clauses. Hybrid search queries target sections like "Technical Specifications", "General Requirements", "Particular Specifications". LLM extracts list of RequirementItem objects with field_type="technical". |
| CHK-02 | System extracts commercial requirements | Dedicated "Commercial" category extraction targeting pricing, payment, bonds, insurance, warranties. Hybrid search queries: "commercial terms", "pricing requirements", "insurance requirements", "warranty obligations", "performance bond". |
| CHK-03 | System extracts legal requirements | "Legal" category extraction targeting contract conditions, dispute resolution, applicable law, intellectual property, confidentiality. Queries: "conditions of contract", "applicable law", "dispute resolution", "legal obligations", "indemnity". |
| CHK-04 | System extracts HSE requirements | "HSE" category extraction targeting safety plans, environmental compliance, PPE, permits. Queries: "health safety environment", "HSE requirements", "safety plan", "environmental management", "PPE requirements". |
| CHK-05 | System categorizes requirements by type (Technical/Commercial/Legal/HSE) | Category is assigned during extraction since each LLM call targets one category. The prompt instructs the LLM to extract only requirements of that specific type. Enum field in RequirementItem schema enforces valid categories. |
| CHK-06 | System extracts mandatory submission documents list | Dedicated "Submission Documents" category extraction with specialized queries: "documents to be submitted", "submission requirements", "tender submission", "required documents", "appendices to be completed". Returns list of SubmissionDocument items with document name, description, and mandatory flag. |
| CHK-07 | System detects eligibility/pre-qualification criteria | Dedicated "Eligibility" category extraction targeting pre-qualification, experience requirements, financial standing, certifications. Queries: "eligibility criteria", "pre-qualification", "minimum experience", "financial capacity", "required certifications". Results surfaced prominently with is_eligibility=True flag. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | 1.64.0+ | Gemini API SDK | Already installed from Phase 3. Powers all LLM extraction calls. |
| instructor | 1.14.5+ | Structured list extraction with retries | Already installed from Phase 3. `create()` with wrapper model containing `list[RequirementItem]` for extracting multiple items per category. `create_iterable()` also available but wrapper model is more reliable with Gemini. |
| cross-encoder/nli-deberta-v3-xsmall | - | NLI citation verification | Already installed from Phase 3. Same CitationVerifier reused for per-requirement citation checking. |
| pydantic | 2.x | Extraction schemas | Already installed. New schemas: RequirementItem, SubmissionDocument, EligibilityCriterion, RequirementsChecklist. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sentence-transformers | (installed) | NLI cross-encoder loading | Already in place from Phase 3. |
| tenacity | 8.x | Retry logic | Already in place from Phase 3. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Category-based extraction (6 calls) | Single mega-extraction (1 call) | Single call is simpler but: (a) harder to provide focused context per category, (b) output can exceed token limits for large tenders, (c) no natural category assignment, (d) harder to debug which category failed. Category-based is better for citation accuracy and error isolation. |
| Wrapper model `ChecklistResponse(items: list[RequirementItem])` | `Iterable[RequirementItem]` via `create_iterable()` | `create_iterable()` streams items but has caveats with Gemini (streaming limitations with structured output noted in instructor docs as of July 2025). Wrapper model is simpler and more reliable. Use wrapper. |
| Per-category retrieval (hybrid search) | Full document to LLM (no retrieval) | Gemini 2.5 Pro can handle full docs (~98% recall per Forgent AI), but: (a) our docs are already chunked, (b) full doc approach bypasses citation verification infrastructure, (c) exceeds 1M token limit for large tender packages. Per-category retrieval keeps context focused. |
| 6 categories (Technical, Commercial, Legal, HSE, Submission, Eligibility) | 10 categories from old bidops-ai (adds Quality, Schedule, Bonds, Documentation) | Fewer categories reduces LLM calls and deduplication complexity. Technical covers Quality, Commercial covers Bonds, Submission covers Documentation, Schedule items split naturally across Technical/Commercial. Can expand later if needed. |

**Installation:**
```bash
# No new packages needed -- all dependencies already installed from Phase 3
```

## Architecture Patterns

### Recommended Project Structure

New and modified files for Phase 4 (within existing `app/` directory):

```
app/
├── services/
│   ├── extraction/
│   │   ├── extraction_service.py     # EXISTING (Phase 3) -- no changes needed
│   │   ├── checklist_service.py      # NEW: Orchestrates category-based checklist extraction
│   │   ├── checklist_definitions.py  # NEW: Category definitions with queries and prompts
│   │   ├── citation_verifier.py      # EXISTING (Phase 3) -- reused as-is
│   │   └── field_definitions.py      # EXISTING (Phase 3) -- no changes needed
│   ├── llm/
│   │   ├── gemini_service.py         # EXISTING (Phase 3) -- no changes needed
│   │   └── context_builder.py        # MODIFY: Add build_checklist_prompt()
│   └── search/
│       └── hybrid_search.py          # EXISTING (Phase 2) -- no changes needed
├── schemas/
│   ├── extraction.py                 # EXISTING (Phase 3) -- no changes needed
│   └── checklist.py                  # NEW: RequirementItem, SubmissionDocument, RequirementsChecklist
├── models/
│   └── project.py                    # MODIFY: Add checklist_json column, checklist_status
├── api/
│   ├── extraction.py                 # EXISTING (Phase 3) -- no changes needed
│   └── checklist.py                  # NEW: POST/GET /api/projects/{id}/checklist
└── config.py                         # MINOR: Add checklist-specific settings if needed
```

### Pattern 1: Category-Based Retrieval-Then-Extract

**What:** For each requirement category (Technical, Commercial, Legal, HSE, Submission Documents, Eligibility), issue a targeted hybrid search query with category-specific terms, retrieve 15-20 chunks, and extract a list of requirements from those chunks.

**When to use:** Always for checklist extraction. This is the core pattern.

**Why 6 categories, not 1 mega-call:**
1. Focused context per category improves extraction accuracy (less "lost in the middle").
2. Natural categorization -- category is known by which call produced it.
3. Error isolation -- if HSE extraction fails, Technical requirements are unaffected.
4. Better deduplication -- most duplicates would occur across categories, and category-focused queries reduce cross-category overlap.
5. Manageable output size per call -- a tender might have 50+ technical requirements; splitting keeps output well within token limits.

**Example:**
```python
@dataclass
class CategoryDefinition:
    """Defines a requirement category for extraction."""
    name: str                    # "technical", "commercial", "legal", "hse"
    display_name: str            # "Technical", "Commercial", etc.
    description: str             # What this category covers
    queries: list[str]           # Multiple search queries for retrieval
    top_k: int                   # Chunks to retrieve per query
    prompt_hints: str            # Category-specific extraction instructions
    mandatory_keywords: list[str]  # Words indicating mandatory requirements

CHECKLIST_CATEGORIES: list[CategoryDefinition] = [
    CategoryDefinition(
        name="technical",
        display_name="Technical",
        description="Technical specifications, standards, materials, testing, workmanship",
        queries=[
            "technical requirements specifications standards",
            "material requirements testing quality workmanship",
            "design requirements drawings calculations",
        ],
        top_k=8,
        prompt_hints="Focus on: specifications, standards (BS, ASTM, ISO), material requirements, testing/inspection, workmanship, tolerances, design criteria.",
        mandatory_keywords=["shall", "must", "required", "mandatory"],
    ),
    # ... similar for commercial, legal, hse, submission_documents, eligibility
]
```

### Pattern 2: List Extraction with Wrapper Model

**What:** Instead of extracting one field per LLM call (Phase 3 pattern), extract a list of requirements using a Pydantic wrapper model that contains `items: list[RequirementItem]`.

**When to use:** For every category extraction call. The wrapper model pattern is more reliable than `Iterable[T]` with Gemini.

**Why wrapper model over Iterable:**
- Gemini has streaming limitations with structured output (noted in instructor docs, July 2025).
- Wrapper model allows additional metadata fields (category name, extraction count, etc.).
- Instructor handles validation and retries of the entire response, not individual items.

**Example:**
```python
from pydantic import BaseModel, Field

class RequirementItem(BaseModel):
    """A single extracted requirement with citation."""
    requirement: str = Field(
        description="Clear, concise statement of the requirement"
    )
    description: str = Field(
        default="",
        description="Additional context or details about the requirement"
    )
    is_mandatory: bool = Field(
        description="True if requirement uses mandatory language (shall, must, required)"
    )
    source_document: str = Field(
        description="Filename of the source document"
    )
    page_number: int = Field(
        ge=1,
        description="Page number where the requirement was found"
    )
    quote: str = Field(
        min_length=1,
        description="Exact verbatim quote from source supporting this requirement"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Self-assessed confidence (0.0 to 1.0)"
    )

class CategoryExtractionResponse(BaseModel):
    """LLM response for one category of requirements."""
    items: list[RequirementItem] = Field(
        description="List of all requirements found for this category"
    )
    reasoning: str = Field(
        default="",
        description="Brief summary of extraction approach and findings"
    )
```

### Pattern 3: Multi-Query Retrieval per Category

**What:** Each category uses multiple search queries to maximize recall. Results are merged and deduplicated by chunk_id before being passed to the LLM.

**When to use:** Always. A single query per category misses requirements that use different terminology.

**Example:**
```python
async def _retrieve_category_chunks(
    self, project_id: int, category: CategoryDefinition
) -> list[SearchResult]:
    """Retrieve chunks for a category using multiple queries."""
    seen_chunk_ids: set[str] = set()
    all_chunks: list[SearchResult] = []

    for query in category.queries:
        results = self._search_service.search(
            project_id=project_id,
            query=query,
            top_k=category.top_k,
            mode="hybrid",
        )
        for chunk in results:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                all_chunks.append(chunk)

    # Sort by relevance score descending, take top N
    all_chunks.sort(key=lambda c: c.score, reverse=True)
    return all_chunks[:category.max_context_chunks]  # e.g., 20
```

### Pattern 4: Reuse Phase 3 Citation Verification for List Items

**What:** After extracting a list of RequirementItem objects, verify each item's citation using the same CitationVerifier from Phase 3. Each RequirementItem has a quote and source_document/page_number, which maps directly to the Citation schema.

**When to use:** Always, after every category extraction.

**Example:**
```python
def verify_requirement_citations(
    self,
    items: list[RequirementItem],
    source_chunks: list[SearchResult],
) -> list[VerifiedRequirement]:
    """Verify each requirement's citation against source chunks."""
    verified = []
    for item in items:
        # Build a Citation-compatible object
        citation = Citation(
            document_name=item.source_document,
            page_number=item.page_number,
            quote=item.quote,
        )
        # Verify using NLI
        nli_score = self._citation_verifier.verify_citation(
            claim=item.quote,
            source_text=self._find_source_text(citation, source_chunks),
        )
        # Build verified requirement with confidence
        verified.append(VerifiedRequirement(
            requirement=item.requirement,
            description=item.description,
            category=category_name,
            is_mandatory=item.is_mandatory,
            citation=citation,
            nli_score=nli_score,
            confidence=self._calculate_confidence(item, nli_score),
            confidence_level=self._confidence_level(confidence),
        ))
    return verified
```

### Pattern 5: Post-Extraction Deduplication

**What:** After extracting requirements from all categories, deduplicate items that may appear in multiple categories (e.g., "submit insurance certificates" could appear in both Commercial and Legal).

**When to use:** After all category extractions complete, before assembling the final checklist.

**Approach:** Semantic similarity deduplication using the existing embedding model (paraphrase-multilingual-mpnet-base-v2). For each pair of requirements across categories, compute cosine similarity. If similarity > 0.9, keep the one with higher confidence and note the duplicate category as a secondary tag.

**Example:**
```python
def deduplicate_requirements(
    self,
    all_requirements: list[VerifiedRequirement],
    similarity_threshold: float = 0.9,
) -> list[VerifiedRequirement]:
    """Remove near-duplicate requirements across categories."""
    if len(all_requirements) <= 1:
        return all_requirements

    # Embed all requirement texts
    texts = [r.requirement for r in all_requirements]
    embeddings = self._embedding_service.encode(texts)

    # Find duplicates via cosine similarity
    unique: list[VerifiedRequirement] = []
    duplicate_indices: set[int] = set()

    for i in range(len(all_requirements)):
        if i in duplicate_indices:
            continue
        for j in range(i + 1, len(all_requirements)):
            if j in duplicate_indices:
                continue
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim >= similarity_threshold:
                # Keep the one with higher confidence
                if all_requirements[j].confidence > all_requirements[i].confidence:
                    duplicate_indices.add(i)
                    break
                else:
                    duplicate_indices.add(j)
        if i not in duplicate_indices:
            unique.append(all_requirements[i])

    return unique
```

### Anti-Patterns to Avoid

- **Single mega-prompt for all categories:** Extracting all requirement types in one call dilutes focus, prevents category assignment, and produces lower recall. Always use category-based extraction.
- **Extracting from full documents without retrieval:** Even though Gemini 2.5 Pro can handle full docs, bypassing hybrid search means no retrieval scores for confidence calculation and no chunk-level citation verification.
- **Using `Union` types in Gemini schemas:** Gemini does not support Union types in structured output (confirmed in instructor docs). Use separate models per category or a single model with a category field.
- **Skipping deduplication:** When using multiple queries per category and multiple categories, the same requirement can surface 2-3 times. Always deduplicate before returning results.
- **Over-categorizing:** Using 10+ categories (as in old bidops-ai) increases LLM calls, deduplication complexity, and category confusion. 6 categories is the sweet spot for construction tenders.
- **Treating all requirements as equal priority:** Eligibility criteria and submission documents are disqualification risks -- they should be surfaced prominently with visual priority flags.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| List extraction from LLM | Custom JSON list parser | instructor wrapper model `create(response_model=CategoryExtractionResponse)` | Handles validation, retries, schema enforcement for lists. Proven pattern from instructor docs. |
| Semantic deduplication | Custom string matching/edit distance | Cosine similarity on existing embeddings (paraphrase-multilingual-mpnet-base-v2) | Catches paraphrased duplicates across languages. Embedding model already loaded from Phase 2. |
| Citation verification | Custom text matching | Existing CitationVerifier from Phase 3 | NLI cross-encoder already handles entailment checking. Reuse, don't rebuild. |
| Confidence scoring | New scoring system | Existing `calculate_confidence()` from CitationVerifier | Same three-signal approach (NLI 50%, retrieval 30%, LLM 20%) applies to checklist items. |
| Mandatory detection | Regex for "shall"/"must" | LLM classification during extraction + regex validation | LLM understands context ("shall not be required" is NOT mandatory). Regex as secondary validation only. |

**Key insight:** Phase 4's value comes from the category definitions, prompts, and orchestration. All heavy-lifting components (LLM service, citation verifier, search, embeddings) exist from Phases 2 and 3. The new code is primarily: schemas, category definitions, orchestration service, prompt templates, deduplication, API, and database migration.

## Common Pitfalls

### Pitfall 1: Missing Requirements Due to Insufficient Retrieval

**What goes wrong:** Hybrid search returns only 5 chunks per query (Phase 3 default), but requirements are scattered across many sections and documents. Entire categories of requirements are missed.
**Why it happens:** Phase 3's top_k=5 is optimized for finding one specific value. Requirements extraction needs broader coverage.
**How to avoid:**
- Use multiple queries per category (3-4 queries with different terminology).
- Increase top_k to 8-10 per query, with a total cap of ~20 unique chunks per category.
- Merge and deduplicate chunks across queries before passing to LLM.
- Monitor extraction counts per category -- if a category returns 0 items, the queries may need tuning.
**Warning signs:** Empty categories, low total requirement count (< 20 for a typical tender).

### Pitfall 2: Duplicate Requirements Across Categories

**What goes wrong:** The same requirement appears in multiple categories (e.g., "provide insurance certificate" in both Commercial and Legal), inflating the checklist.
**Why it happens:** Categories have overlapping concerns. The LLM extracts everything it finds in the context, regardless of whether another category covers it.
**How to avoid:**
- Category-specific prompts explicitly instruct: "Only extract requirements that are primarily [category]. Do not extract requirements that are primarily about [other categories]."
- Post-extraction semantic deduplication using embedding similarity.
- Threshold of 0.9 cosine similarity for duplicate detection (empirically, this catches paraphrases without false positives on genuinely distinct requirements).
**Warning signs:** Checklist items that look very similar when reviewed side by side. Total count significantly higher than expected.

### Pitfall 3: Output Token Limit on Large Tenders

**What goes wrong:** A large tender with 80+ technical requirements causes the LLM to truncate output, losing requirements at the end.
**Why it happens:** While Gemini 2.5 Pro has 64K output tokens, a list of 80 items with full citations can approach this limit, especially with long verbatim quotes.
**How to avoid:**
- Split large categories. If Technical context is very large, split into sub-queries (e.g., "civil/structural", "MEP", "materials/testing").
- Monitor output token usage and implement a retry-with-split strategy if truncation is detected.
- Keep quotes concise (1-2 sentences) through prompt instruction.
**Warning signs:** Extraction returning significantly fewer items than expected. Last items in the list having lower quality.

### Pitfall 4: Category Confusion by LLM

**What goes wrong:** LLM assigns wrong category to a requirement, or extracts requirements that belong to a different category when context contains mixed content.
**Why it happens:** Retrieved chunks may contain requirements from multiple categories. The LLM extracts all it sees, not just the target category.
**How to avoid:**
- Strong category boundary in prompt: "You are extracting ONLY [Technical] requirements. Ignore any Commercial, Legal, or HSE items you encounter."
- Category-focused queries that primarily retrieve on-category chunks.
- Post-extraction validation: check if extracted text actually matches category semantics.
**Warning signs:** Uneven distribution (e.g., 90% Technical, 2% each for others).

### Pitfall 5: Mandatory vs Non-Mandatory Misclassification

**What goes wrong:** Requirements using ambiguous language ("should be provided", "it is expected that") are inconsistently classified as mandatory or non-mandatory.
**Why it happens:** Legal/tender language varies. "Should" can be mandatory in some jurisdictions. Context matters.
**How to avoid:**
- Prompt with specific deontic language mapping: "shall/must/required/mandatory = is_mandatory:true; should/may/recommended/desirable = is_mandatory:false."
- Include explicit examples in the extraction prompt.
- Default to is_mandatory=true for ambiguous cases (safer for tender compliance -- better to over-flag than under-flag).
**Warning signs:** Users frequently overriding mandatory flags.

## Code Examples

### Example 1: Category Definition Schema

```python
# Source: Adapted from Phase 3 FieldDefinition pattern + old bidops-ai checklist.py categories
from dataclasses import dataclass, field
from typing import Literal

RequirementCategory = Literal[
    "technical", "commercial", "legal", "hse",
    "submission_documents", "eligibility"
]

@dataclass
class CategoryDefinition:
    """Defines a requirement category for extraction."""
    name: RequirementCategory
    display_name: str
    description: str
    queries: list[str]
    top_k_per_query: int = 8
    max_context_chunks: int = 20
    prompt_hints: str = ""

CHECKLIST_CATEGORIES: list[CategoryDefinition] = [
    CategoryDefinition(
        name="technical",
        display_name="Technical",
        description="Technical specifications, standards, materials, testing, workmanship, design criteria",
        queries=[
            "technical requirements specifications standards",
            "material requirements testing inspection quality workmanship",
            "design requirements drawings calculations tolerances",
        ],
        top_k_per_query=8,
        max_context_chunks=20,
        prompt_hints=(
            "Focus on: technical specifications, referenced standards (BS, ASTM, ISO, EN), "
            "material requirements, testing and inspection, workmanship, tolerances, "
            "design criteria, methodology, and equipment requirements."
        ),
    ),
    CategoryDefinition(
        name="commercial",
        display_name="Commercial",
        description="Pricing, payment, bonds, insurance, warranties, financial requirements",
        queries=[
            "commercial requirements pricing payment terms",
            "insurance requirements warranty bond guarantee",
            "financial requirements tender bond advance payment retention",
        ],
        top_k_per_query=8,
        max_context_chunks=20,
        prompt_hints=(
            "Focus on: pricing format, payment conditions, bonds and guarantees, "
            "insurance requirements, warranty periods, retention, advance payment, "
            "cost breakdowns, and financial obligations."
        ),
    ),
    CategoryDefinition(
        name="legal",
        display_name="Legal",
        description="Contract conditions, dispute resolution, applicable law, compliance, intellectual property",
        queries=[
            "legal requirements conditions of contract applicable law",
            "dispute resolution arbitration governing law compliance",
            "intellectual property confidentiality indemnity liability",
        ],
        top_k_per_query=8,
        max_context_chunks=20,
        prompt_hints=(
            "Focus on: contractual obligations, conditions of contract, applicable law, "
            "dispute resolution, compliance requirements, indemnity, liability limitations, "
            "intellectual property, confidentiality, and regulatory compliance."
        ),
    ),
    CategoryDefinition(
        name="hse",
        display_name="HSE",
        description="Health, safety, environment requirements, plans, permits",
        queries=[
            "health safety environment requirements HSE plan",
            "safety requirements PPE training risk assessment",
            "environmental requirements waste management permits",
        ],
        top_k_per_query=8,
        max_context_chunks=15,
        prompt_hints=(
            "Focus on: HSE plans, safety certifications, PPE requirements, "
            "risk assessments, environmental management, waste disposal, "
            "permits and licenses, safety training, incident reporting, "
            "and environmental impact measures."
        ),
    ),
    CategoryDefinition(
        name="submission_documents",
        display_name="Submission Documents",
        description="Mandatory documents to be submitted with the tender",
        queries=[
            "documents to be submitted tender submission requirements",
            "required documents certificates appendices schedules",
            "submission checklist tender form deliverables",
        ],
        top_k_per_query=8,
        max_context_chunks=15,
        prompt_hints=(
            "Focus on: all documents that must be submitted with the tender, "
            "including forms, certificates, declarations, schedules, appendices, "
            "pricing documents, technical proposals, and any attachments. "
            "Note whether each document is mandatory or optional."
        ),
    ),
    CategoryDefinition(
        name="eligibility",
        display_name="Eligibility / Pre-Qualification",
        description="Pre-qualification criteria, eligibility requirements, minimum qualifications",
        queries=[
            "eligibility criteria pre-qualification requirements minimum",
            "experience requirements financial capacity turnover",
            "required certifications licenses registrations",
        ],
        top_k_per_query=8,
        max_context_chunks=15,
        prompt_hints=(
            "Focus on: minimum experience requirements, financial standing criteria, "
            "required certifications and licenses, technical capacity requirements, "
            "similar project experience, key personnel qualifications, "
            "and any disqualification criteria. These are CRITICAL for bid/no-bid decisions."
        ),
    ),
]
```

### Example 2: Pydantic Schemas for Checklist

```python
# Source: Adapted from Phase 3 extraction.py + old bidops-ai checklist.py
from pydantic import BaseModel, Field
from typing import Literal

RequirementCategory = Literal[
    "technical", "commercial", "legal", "hse",
    "submission_documents", "eligibility"
]

class RequirementItem(BaseModel):
    """A single requirement extracted by the LLM."""
    requirement: str = Field(
        description="Clear, concise statement of the requirement or obligation"
    )
    description: str = Field(
        default="",
        description="Additional context, details, or specific criteria"
    )
    is_mandatory: bool = Field(
        description=(
            "True if requirement uses mandatory language "
            "(shall, must, required, mandatory). "
            "False for recommendations (should, may, recommended)."
        )
    )
    source_document: str = Field(
        description="Filename of the source document"
    )
    page_number: int = Field(
        ge=1,
        description="1-based page number where requirement was found"
    )
    quote: str = Field(
        min_length=1,
        description="Exact verbatim quote from source supporting this requirement"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Self-assessed confidence (0.0 to 1.0)"
    )

class CategoryExtractionResponse(BaseModel):
    """LLM response for extracting requirements of one category."""
    items: list[RequirementItem] = Field(
        default_factory=list,
        description="List of all requirements found for this category"
    )
    reasoning: str = Field(
        default="",
        description="Brief summary of extraction approach"
    )

class VerifiedRequirement(BaseModel):
    """A requirement after NLI citation verification."""
    requirement: str
    description: str = ""
    category: RequirementCategory
    is_mandatory: bool
    citation: Citation  # Reuse from app.schemas.extraction
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: str = "low"  # high/medium/low
    requires_review: bool = True

class RequirementsChecklist(BaseModel):
    """Complete requirements checklist for a project."""
    requirements: list[VerifiedRequirement] = Field(default_factory=list)
    submission_documents: list[VerifiedRequirement] = Field(default_factory=list)
    eligibility_criteria: list[VerifiedRequirement] = Field(default_factory=list)
    total_count: int = 0
    mandatory_count: int = 0
    categories_extracted: list[str] = Field(default_factory=list)

class ChecklistResponse(BaseModel):
    """API response for checklist extraction."""
    project_id: int
    status: str  # "completed", "in_progress", "failed", "not_started"
    checklist: RequirementsChecklist | None = None
    extraction_time_seconds: float | None = None
    total_requirements: int = 0
    requirements_requiring_review: int = 0
```

### Example 3: Checklist Extraction Prompt Template

```python
def build_checklist_extraction_prompt(
    category: CategoryDefinition,
    context: str,
) -> str:
    """Build extraction prompt for one requirement category."""
    return f"""\
Extract ALL {category.display_name} requirements from the tender document excerpts below.

CATEGORY: {category.display_name}
CATEGORY DESCRIPTION: {category.description}

{category.prompt_hints}

INSTRUCTIONS:
1. Extract EVERY {category.display_name.lower()} requirement, obligation, or condition found in the excerpts.
2. For each requirement:
   - Write a clear, concise statement of the requirement.
   - Add a description with any specific quantities, percentages, deadlines, or criteria.
   - Determine if it is mandatory (uses "shall", "must", "required") or recommended ("should", "may").
   - Copy the EXACT verbatim quote from the source supporting this requirement.
   - Include the source document name and page number from the [SOURCE:... | PAGE:...] labels.
   - Assess your confidence from 0.0 to 1.0.
3. ONLY extract {category.display_name.lower()} requirements. Skip requirements that belong to other categories.
4. Do NOT fabricate or infer requirements not explicitly stated in the documents.
5. If no {category.display_name.lower()} requirements are found, return an empty items list.
6. Be thorough -- missing a requirement could lead to tender disqualification.

DOCUMENT EXCERPTS:
{context}"""
```

### Example 4: ChecklistService Orchestration

```python
class ChecklistService:
    """Orchestrates category-based requirements checklist extraction."""

    def __init__(
        self,
        search_service: HybridSearchService,
        llm_service: GeminiService,
        citation_verifier: CitationVerifier,
    ):
        self._search = search_service
        self._llm = llm_service
        self._verifier = citation_verifier

    async def extract_checklist(self, project_id: int) -> RequirementsChecklist:
        all_requirements: list[VerifiedRequirement] = []

        for category in CHECKLIST_CATEGORIES:
            # 1. Multi-query retrieval
            chunks = await self._retrieve_category_chunks(project_id, category)
            if not chunks:
                continue

            # 2. Build context and prompt
            context = build_labeled_context(chunks)
            prompt = build_checklist_extraction_prompt(category, context)

            # 3. Extract list of requirements
            response: CategoryExtractionResponse = await asyncio.to_thread(
                self._llm.extract,
                prompt=prompt,
                response_model=CategoryExtractionResponse,
            )

            # 4. Verify each citation
            for item in response.items:
                verified = self._verify_requirement(item, chunks, category.name)
                all_requirements.append(verified)

            # Rate limit delay
            await asyncio.sleep(0.5)

        # 5. Deduplicate across categories
        unique = self._deduplicate(all_requirements)

        # 6. Assemble checklist
        return self._assemble_checklist(unique)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single mega-prompt for all requirements | Category-based or per-section extraction | 2024-2025 | Better recall, natural categorization, error isolation |
| Regex for "shall"/"must" obligation detection | LLM contextual understanding + regex validation | 2024-2025 | LLM handles negation ("shall not be required"), context-dependent mandatory language |
| Manual JSON schema (old bidops-ai) | Pydantic schema with instructor validation + retries | 2025 | Eliminates manual JSON parsing, automatic validation |
| No citation verification | NLI cross-encoder verification (Phase 3 infrastructure) | 2025 | Independent verification catches hallucinated requirements |
| Full document context | Retrieval-based focused context | 2024-2025 | Avoids "lost in the middle" degradation, enables citation tracking |

**Deprecated/outdated:**
- Old bidops-ai `checklist.py`: Uses raw JSON schema (not Pydantic), sends full document content (not retrieval), no citation verification, uses LangChain. Reference for category names and prompt structure only.
- 10-category system (from old bidops-ai): Too fine-grained. 6 categories is sufficient -- Quality maps to Technical, Bonds to Commercial, Schedule splits across Technical/Commercial, Documentation to Submission Documents.

## Integration Points with Existing Code

### Phase 3 Services (Reused Directly)

| Existing Service | Location | How Phase 4 Uses It |
|-----------------|----------|---------------------|
| `GeminiService` | `app/services/llm/gemini_service.py` | `.extract(prompt, response_model=CategoryExtractionResponse)` for list extraction per category. No changes needed. |
| `CitationVerifier` | `app/services/extraction/citation_verifier.py` | `.verify_citation(claim, source_text)` for per-requirement NLI checking. `.calculate_confidence()` for confidence scores. No changes needed. |
| `build_labeled_context()` | `app/services/llm/context_builder.py` | Reused as-is for building labeled context from retrieved chunks. |
| `HybridSearchService` | `app/services/search/hybrid_search.py` | `.search(project_id, query, top_k, mode="hybrid")` for per-category chunk retrieval. |
| `Citation` schema | `app/schemas/extraction.py` | Reused in VerifiedRequirement to store source document + page + quote. |

### Phase 3 Patterns (Replicated)

| Phase 3 Pattern | Phase 4 Adaptation |
|-----------------|-------------------|
| `extract_project_summary()` loop over SUMMARY_FIELDS | `extract_checklist()` loop over CHECKLIST_CATEGORIES |
| `FieldDefinition` dataclass | `CategoryDefinition` dataclass (similar but for categories) |
| `ExtractedField` (single value) | `CategoryExtractionResponse` (list of items) |
| `build_extraction_prompt()` | `build_checklist_extraction_prompt()` (similar structure) |
| `extract_and_persist()` | `extract_and_persist_checklist()` (same pattern, different column) |
| `POST /api/projects/{id}/extract` | `POST /api/projects/{id}/checklist` (same API pattern) |

### Database Changes Needed

| Model | Change | Details |
|-------|--------|---------|
| `Project` | Add `checklist_json: Mapped[str \| None]` | Text column storing RequirementsChecklist as JSON |
| `Project` | Add `checklist_status: Mapped[str \| None]` | Status tracking: None, "in_progress", "completed", "failed" |

## Open Questions

1. **Optimal chunk count per category**
   - What we know: Phase 3 uses 3-8 chunks per field. Requirements extraction needs broader coverage.
   - What's unclear: Whether 20 unique chunks per category is sufficient for large tenders (500+ pages).
   - Recommendation: Start with 8 per query, 3 queries, max 20 unique chunks per category. If testing shows missed requirements, increase to 10 per query or add more query variants.

2. **Deduplication threshold tuning**
   - What we know: Cosine similarity of 0.9 is a common threshold for near-duplicate detection. The Forgent AI article used Gemini 2.5 Pro clustering for deduplication but noted it was slow and erratic.
   - What's unclear: Whether 0.9 is optimal for construction tender language. Arabic/English cross-language duplicates may have different similarity distributions.
   - Recommendation: Start with 0.9. Log duplicates detected for manual review during testing. Adjust threshold based on false positive/negative rates.

3. **Handling very large tenders (500+ pages)**
   - What we know: A typical construction tender has 50-200 pages. Some large infrastructure tenders can exceed 500 pages with many volumes.
   - What's unclear: Whether 6 category extraction calls with 20 chunks each (~120 chunks total) is sufficient coverage for 500+ page tenders.
   - Recommendation: Design for extensibility -- the category system can add sub-categories or increase chunk counts. For v1, optimize for typical 50-200 page tenders.

4. **Arabic-specific extraction accuracy**
   - What we know: Gemini handles Arabic natively. The multilingual embedding model handles Arabic retrieval. Old bidops-ai did not have Arabic-specific checklist extraction.
   - What's unclear: Whether Arabic obligation language mapping ("yajib" = shall, "yanbaghi" = should) is handled correctly by Gemini without explicit mapping.
   - Recommendation: Include bilingual examples in extraction prompts. Test with Arabic tenders early. Add Arabic-specific prompt variants only if accuracy is measurably lower.

## Sources

### Primary (HIGH confidence)

- Phase 3 RESEARCH.md and existing codebase -- direct code inspection of GeminiService, CitationVerifier, ExtractionService, field_definitions.py, context_builder.py, extraction schemas
- [Instructor List Extraction Documentation](https://python.useinstructor.com/learning/patterns/list_extraction/) -- Wrapper model pattern, validation, constraints for list extraction
- [Instructor Iterable Extraction Documentation](https://python.useinstructor.com/concepts/iterable/) -- `create_iterable()` pattern for streaming multiple objects
- [Instructor google-genai Integration Guide](https://python.useinstructor.com/integrations/genai/) -- Confirmed: Gemini does NOT support Union types, streaming limitations with structured output (as of July 2025), `create_iterable` works with Gemini
- [Gemini Structured Outputs Documentation](https://ai.google.dev/gemini-api/docs/structured-output) -- response_json_schema supports list types, 64K output token limit

### Secondary (MEDIUM confidence)

- [Forgent AI: LLM Extraction MVP Lessons](https://forgent.medium.com/beyond-the-hype-lessons-learned-from-building-an-llm-based-extraction-mvp-a969d4ac0fcf) -- Gemini 2.5 Pro ~98% recall on requirements extraction, deduplication challenges with chunked approach, clustering + LLM deduplication strategy (May 2025)
- [Stack AI: Tender Document Analysis](https://www.stack-ai.com/blog/how-to-build-a-tender-document-analysis-ai-tool) -- Architecture patterns for tender analysis with AI agents
- [Gemini Context Window Specifications](https://www.datastudios.org/post/google-gemini-context-window-token-limits-model-comparison-and-workflow-strategies-for-late-2025) -- 1M input, 64K output tokens for Gemini 2.5 Pro
- Old bidops-ai `checklist.py` -- Reference for category definitions and prompt structure (not to be imported, only referenced)

### Tertiary (LOW confidence)

- [LLM-assisted Extraction of Regulatory Requirements (GDPR case study)](https://orbilu.uni.lu/bitstream/10993/65265/1/2025-RE-ACSBLSVS.pdf) -- 97.71% accuracy on compliance template filling, 70.56% on obligation extraction. Different domain (GDPR vs construction) but similar patterns.
- [Structuring LLM Outputs for Legal Prompt Engineering](https://studio.netdocuments.com/post/structuring-llm-outputs) -- Best practices for legal/obligation language extraction

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries already installed from Phases 2-3. No new dependencies. Instructor list extraction patterns verified in official docs.
- Architecture: HIGH -- Category-based extraction follows established Phase 3 per-field pattern. Multi-query retrieval is a natural extension of Phase 2 search. All integration points verified by reading actual code.
- Pitfalls: HIGH -- Deduplication challenge confirmed by Forgent AI (May 2025 production experience). Output token limits documented. Category confusion mitigated by focused prompts.
- Code examples: MEDIUM -- Examples adapted from Phase 3 patterns (verified) combined with instructor list extraction docs (verified). Deduplication threshold (0.9) needs empirical tuning.

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days -- patterns are stable, category definitions may need tuning based on testing)
