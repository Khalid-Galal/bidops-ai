"""LLM Service with hybrid routing between Gemini Flash and Pro models."""

import json
from enum import Enum
from typing import Any, Optional, Union

from app.config import get_settings, get_rules

settings = get_settings()
rules = get_rules()


class LLMProvider(str, Enum):
    """Available LLM providers."""
    GEMINI_FLASH = "gemini_flash"
    GEMINI_PRO = "gemini_pro"
    AUTO = "auto"  # Automatic routing based on task


class TaskComplexity(str, Enum):
    """Task complexity levels for routing."""
    SIMPLE = "simple"      # Use Gemini Flash
    MODERATE = "moderate"  # Use Gemini Flash
    COMPLEX = "complex"    # Use Gemini Pro


class LLMService:
    """Service for LLM operations with hybrid routing.

    Routes requests to either Gemini Flash (fast, simple tasks) or
    Gemini Pro (complex tasks) based on task complexity.
    """

    # Task to complexity mapping
    TASK_COMPLEXITY = {
        # Simple tasks - use Gemini Flash
        "classification": TaskComplexity.SIMPLE,
        "keyword_extraction": TaskComplexity.SIMPLE,
        "language_detection": TaskComplexity.SIMPLE,
        "simple_qa": TaskComplexity.SIMPLE,

        # Moderate tasks - use Gemini Flash
        "categorization": TaskComplexity.MODERATE,
        "entity_extraction": TaskComplexity.MODERATE,
        "template_filling": TaskComplexity.MODERATE,

        # Complex tasks - use Gemini Pro
        "summary_extraction": TaskComplexity.COMPLEX,
        "checklist_generation": TaskComplexity.COMPLEX,
        "offer_analysis": TaskComplexity.COMPLEX,
        "compliance_check": TaskComplexity.COMPLEX,
        "clarification_drafting": TaskComplexity.COMPLEX,
        "document_understanding": TaskComplexity.COMPLEX,
    }

    def __init__(self):
        """Initialize LLM service."""
        self._gemini_flash_client = None
        self._gemini_pro_client = None

    @property
    def gemini_flash_client(self):
        """Lazy-load Gemini Flash client."""
        if self._gemini_flash_client is None and settings.GOOGLE_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            self._gemini_flash_client = ChatGoogleGenerativeAI(
                model=settings.GEMINI_FLASH_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.1,
                max_output_tokens=8192,
            )
        return self._gemini_flash_client

    @property
    def gemini_pro_client(self):
        """Lazy-load Gemini Pro client."""
        if self._gemini_pro_client is None and settings.GOOGLE_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            self._gemini_pro_client = ChatGoogleGenerativeAI(
                model=settings.GEMINI_PRO_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.1,
                max_output_tokens=8192,
            )
        return self._gemini_pro_client

    def _get_provider_for_task(self, task_type: str) -> LLMProvider:
        """Determine which provider to use for a task.

        Args:
            task_type: Type of task being performed

        Returns:
            LLMProvider to use
        """
        # Route based on task complexity
        complexity = self.TASK_COMPLEXITY.get(task_type, TaskComplexity.COMPLEX)

        if complexity in (TaskComplexity.SIMPLE, TaskComplexity.MODERATE):
            return LLMProvider.GEMINI_FLASH
        else:
            return LLMProvider.GEMINI_PRO

    async def generate(
        self,
        prompt: str,
        task_type: str = "general",
        provider: LLMProvider = LLMProvider.AUTO,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate text using appropriate LLM.

        Args:
            prompt: The prompt to send
            task_type: Type of task for routing
            provider: Force specific provider or AUTO
            json_mode: Request JSON output format
            max_tokens: Override max tokens
            temperature: Override temperature

        Returns:
            Generated text response
        """
        # Determine provider
        if provider == LLMProvider.AUTO:
            provider = self._get_provider_for_task(task_type)

        try:
            if provider == LLMProvider.GEMINI_PRO:
                return await self._generate_gemini(
                    self.gemini_pro_client, prompt, json_mode, max_tokens, temperature
                )
            else:
                return await self._generate_gemini(
                    self.gemini_flash_client, prompt, json_mode, max_tokens, temperature
                )
        except Exception as e:
            # Fallback to other model on failure
            if provider == LLMProvider.GEMINI_PRO and self.gemini_flash_client:
                return await self._generate_gemini(
                    self.gemini_flash_client, prompt, json_mode, max_tokens, temperature
                )
            elif provider == LLMProvider.GEMINI_FLASH and self.gemini_pro_client:
                return await self._generate_gemini(
                    self.gemini_pro_client, prompt, json_mode, max_tokens, temperature
                )
            raise

    async def _generate_gemini(
        self,
        client,
        prompt: str,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate using Gemini."""
        from langchain_core.messages import HumanMessage

        if not client:
            raise ValueError("Gemini client not configured")

        # Add JSON instruction if needed
        if json_mode:
            prompt = f"{prompt}\n\nRespond with valid JSON only."

        messages = [HumanMessage(content=prompt)]

        # Configure parameters
        if max_tokens:
            client.max_output_tokens = max_tokens
        if temperature is not None:
            client.temperature = temperature

        response = await client.ainvoke(messages)
        return response.content

    async def generate_structured(
        self,
        prompt: str,
        output_schema: dict,
        task_type: str = "general",
        provider: LLMProvider = LLMProvider.AUTO,
    ) -> dict:
        """Generate structured output matching a schema.

        Args:
            prompt: The prompt to send
            output_schema: Expected output JSON schema
            task_type: Type of task for routing
            provider: Force specific provider or AUTO

        Returns:
            Parsed JSON response
        """
        # Add schema to prompt
        schema_prompt = f"""{prompt}

Your response must be valid JSON matching this schema:
```json
{json.dumps(output_schema, indent=2)}
```

Respond with only the JSON object, no additional text."""

        response = await self.generate(
            prompt=schema_prompt,
            task_type=task_type,
            provider=provider,
            json_mode=True,
        )

        # Parse JSON response
        try:
            # Clean response if needed
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")

    async def chat(
        self,
        messages: list[dict],
        task_type: str = "general",
        provider: LLMProvider = LLMProvider.AUTO,
    ) -> str:
        """Multi-turn chat conversation.

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            task_type: Type of task for routing
            provider: Force specific provider or AUTO

        Returns:
            Assistant response
        """
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        if provider == LLMProvider.AUTO:
            provider = self._get_provider_for_task(task_type)

        # Convert messages to LangChain format
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        # Choose client based on provider
        client = (
            self.gemini_pro_client if provider == LLMProvider.GEMINI_PRO
            else self.gemini_flash_client
        )

        if client:
            response = await client.ainvoke(lc_messages)
            return response.content
        else:
            raise ValueError("No Gemini client available")

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if settings.GOOGLE_API_KEY:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.GEMINI_EMBEDDING_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
            )
            return await embeddings.aembed_query(text)
        else:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            return model.encode(text).tolist()

    def get_provider_status(self) -> dict:
        """Get status of available providers.

        Returns:
            Status dictionary
        """
        return {
            "gemini_flash": {
                "available": bool(self.gemini_flash_client),
                "model": settings.GEMINI_FLASH_MODEL if self.gemini_flash_client else None,
            },
            "gemini_pro": {
                "available": bool(self.gemini_pro_client),
                "model": settings.GEMINI_PRO_MODEL if self.gemini_pro_client else None,
            },
            "default": "gemini_flash (simple/moderate) and gemini_pro (complex)",
        }
