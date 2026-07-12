"""
Lightweight RAG engine using BM25 retrieval + Groq LLM.
No PyTorch, no sentence-transformers, no FastAPI — runs entirely inside Streamlit Cloud.
"""
import json
import os
import re
from pathlib import Path
from rank_bm25 import BM25Okapi
from groq import Groq

# ── Data loading ──────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
_DATA_FILE = _BASE_DIR / "data" / "processed" / "comprehensive_business_data.json"

_documents = None
_bm25 = None

def _load_data():
    global _documents, _bm25
    if _documents is not None:
        return
    with open(_DATA_FILE, "r") as f:
        raw = json.load(f)
    _documents = raw
    # Tokenise for BM25
    corpus = [_tokenise(doc["text"]) for doc in _documents]
    _bm25 = BM25Okapi(corpus)

def _tokenise(text: str) -> list[str]:
    """Simple whitespace + lowercase tokeniser for BM25."""
    return re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower()).split()

# ── Retrieval ─────────────────────────────────────────────────────────────────
def search_documents(query: str, k: int = 6) -> list[dict]:
    """BM25 retrieval — returns top-k most relevant document dicts."""
    _load_data()
    tokens = _tokenise(query)
    scores = _bm25.get_scores(tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [_documents[i] for i in top_indices]

def format_context(docs: list[dict]) -> str:
    """Formats retrieved docs into a context string for the LLM."""
    parts = []
    for d in docs:
        m = d["metadata"]
        parts.append(
            f"[Source: {m.get('authority','Unknown')} | Type: {m.get('business_type','general')} | "
            f"State: {m.get('state','national')} | Category: {m.get('doc_type','general')}]\n{d['text']}"
        )
    return "\n\n".join(parts)

# ── Generation ────────────────────────────────────────────────────────────────
_PROMPT_TEMPLATE = """You are an expert assistant for Indian business registration, compliance, taxation, and licensing.
You help entrepreneurs and business owners understand the legal requirements for starting and running a business in India.

Based ONLY on the following official sources, provide a comprehensive, well-structured answer to the user's question.

## Crucial Rules:
1. **Cite sources**: Reference the authority/source for each requirement (e.g., [Source: MCA], [Source: FSSAI]).
2. **No hallucination**: If the context doesn't cover something, say so explicitly.
3. **Step-by-step format**: When listing processes or requirements, use numbered steps.
4. **Include costs and timelines**: Where available, mention government fees and processing times.
5. **Practical advice**: Provide practical tips and common pitfalls to avoid.

## Response Format:
- Use markdown formatting for readability
- Use bullet points and numbered lists
- Bold important terms, fees, and deadlines

Context:
{context}

Question:
{question}

Answer:"""


def generate_response(query: str, context: str) -> str:
    """Calls Groq API to generate an answer from context."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "⚠️ **GROQ_API_KEY not set.** Add it to Streamlit secrets."

    client = Groq(api_key=api_key)
    prompt = _PROMPT_TEMPLATE.format(context=context, question=query)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=2048,
    )
    return response.choices[0].message.content


# ── Query metadata detection (carried from query_router) ─────────────────────
BUSINESS_KEYWORDS = {
    "sole_proprietorship": ["sole proprietor", "proprietorship", "single owner"],
    "pvt_ltd": ["private limited", "pvt ltd", "pvt. ltd", "company incorporation"],
    "llp": ["llp", "limited liability partnership"],
    "startup": ["startup india", "dpiit", "startup recognition"],
    "msme": ["msme", "udyam", "micro small medium"],
    "food_business": ["fssai", "food license", "restaurant", "food truck", "cloud kitchen"],
    "ecommerce": ["ecommerce", "e-commerce", "online store", "amazon", "flipkart"],
    "freelancer": ["freelancer", "consultant", "freelance"],
    "manufacturing": ["manufacturing", "factory", "industrial"],
    "healthcare": ["clinic", "hospital", "pharmacy", "medical"],
    "education": ["school", "coaching", "edtech", "education"],
    "real_estate": ["rera", "real estate", "construction", "builder"],
    "it_software": ["software", "saas", "tech company", "it company"],
    "gst": ["gst", "goods and services tax"],
}

def detect_business_type(query: str) -> str:
    q = query.lower()
    for btype, keywords in BUSINESS_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return btype
    return "general"


FOLLOW_UP_MAP = {
    "pvt_ltd": ["What is the annual compliance calendar for a Pvt Ltd?", "How much does it cost to incorporate a Pvt Ltd?", "What are the penalties for non-compliance?"],
    "llp": ["What is the difference between LLP and Pvt Ltd?", "What are the annual filing requirements for an LLP?", "Can an LLP raise funding?"],
    "startup": ["What tax exemptions do DPIIT-recognized startups get?", "What funding schemes are available for startups?", "How to apply for Startup India Seed Fund?"],
    "food_business": ["What are the different FSSAI license categories?", "What additional licenses does a restaurant need?", "How to start a cloud kitchen business?"],
    "ecommerce": ["Is GST mandatory for selling on Amazon/Flipkart?", "What are the consumer protection rules for e-commerce?", "How to start a D2C brand?"],
    "freelancer": ["How does presumptive taxation work for freelancers?", "Do freelancers need GST registration?", "How to receive international payments?"],
    "general": ["How to choose the right business structure?", "What are the MSME registration benefits?", "What funding schemes are available for new businesses?"],
}

def get_follow_ups(business_type: str) -> list[str]:
    return FOLLOW_UP_MAP.get(business_type, FOLLOW_UP_MAP["general"])


# ── Full RAG pipeline ─────────────────────────────────────────────────────────
def ask(query: str) -> dict:
    """End-to-end RAG: retrieve → format → generate → return structured result."""
    docs = search_documents(query)
    context = format_context(docs)
    answer = generate_response(query, context)
    btype = detect_business_type(query)
    sources = [d["metadata"] for d in docs]
    return {
        "answer": answer,
        "sources": sources,
        "detected_business_type": btype,
        "follow_up_questions": get_follow_ups(btype),
    }
