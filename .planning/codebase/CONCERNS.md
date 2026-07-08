# Codebase Concerns

> **SUPERSEDED (2026-07-08):** describes the February v1; the shipped system is the root app/ FastAPI+Jinja build - see docs/reviews/2026-07-07-full-system-review.md

**Analysis Date:** 2026-02-04

## Security Concerns

### Default Secret Key in Config

**Risk:** Production deployment with weak or default SECRET_KEY
- **Files:** `backend/app/config.py:60-62`
- **Issue:** Default value is `"change-this-secret-key-in-production"`. If deployment uses defaults, JWT tokens are compromisable.
- **Current mitigation:** Documentation mentions changing in production (DEPLOYMENT-SUMMARY.md), but no validation enforces production SECRET_KEY
- **Recommendations:**
  - Add startup validation that fails if SECRET_KEY contains "change-this" in production environments
  - Generate cryptographically secure default during first setup
  - Store SECRET_KEY separately from version control (already in .gitignore)

### Default Admin Credentials Hardcoded in Documentation

**Risk:** Default credentials in deployment docs enable unauthorized access
- **Files:** `DEPLOYMENT-SUMMARY.md:180-187`, deployment docs throughout
- **Issue:** Default login `admin@example.com` / `Admin123` documented publicly
- **Current mitigation:** Documentation notes "IMPORTANT: Change immediately after first login" but doesn't enforce it
- **Recommendations:**
  - Script should auto-generate strong random admin password on first deployment
  - Require password change on first login (add flag to User model)
  - Implement password rotation policy for admin accounts

### CORS Configuration Too Permissive in Development

**Risk:** CORS allows specific origins but includes hardcoded render.com URLs
- **Files:** `backend/app/main.py:51-56`
- **Issue:** `allow_origins` includes production URLs hardcoded in code (Render.com domains)
- **Current mitigation:** None - URLs are static in source
- **Recommendations:**
  - Load allowed origins from environment variable (ALLOWED_ORIGINS_JSON or similar)
  - Use ENVIRONMENT setting to auto-configure (dev allows localhost:3000, prod requires explicit list)
  - Remove hardcoded production URLs from source code

### Database Connection String in Config Defaults

**Risk:** SQLite database path is relative, can cause permission/path issues
- **Files:** `backend/app/config.py:34-37`
- **Issue:** Default `DATABASE_URL` is `"sqlite+aiosqlite:///./storage/database/bidops.db"` - relative path may resolve differently in different execution contexts
- **Impact:** Database migrations, backups, and access control become problematic in production
- **Recommendations:**
  - Always use absolute paths for production databases
  - Default to PostgreSQL for production scenarios
  - Add validation that development/local envs must explicitly opt-in to SQLite

### API Key Exposure in Error Messages

**Risk:** Exception handlers may leak sensitive information
- **Files:** `backend/app/main.py:86-99`
- **Issue:** General exception handler has conditional debug output. If DEBUG is accidentally enabled in production, stack traces with API keys/credentials could be exposed
- **Current mitigation:** DEBUG is false by default, but checked at runtime
- **Recommendations:**
  - Remove stack trace details completely from production responses
  - Log full exceptions server-side only with correlation IDs
  - Never expose internal error details to clients

---

## Error Handling Issues

### Broad Exception Catching Without Specific Logging

**Risk:** Silent failures in background tasks and service layer
- **Files:**
  - `backend/app/worker.py:139-140` (bare except Exception with no logging)
  - `backend/app/services/offer_service.py:136-137` (except Exception: pass)
  - `backend/app/parsers/pdf_parser.py:60, 74, 92` (multiple except blocks)
- **Issue:** Failures in document parsing and worker tasks are silently swallowed without logging, making debugging production issues impossible
- **Impact:** Documents fail to parse silently, extraction tasks fail without notification, errors accumulate undetected
- **Recommendations:**
  - Replace bare `except Exception` with specific exception types
  - Add structured logging (structlog is already in requirements.txt but not used)
  - Log at ERROR level with context (file path, project ID, attempt count)
  - Implement retry logic with exponential backoff for transient failures

### Database Session Exception Handling is Generic

