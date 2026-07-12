import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

def get_llm():
    """Initializes and returns the Groq LLM client."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        print("WARNING: GROQ_API_KEY not set. Generation will fail.")
        
    return ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.3-70b-versatile",
        temperature=0.1
    )

def generate_response(query: str, context: str) -> str:
    """Generates a response using the LLM given the context."""
    llm = get_llm()
    from src.generation.prompt_templates import RAG_PROMPT
    
    chain = RAG_PROMPT | llm | StrOutputParser()
    return chain.invoke({"context": context, "question": query})
