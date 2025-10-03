import os
from typing import Optional

import dotenv
try:  # pragma: no cover - 実環境では正しく import される
    import google.generativeai as generativeai
except ImportError:  # pragma: no cover - テストではモックで代替
    generativeai = None


class LLMUnavailableError(Exception):
    """Raised when the LLM client cannot be configured."""


def build_generative_model(config: dict, model_name_override: Optional[str] = None):
    """Configure and return a GenerativeModel instance.

    Parameters
    ----------
    config: dict
        Loaded configuration dictionary (expects gemini_model_name).
    model_name_override: Optional[str]
        Explicit Gemini model id to use instead of the config value.

    Returns
    -------
    google.generativeai.GenerativeModel
        Configured generative model ready for use.

    Raises
    ------
    LLMUnavailableError
        If the API key or model configuration is missing or invalid.
    """
    dotenv.load_dotenv()

    model_name = model_name_override or config.get("gemini_model_name")
    if not model_name:
        raise LLMUnavailableError(
            "Gemini model name is not configured. Set 'gemini_model_name' in config.yaml "
            "or provide --llm-model when invoking the CLI."
        )

    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        raise LLMUnavailableError(
            "Environment variable AI_API_KEY is not set. Provide a valid Gemini API key."
        )

    if generativeai is None:
        raise LLMUnavailableError(
            "google-generativeai パッケージがインストールされていません。"
        )

    try:
        generativeai.configure(api_key=api_key)
        return generativeai.GenerativeModel(model_name)
    except Exception as exc:  # pragma: no cover - passthrough for external SDK failures
        raise LLMUnavailableError(str(exc)) from exc