**Risk:** Rollback failures may cascade
- **Files:** `backend/app/database.py:48-49, 62-63`
- **Issue:** `except Exception` catches all errors but doesn't distinguish between DB connection errors and business logic errors
- **Impact:** Failed transactions aren't properly categorized; connection pool may become exhausted if rollback fails
- **Recommendations:**
  - Catch specific SQLAlchemy exceptions (IntegrityError, OperationalError, TimeoutError)
  - Log connection state when rollback fails
  - Close session forcefully if rollback fails to prevent pool exhaustion

### Document Parsing Returns Early on Missing Results Without Notification

**Risk:** Silent failures in document processing pipeline
- **Files:** `backend/app/services/document_service.py:357` (bare return)
- **Issue:** Empty return with no error logging when chunks cannot be split
- **Impact:** Document appears indexed but contains no content; downstream extraction/search fails
- **Recommendations:**
  - Raise specific exception (DocumentProcessingError) instead of returning
  - Log warning with document details before returning
  - Update document status to FAILED with error message

---

## Performance Bottlenecks

### Vector Store Search Without Pagination or Limits

**Risk:** Memory exhaustion on large projects
- **Files:** `backend/app/services/vector_store.py:167` (query_embedding used without explicit limits)
- **Issue:** No mention of max results or pagination in semantic search
- **Impact:** Large collections (1M+ documents) could return enormous result sets
- **Recommendations:**
  - Enforce max_results parameter (default 100, max 1000)
  - Implement cursor-based pagination for vector DB
  - Add timeout to search queries

### No Database Connection Pooling Configuration

**Risk:** Connection exhaustion under load
- **Files:** `backend/app/database.py:19-24`
- **Issue:** `create_async_engine` has no pool_size or max_overflow settings
- **Impact:** Concurrent requests may starve for connections; database connection limit reached under load
- **Recommendations:**
  - Set `pool_size=20` and `max_overflow=40` for production (environment-dependent)
  - Configure `pool_timeout=30` and `pool_recycle=3600`
  - Monitor pool exhaustion in logs

### Large File Uploads Without Streaming

**Risk:** Memory usage proportional to file size
- **Files:** `backend/app/api/v1/documents.py` (uses UploadFile)
- **Issue:** FastAPI's UploadFile keeps entire file in memory before parsing
- **Impact:** 500MB file (max_upload_size) uses 500MB+ of RAM per concurrent upload
- **Recommendations:**
  - Stream uploads to disk using SpooledTemporaryFile
  - Set MAX_UPLOAD_SIZE_MB to reasonable limit (currently 500 is very high)
  - Implement chunk-based streaming parser for large files

### LLM Service Creates New Embedding Model Per Call

**Risk:** Memory leak and initialization overhead
- **Files:** `backend/app/services/llm_service.py:276-295` (embed_text creates new SentenceTransformer)
- **Issue:** `SentenceTransformer("all-MiniLM-L6-v2")` is loaded fresh for every embed call if Google API key not configured
- **Impact:** Hundreds of model loads during batch processing; significant RAM/latency overhead
- **Recommendations:**
  - Cache embedding model as singleton instance
  - Initialize on service instantiation, not per-call
  - Pre-load both Gemini and fallback embeddings at startup

### No Query Result Limits on List Endpoints

**Risk:** Out of memory on endpoints listing large datasets
- **Files:** `backend/app/api/v1/packages.py`, `backend/app/api/v1/suppliers.py`
- **Issue:** Database queries lack default LIMIT if pagination parameters missing
- **Current mitigation:** Pydantic validation on `page_size` (le=100) helps, but count queries are unlimited
- **Recommendations:**
  - Add max_limit constant (1000) at module level
  - Enforce LIMIT on all queries regardless of pagination params
  - Add query timeout for count operations

---

## Technical Debt

### Duplicate Database Context Management

**Risk:** Inconsistent error handling and resource leaks
- **Files:**
  - `backend/app/database.py:42-52` (get_db dependency)
  - `backend/app/database.py:56-66` (get_db_context context manager)
- **Issue:** Two similar implementations of database session management; services use context manager while endpoints use dependency
- **Impact:** Inconsistent rollback behavior; potential for connection leaks
- **Recommendations:**
  - Consolidate to single pattern (recommend context manager)
  - Wrapper function for dependency injection
  - Add cleanup timeout

