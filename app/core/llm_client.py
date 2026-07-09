import os
from langchain_core.language_models.chat_models import BaseChatModel

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
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=temperature
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            temperature=temperature
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
            temperature=temperature
        )
    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3"),
            temperature=temperature,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model=os.getenv("GROQ_MODEL", "llama3"),
            temperature=temperature
        )
    else:
        
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
        

