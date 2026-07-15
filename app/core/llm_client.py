import os
from langchain_core.language_models.chat_models import BaseChatModel

from app.services.generation.debug_log import gen_log

def get_chat_model(purpose: str) -> BaseChatModel:
    """
    Returns a configured LangChain chat model based on the LLM_PROVIDER env var.
    The purpose parameter allows for future model routing based on agent role
    (e.g., 'strategist', 'writer', 'reviewer').
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    # We can eventually use the 'purpose' string to pick a different model name or temperature,
    # but for now we just use a default for each provider.
    temperature = 0.7 if purpose != "reviewer" else 0.2

    if provider == "openai":
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    elif provider == "anthropic":
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    elif provider == "gemini":
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    elif provider == "ollama":
        model_name = os.getenv("OLLAMA_MODEL", "llama3")
    elif provider == "groq":
        model_name = os.getenv("GROQ_MODEL", "llama3")
    else:
        model_name = "unknown"

    gen_log(
        "LLM → get_chat_model",
        agent_purpose=purpose,
        provider=provider,
        model=model_name,
        temperature=temperature,
    )
    
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
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature
        )
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
        