### Hardcoded Task IDs in Worker

**Risk:** Job serialization fragility
- **Files:** `backend/app/worker.py:177-182`
- **Issue:** Task functions are in `WorkerSettings.functions` list - adding/removing tasks requires code edit
- **Impact:** Cannot dynamically register workers; refactoring task names breaks serialization
- **Recommendations:**
  - Use function registry decorator pattern
  - Store task names in database or config
  - Add function versioning for backward compatibility

### Configuration Split Between Code and YAML

**Risk:** Inconsistent config sources and validation gaps
- **Files:**
  - `backend/app/config.py` (Pydantic Settings)
  - `config/rules.yaml` (RulesConfig)
- **Issue:** Core settings in .env/Python, business rules in YAML; no unified schema or validation
- **Impact:** Hard to audit all configuration; rules changes require file edit + no validation
- **Recommendations:**
  - Consolidate all configuration into Pydantic models
  - Add JSON schema export for documentation
  - Implement hot-reload for rules with validation

### No Structured Logging Throughout Application

**Risk:** Debugging production issues is difficult
- **Files:** All service files use print() and basic string logging
- **Issue:** `structlog` is in requirements.txt but never imported/used
- **Current mitigation:** None - logs are unstructured
- **Recommendations:**
  - Implement structlog throughout services
  - Include context: project_id, user_id, request_id, operation name
  - Use log levels consistently (INFO for operations, WARNING for retries, ERROR for failures)
  - Example: `logger.info("document_parsed", document_id=doc_id, chunks=chunk_count, source="pdf")`

### Import Organization Inconsistent

**Risk:** Circular imports and tight coupling
- **Files:** Multiple service files have circular-looking imports (e.g., services importing services)
- **Issue:** No clear import rules documented; potential for circular dependency bugs
- **Recommendations:**
  - Establish import order: models → schemas → services → api
  - Move shared utilities to separate utils module
  - Add isort/ruff import sorting to pre-commit

---

## Scalability Limits

### Redis Used for Task Queue Without Persistence Config

**Risk:** Lost jobs on restart
- **Files:** `backend/app/worker.py:160-187`
- **Issue:** ARQ uses Redis but no configuration for persistence (AOF/RDB) mentioned
- **Current mitigation:** Job keep_result = 3600 only keeps results 1 hour
- **Recommendations:**
  - Document Redis persistence requirements (AOF recommended for production)
  - Add health check for Redis availability in startup
  - Implement retry on Redis connection failure (fallback to sync processing)

### Vector Database Not Sharded

**Risk:** Single Qdrant instance bottleneck
- **Files:** `backend/app/config.py:56`
- **Issue:** QDRANT_URL is single URL; no sharding configuration
- **Impact:** Collection grows unbounded; single point of failure
- **Recommendations:**
  - Document expected collection size limits
  - Plan migration path to Qdrant cluster
  - Implement collection rotation/archival strategy

### No Rate Limiting on API Endpoints

**Risk:** DoS vulnerability and resource exhaustion
- **Files:** All endpoints in `backend/app/api/v1/`
- **Issue:** No rate limiting middleware; endpoints accept unlimited requests
- **Impact:** Malicious users can exhaust database/LLM resources; expensive operations (extraction, parsing) can be spammed
- **Recommendations:**
  - Add SlowAPI rate limiter middleware
  - Configure per-user limits: 100 requests/minute for normal ops, 10 for extraction
  - Track by IP + user_id to prevent spoofing

---

## Testing Gaps

### No Test Suite in Repository

**Risk:** Refactoring breaks production functionality
- **Files:** Development packages commented out in `backend/requirements.txt:101-107`
- **Issue:** pytest and related testing packages are commented out; no test files in repo
- **Impact:** Cannot verify changes don't break existing functionality; bug detection relies on manual testing
- **Recommendations:**
  - Uncomment test dependencies
  - Create test suite covering:
    - API endpoint authorization (permission checks)
    - Database transaction rollback on errors
    - LLM service routing logic
    - Document parser error handling
  - Add integration tests for critical workflows (upload → parse → extract)
  - Configure pytest-cov to enforce >80% coverage

### No Type Hints Validation

