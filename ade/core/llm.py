import json
import sys
import time
import uuid

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ade.core.config import Settings, get_settings
from ade.core.models import LLMResponse
from ade.core.redis_client import cache_get, cache_set, make_llm_cache_key

_llm_instance: "ClaudeLLM | None" = None


class ClaudeLLM:
    """Claude API wrapper with retry logic, Redis caching, and usage logging."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = anthropic.AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    async def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        use_cache: bool = True,
        task_id: uuid.UUID | None = None,
        step_id: uuid.UUID | None = None,
        agent_name: str = "default",
    ) -> LLMResponse:
        """Send a completion request to Claude with caching and retry."""
        model = model or self.settings.default_codegen_model

        # Check cache
        cache_key = make_llm_cache_key(model, messages, system, temperature, max_tokens)
        if use_cache:
            cached = await cache_get(cache_key)
            if cached is not None:
                data = json.loads(cached)
                return LLMResponse(**data, cached=True)

        # Call Claude API with retry
        start = time.monotonic()
        response = await self._call_api(
            model=model,
            messages=messages,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency_ms = (time.monotonic() - start) * 1000

        # Extract response data
        content = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        result = LLMResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached=False,
            latency_ms=latency_ms,
        )

        # Cache the response (exclude cached and latency_ms — those are per-call)
        cache_data = {
            "content": content,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        }
        await cache_set(cache_key, json.dumps(cache_data), ttl=self.settings.llm_cache_ttl_seconds)

        # Log usage (best-effort — don't fail the call if logging fails)
        try:
            await self._log_usage(
                task_id=task_id,
                step_id=step_id,
                agent_name=agent_name,
                action="complete",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
        except Exception as e:
            print(f"Warning: failed to log LLM usage: {e}", file=sys.stderr)

        return result

    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _call_api(
        self,
        model: str,
        messages: list[dict],
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> anthropic.types.Message:
        """Make the actual API call with retry on transient errors."""
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        return await self.client.messages.create(**kwargs)

    async def _log_usage(
        self,
        task_id: uuid.UUID | None,
        step_id: uuid.UUID | None,
        agent_name: str,
        action: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> None:
        """Log token usage to the agent_logs table. Best-effort — never raises."""
        try:
            from ade.core.database import async_session_factory
            from ade.core.models import AgentLog

            async with async_session_factory() as session:
                log = AgentLog(
                    task_id=task_id,
                    step_id=step_id,
                    agent_name=agent_name,
                    action=action,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            print(f"Warning: failed to log LLM usage: {e}", file=sys.stderr)


def get_llm() -> ClaudeLLM:
    """Get or create the ClaudeLLM singleton."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ClaudeLLM()
    return _llm_instance
