"""Minimal single-call Gemini smoke test — proves the LLM integration works
independent of the per-field extraction's rate-limit storm.

Makes at most a few requests, spaced to respect the free-tier 5 RPM window.
Exit 0 = LLM returned a validated structured object (integration OK).
Exit 2 = quota/429 exhausted (key tier insufficient, NOT a code bug).
"""

from __future__ import annotations

import sys
import time

from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.llm.gemini_service import GeminiService


class MiniSummary(BaseModel):
    project_name: str = Field(description="The project / tender name")
    project_owner: str = Field(description="The project owner / employer")


PROMPT = (
    "Extract the project name and owner from this tender text.\n"
    "Text: 'Project: New Cairo Medical Center - Main Hospital Building. "
    "Project Owner / Employer: New Urban Communities Authority (NUCA). "
    "Tender Reference No.: NCMC-2026-TND-014.'"
)


def main() -> int:
    s = get_settings()
    keys = s.gemini_key_list()
    svc = GeminiService(api_keys=keys, model=s.gemini_model)
    print(f"model={s.gemini_model} keys={len(keys)}", flush=True)

    for attempt in range(1, 4):
        try:
            r = svc.extract(PROMPT, MiniSummary, max_retries=1)
            print("LLM_OK:", r.model_dump(), flush=True)
            return 0
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            print(f"attempt {attempt} failed: {msg[:180]}", flush=True)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                if attempt < 3:
                    print("429 -> waiting 65s before retry", flush=True)
                    time.sleep(65)
                continue
            print("NON_QUOTA_ERROR", flush=True)
            return 1
    print("LLM_FAILED_QUOTA (free-tier exhausted — not a code defect)", flush=True)
    return 2


if __name__ == "__main__":
    sys.exit(main())