**Risk:** Type-related bugs slip to production
- **Files:** Some files missing type hints on function arguments
- **Issue:** mypy not configured; no type checking in CI (not even configured)
- **Recommendations:**
  - Add mypy to requirements.txt and pre-commit
  - Configure strict mode: `strict = true` in setup.cfg
  - Add type checking to CI pipeline

### Email Service Not Tested Against Real SMTP

**Risk:** Email features fail in production
- **Files:** `backend/app/services/email_service.py` (658 lines, no test references)
- **Issue:** Complex email logic (Graph API, SMTP, HTML parsing) has no test coverage
- **Impact:** Email sends silently fail; users don't get RFQs or notifications
- **Recommendations:**
  - Create fixtures for testing both SMTP and Graph APIs
  - Mock external APIs for unit tests
  - Integration test against test SMTP server (TestServer or mailhog)

---

## Known Issues & Fragile Areas

### CAD File Processing via ODA Converter

**Fragility:** External executable dependency
- **Files:** `backend/app/config.py:94`, `backend/app/parsers/cad_parser.py`
- **Issue:** Requires ODA File Converter executable installed separately; path configured in `ODA_CONVERTER_PATH`
- **Current state:** Documented as required in README.md, but no fallback if missing
- **Safe modification:**
  - Verify ODA path exists on startup
  - Raise clear error if missing rather than cryptic subprocess failure
  - Provide Docker image with ODA pre-installed
- **Risk if unchanged:** CAD file uploads silently fail; error messages unhelpful

### Tesseract OCR Language Data

**Fragility:** Language pack dependency
- **Files:** `backend/app/config.py:91`, document parsers
- **Issue:** Requires both English and Arabic language packs installed for `TESSERACT_LANG=eng+ara`
- **Current state:** Windows setup guide exists but installation is manual
- **Safe modification:**
  - Check language packs exist on startup
  - Fall back to eng-only if ara unavailable (with warning)
  - Add script to install language packs
- **Risk if unchanged:** Arabic documents processed incorrectly; errors appear as garbled text

### Document Chunking Strategy Fixed at Runtime

**Fragility:** No ability to re-chunk without rebuilding
- **Files:** `backend/app/services/document_service.py:37-38`
- **Issue:** CHUNK_SIZE and CHUNK_OVERLAP set at config load time; changing requires restart + manual re-processing
- **Current state:** Chunks are stored but not regeneratable from original content
- **Safe modification:**
  - Store original raw text in database (separate from chunks)
  - Add endpoint to re-chunk documents with new parameters
  - Version chunks by CHUNK_SIZE parameter
- **Risk if unchanged:** Suboptimal chunking strategy can't be corrected without full re-ingest

### Offer Evaluation Score Weights Hardcoded

**Fragility:** Business logic tightly coupled to config
- **Files:** `backend/app/config.py:142-149` (RulesConfig.scoring_weights)
- **Issue:** Scoring weights in YAML but nowhere to update them without restarting service
- **Current state:** No UI to modify weights; requires file edit + restart
- **Safe modification:**
  - Store weights in database with audit trail
  - Add management endpoint to update weights (admin-only)
  - Cache in memory with invalidation on change
- **Risk if unchanged:** Cannot adjust evaluation criteria without downtime

### Missing Organization Isolation in Some Queries

**Fragility:** Potential data leakage between organizations
- **Files:** Some endpoints check `current_user.organization_id` but others may not
- **Issue:** Not systematically verified; easy to miss in refactoring
- **Current state:** Permissions layer exists but not comprehensive
- **Safe modification:**
  - Add decorator `@require_org_access` to all endpoints
  - Verify in database layer, not just API layer
  - Add automated test that user A cannot access user B's projects
- **Risk if unchanged:** Privilege escalation or data exposure between organizations

---

## Dependencies at Risk

### Pinned to Minimum Versions Without Upper Bounds

**Risk:** Breaking changes in minor version updates
- **Files:** `backend/requirements.txt` (e.g., `fastapi>=0.109.0`)
- **Issue:** Using `>=` without upper bounds means major version jumps allowed (0.109 → 1.0 could break)
- **Current mitigation:** None - `pip install` will grab latest compatible
- **Recommendations:**
  - Use compatible release clause: `fastapi>=0.109.0,<1`
  - Lock critical dependencies: `pydantic>=2.5.0,<3`, `sqlalchemy>=2.0,<3`
  - Use lock file (pip-freeze or poetry/pipenv)
  - Add dependency update policy (quarterly review)

