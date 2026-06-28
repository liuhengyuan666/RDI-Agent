"""LLM Provider Factory — 隔离循环导入."""

import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# ---------------------------------------------------------------------------
# LLM Provider Configuration (env-driven, pluggable)
# ---------------------------------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))  # 0.0 for deterministic guardrails


def get_llm() -> Any:
    """
    Return a LangChain chat model based on environment variables.

    Supported providers:
      - openai    → ChatOpenAI (default)
      - anthropic → ChatAnthropic
      - deepseek  → ChatOpenAI (OpenAI-compatible, base_url override)
      - (extendable) azure, local, etc.

    Environment variables:
      LLM_PROVIDER        (default: openai)
      LLM_MODEL           (default: gpt-4o)
      LLM_BASE_URL        (optional, for deepseek / local models)
      LLM_API_KEY         (optional, overrides provider-specific env var)
      LLM_TEMPERATURE     (default: 0.0 — deterministic for guardrails)
      OPENAI_API_KEY / ANTHROPIC_API_KEY / DEEPSEEK_API_KEY
    """
    if LLM_PROVIDER == "openai":
        return ChatOpenAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
        )
    elif LLM_PROVIDER == "anthropic":
        return ChatAnthropic(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
        )
    elif LLM_PROVIDER == "deepseek":
        # DeepSeek is OpenAI-compatible; requires LLM_BASE_URL and LLM_API_KEY
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
        api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "DeepSeek provider requires DEEPSEEK_API_KEY or LLM_API_KEY env var."
            )
        return ChatOpenAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            base_url=base_url,
            openai_api_key=api_key,
        )
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}. "
            "Set env to 'openai', 'anthropic', or 'deepseek'."
        )
