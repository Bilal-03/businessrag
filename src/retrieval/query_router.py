"""
Query Router — Uses LLM to extract structured metadata from user queries.
This enables automatic metadata filtering without requiring manual sidebar selection.
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()

BUSINESS_TYPES = [
    "sole_proprietorship", "partnership", "pvt_ltd", "llp", "opc",
    "startup", "msme", "food_business", "ecommerce", "import_export",
    "freelancer", "manufacturing", "healthcare", "education", "real_estate",
    "it_software", "services", "retail", "logistics", "agriculture",
    "renewable_energy", "fintech", "ngo", "general"
]

STATES = [
    "Telangana", "Karnataka", "Maharashtra", "Delhi", "Tamil Nadu", "national"
]

INTENTS = [
    "registration", "license", "tax", "compliance", "funding", "comparison", "general"
]


def extract_query_metadata(query: str) -> dict:
    """
    Uses the Groq LLM to parse a user query and extract business_type, state, and intent.
    Returns a dict with detected metadata.
    Falls back to keyword matching if LLM call fails.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        return _keyword_fallback(query)

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        system_prompt = f"""You are a metadata extraction assistant for an Indian business registration system.
Given a user query, extract:
1. business_type: one of {json.dumps(BUSINESS_TYPES)}
2. state: one of {json.dumps(STATES)}  
3. intent: one of {json.dumps(INTENTS)}

Rules:
- If the user doesn't mention a specific business type, use "general"
- If the user doesn't mention a specific state, use "national"
- If comparing business types, set intent to "comparison"
- Return ONLY valid JSON, no explanation

Example:
Query: "What licenses do I need for a restaurant in Bengaluru?"
Output: {{"business_type": "food_business", "state": "Karnataka", "intent": "license"}}

Query: "Pvt Ltd vs LLP which is better?"
Output: {{"business_type": "general", "state": "national", "intent": "comparison"}}
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}"}
            ],
            temperature=0,
            max_tokens=150
        )

        raw = response.choices[0].message.content.strip()
        # Extract JSON from the response (handle markdown code blocks)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)

        # Validate and sanitize
        if result.get("business_type") not in BUSINESS_TYPES:
            result["business_type"] = "general"
        if result.get("state") not in STATES:
            result["state"] = "national"
        if result.get("intent") not in INTENTS:
            result["intent"] = "general"

        return result

    except Exception as e:
        print(f"Query router LLM call failed: {e}. Falling back to keyword matching.")
        return _keyword_fallback(query)


def _keyword_fallback(query: str) -> dict:
    """Simple keyword-based fallback when LLM is not available."""
    query_lower = query.lower()

    # Detect business type
    business_type = "general"
    type_keywords = {
        "sole_proprietorship": ["sole prop", "proprietorship", "single owner"],
        "partnership": ["partnership", "partner firm"],
        "pvt_ltd": ["pvt ltd", "private limited", "pvt. ltd", "private company", "incorporate company"],
        "llp": ["llp", "limited liability partnership"],
        "opc": ["opc", "one person company"],
        "startup": ["startup", "start-up", "dpiit", "start up"],
        "msme": ["msme", "udyam", "micro enterprise", "small enterprise", "medium enterprise"],
        "food_business": ["food", "restaurant", "cafe", "food truck", "cloud kitchen", "catering", "fssai", "bakery"],
        "ecommerce": ["ecommerce", "e-commerce", "online store", "online business", "d2c", "marketplace", "shopify"],
        "import_export": ["import", "export", "iec", "dgft", "customs", "foreign trade"],
        "freelancer": ["freelanc", "consultant", "self-employed", "independent contractor"],
        "manufacturing": ["manufactur", "factory", "production", "industrial"],
        "healthcare": ["clinic", "hospital", "healthcare", "medical", "pharma", "drug license", "doctor"],
        "education": ["education", "coaching", "tuition", "school", "edtech", "teaching"],
        "real_estate": ["real estate", "rera", "property", "construction", "builder"],
        "it_software": ["software", "it company", "saas", "tech company", "app development"],
        "services": ["salon", "gym", "spa", "consulting", "event management", "travel agency", "co-working"],
        "retail": ["retail", "shop", "store", "franchise"],
        "logistics": ["logistics", "transport", "courier", "delivery"],
        "agriculture": ["agriculture", "farm", "agri", "organic"],
        "renewable_energy": ["solar", "wind", "renewable", "ev ", "electric vehicle"],
        "fintech": ["fintech", "digital lending", "payment", "nbfc"],
        "ngo": ["ngo", "non-profit", "trust", "society", "section 8", "charity"],
    }

    for btype, keywords in type_keywords.items():
        if any(kw in query_lower for kw in keywords):
            business_type = btype
            break

    # Detect state
    state = "national"
    state_keywords = {
        "Telangana": ["telangana", "hyderabad", "secunderabad"],
        "Karnataka": ["karnataka", "bengaluru", "bangalore", "mysore", "mysuru"],
        "Maharashtra": ["maharashtra", "mumbai", "pune", "nagpur"],
        "Delhi": ["delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida"],
        "Tamil Nadu": ["tamil nadu", "chennai", "coimbatore", "madurai"],
    }

    for st, keywords in state_keywords.items():
        if any(kw in query_lower for kw in keywords):
            state = st
            break

    # Detect intent
    intent = "general"
    intent_keywords = {
        "registration": ["register", "registration", "incorporate", "start", "setup", "how to open", "how to start"],
        "license": ["license", "licence", "permit", "noc", "clearance", "approval", "certificate"],
        "tax": ["tax", "gst", "income tax", "tds", "itr", "return filing"],
        "compliance": ["compliance", "annual filing", "penalty", "deadline", "rules", "laws"],
        "funding": ["fund", "loan", "invest", "subsidy", "grant", "mudra", "scheme", "capital"],
        "comparison": ["vs", "versus", "compare", "difference", "better", "which one", "or"],
    }

    for intent_type, keywords in intent_keywords.items():
        if any(kw in query_lower for kw in keywords):
            intent = intent_type
            break

    return {
        "business_type": business_type,
        "state": state,
        "intent": intent
    }