### Sentence Transformers Fallback Without Version Lock

**Risk:** Embedding model changes break vector search
- **Files:** `backend/app/services/llm_service.py:293-295`
- **Issue:** `SentenceTransformer("all-MiniLM-L6-v2")` auto-downloads latest version
- **Impact:** Old vectors can't be searched with new model; silently produces incorrect results
- **Recommendations:**
  - Pin transformers version in requirements.txt
  - Add model version to vector metadata
  - Document embedding model as part of data schema
  - Implement migration path if model must change

### ifcopenshell Commented Out (Cannot Install via Pip)

**Risk:** BIM file support incomplete
- **Files:** `backend/requirements.txt:71` (commented out)
- **Issue:** IFC parsing listed as supported in README.md but package can't be installed via pip (requires conda)
- **Impact:** IFC files uploaded will fail with unclear error
- **Recommendations:**
  - Either document BIM support as not available, or
  - Create Docker image with conda + ifcopenshell pre-installed
  - Add clear error message if IFC file uploaded without library
  - Consider alternative library (python-ifc)

---

## Missing Critical Features

### No Audit Trail for Data Changes

**Problem:** Cannot answer "who changed what and when"
- **Impact:** Compliance failure for regulated industries; cannot debug data corruption
- **Blocks:** Audit requirements, data governance, troubleshooting

### No Soft Deletes

**Problem:** Deleted data is permanently removed
- **Impact:** Cannot recover accidentally deleted projects/documents; audit trail incomplete
- **Blocks:** Data retention policies, compliance

### No Bulk Operations

**Problem:** Operations on 100+ items require individual API calls
- **Impact:** Slow data migrations, user operations timeout
- **Current gap:** No batch endpoints for documents, packages, suppliers, or offers

### No Export/Import Roundtrip

**Problem:** Data exported cannot be re-imported
- **Impact:** Difficult data migration between deployments
- **Current gap:** Export exists, but no import endpoint

### No API Documentation Generation

**Problem:** API Docs (/docs endpoint) disabled in production
- **Impact:** Integrators can't discover endpoints without reading code
- **Blocks:** Third-party integrations, API partnerships

---

## Infrastructure Concerns

### Docker Image Build Not Documented

**Risk:** Cannot rebuild container from source
- **Files:** `backend/Dockerfile` and `backend/Dockerfile.prod` exist
- **Issue:** No build instructions in README or deployment guides
- **Recommendations:**
  - Document: `docker build -t bidops-ai:latest -f Dockerfile.prod .`
  - Add build caching layer for dependencies
  - Test cold builds in CI

### Database Migrations Not Automatic

**Risk:** Schema changes don't deploy automatically
- **Files:** Alembic configured but no auto-migration in startup
- **Issue:** Manual `alembic upgrade head` required after deployment
- **Recommendations:**
  - Add startup hook to auto-run migrations
  - Test migrations in CI before deployment
  - Add rollback endpoint for disaster recovery

### No Health Check Endpoint for Load Balancer

**Risk:** Load balancer may route to unhealthy instances
- **Files:** `backend/app/api/v1/health.py` exists but may not be used
- **Recommendations:**
  - Ensure /health endpoint is configured in Docker healthcheck
  - Add to docker-compose.yml
  - Document in deployment guides

---

## Summary by Priority

### HIGH (Fix Before Production)
1. Default SECRET_KEY validation
2. CORS hardcoded URLs to environment
3. Broad exception catching with logging
4. Rate limiting on API endpoints
5. Organization isolation verification

### MEDIUM (Fix Before Scaling)
1. Database connection pooling
2. Vector store search limits
3. Structured logging implementation
4. Test suite creation
5. Type checking (mypy) validation

### LOW (Nice to Have)
1. Audit trail implementation
2. Soft deletes feature
3. Bulk operations support
4. API documentation in production
5. Configuration consolidation

---

*Concerns audit: 2026-02-04*
