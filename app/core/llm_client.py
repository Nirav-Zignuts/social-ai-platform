import os
from langchain_core.language_models.chat_models import BaseChatModel


# Conversational onboarding always uses Gemini (structured JSON turns).
ONBOARDING_PURPOSES = frozenset({"onboarding_assistant", "onboarding_synthesizer"})


def get_chat_model(purpose: str) -> BaseChatModel:
    """
    Returns a configured LangChain chat model based on the LLM_PROVIDER env var.
    The purpose parameter allows for model routing based on agent role
    (e.g., 'strategist', 'writer', 'reviewer', 'onboarding_assistant').

    Onboarding purposes always use Gemini via GEMINI_API_KEY / GOOGLE_API_KEY.
    """
    if purpose in ONBOARDING_PURPOSES:
        provider = "gemini"
    else:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if purpose == "reviewer":
        temperature = 0.2
    elif purpose == "onboarding_synthesizer":
        temperature = 0.4
    elif purpose == "onboarding_assistant":
        temperature = 0.7
    else:
        temperature = 0.7

    if provider == "openai":
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    elif provider == "anthropic":
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    elif provider == "gemini":
        # Default: gemini-2.5-flash — gemini-2.0-flash is listed for this key but has
        # free_tier quota limit:0 (returns 429 RESOURCE_EXHAUSTED on first request).
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    elif provider == "ollama":
        model_name = os.getenv("OLLAMA_MODEL", "llama3")
    elif provider == "groq":
        model_name = os.getenv("GROQ_MODEL", "llama3")
    else:
        model_name = "unknown"


    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            temperature=temperature
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        kwargs = {
            "model": model_name,
            "temperature": temperature,
        }
        if api_key:
            kwargs["google_api_key"] = api_key
        return ChatGoogleGenerativeAI(**kwargs)
    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model=model_name,
            temperature=temperature
        )
    else:

        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
