import groq
from typing import Optional
from config import get_settings
from src.retrieval.retriever import retrieve_context
from src.prompts.prompt_templates import ROUTER_SYSTEM_PROMPT, build_agent_prompt
from src.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Initialize Groq client
client = groq.Groq(api_key=settings.groq_api_key)
MODEL_NAME = "llama-3.3-70b-versatile"

def route_query(query: str) -> str:
    """Basic routing logic to simulate multi-agent orchestration."""
    try:
        res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0.1,
            max_tokens=10,
        )
        agent_name = res.choices[0].message.content.strip()
        logger.info(f"Routed query to: {agent_name}")
        return agent_name
    except Exception as e:
        logger.error(f"Routing error: {str(e)}")
        return "General Agent"

def agent_generate(query: str, agent_type: str, namespace: Optional[str] = None) -> str:
    """Generates a response using the appropriate agent and context."""
    # 1. Retrieve relevant documents — scoped to this session's namespace only
    context_text = retrieve_context(query, namespace=namespace)
    
    # 2. Build the prompt
    final_prompt = build_agent_prompt(agent_type, context_text)
    
    # 3. Generate response
    try:
        res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": final_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.2,
        )
        return res.choices[0].message.content
    except Exception as e:
        logger.error(f"Generation error with {agent_type}: {str(e)}")
        raise
