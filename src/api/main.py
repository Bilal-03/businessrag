import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.schemas import ChatRequest, ChatResponse, SuggestionResponse
from src.retrieval.hybrid_search import search_documents, format_docs
from src.retrieval.query_router import extract_query_metadata, BUSINESS_TYPES, STATES
from src.generation.llm_client import generate_response

app = FastAPI(title="Business Registration RAG API", version="2.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Business type display info for frontend
BUSINESS_TYPE_INFO = [
    {"id": "sole_proprietorship", "label": "Sole Proprietorship", "icon": "👤", "description": "Simplest single-owner business"},
    {"id": "partnership", "label": "Partnership Firm", "icon": "🤝", "description": "Two or more partners sharing profits"},
    {"id": "pvt_ltd", "label": "Private Limited (Pvt. Ltd.)", "icon": "🏢", "description": "Best for startups seeking investment"},
    {"id": "llp", "label": "LLP", "icon": "⚖️", "description": "Limited liability for partners"},
    {"id": "opc", "label": "One Person Company", "icon": "1️⃣", "description": "Solo founder with limited liability"},
    {"id": "startup", "label": "Startup India", "icon": "🚀", "description": "DPIIT recognition and benefits"},
    {"id": "msme", "label": "MSME / Udyam", "icon": "🏭", "description": "Micro, Small & Medium Enterprise benefits"},
    {"id": "food_business", "label": "Food Business", "icon": "🍽️", "description": "Restaurant, food truck, cloud kitchen, catering"},
    {"id": "ecommerce", "label": "E-Commerce", "icon": "🛒", "description": "Online store, marketplace, D2C brand"},
    {"id": "import_export", "label": "Import / Export", "icon": "🌍", "description": "International trade and customs"},
    {"id": "freelancer", "label": "Freelancer / Consultant", "icon": "💻", "description": "Independent professional services"},
    {"id": "manufacturing", "label": "Manufacturing", "icon": "⚙️", "description": "Factory, production, industrial"},
    {"id": "healthcare", "label": "Healthcare / Clinic", "icon": "🏥", "description": "Hospital, clinic, pharmacy, lab"},
    {"id": "education", "label": "Education / Coaching", "icon": "📚", "description": "School, coaching, EdTech"},
    {"id": "real_estate", "label": "Real Estate", "icon": "🏗️", "description": "Construction, RERA, property development"},
    {"id": "it_software", "label": "IT / Software", "icon": "💡", "description": "SaaS, tech company, app development"},
    {"id": "services", "label": "Services", "icon": "🛎️", "description": "Salon, gym, travel, events, consulting"},
    {"id": "retail", "label": "Retail / Shop", "icon": "🏪", "description": "Physical store, franchise"},
    {"id": "logistics", "label": "Logistics / Transport", "icon": "🚚", "description": "Courier, fleet, transportation"},
    {"id": "ngo", "label": "NGO / Non-Profit", "icon": "🤲", "description": "Trust, society, Section 8 company"},
    {"id": "general", "label": "General / Other", "icon": "📋", "description": "Cross-cutting topics like GST, PAN, compliance"},
]

STATE_INFO = [
    {"id": "national", "label": "Pan-India (National)", "icon": "🇮🇳"},
    {"id": "Telangana", "label": "Telangana", "icon": "🏛️"},
    {"id": "Karnataka", "label": "Karnataka", "icon": "🏛️"},
    {"id": "Maharashtra", "label": "Maharashtra", "icon": "🏛️"},
    {"id": "Delhi", "label": "Delhi", "icon": "🏛️"},
    {"id": "Tamil Nadu", "label": "Tamil Nadu", "icon": "🏛️"},
]

POPULAR_SUGGESTIONS = [
    {"query": "How to register a Private Limited Company in India?", "category": "Registration", "icon": "🏢"},
    {"query": "What is the difference between LLP and Pvt Ltd?", "category": "Comparison", "icon": "⚖️"},
    {"query": "Steps to get GST registration", "category": "Tax", "icon": "📊"},
    {"query": "How to get FSSAI license for a restaurant?", "category": "Food Business", "icon": "🍽️"},
    {"query": "What are the benefits of Startup India registration?", "category": "Startup", "icon": "🚀"},
    {"query": "How to register as an MSME on Udyam portal?", "category": "MSME", "icon": "🏭"},
    {"query": "What licenses do I need for an e-commerce business?", "category": "E-Commerce", "icon": "🛒"},
    {"query": "Tax compliance for freelancers in India", "category": "Freelancer", "icon": "💻"},
    {"query": "What funding schemes are available for women entrepreneurs?", "category": "Funding", "icon": "💰"},
    {"query": "How to choose the right business structure?", "category": "General", "icon": "📋"},
    {"query": "What are the annual compliance requirements for a Pvt Ltd company?", "category": "Compliance", "icon": "📅"},
    {"query": "How to get an Import Export Code (IEC)?", "category": "Import/Export", "icon": "🌍"},
]


@app.get("/api/business-types")
async def get_business_types():
    """Returns all supported business types with display info."""
    return {"business_types": BUSINESS_TYPE_INFO}


@app.get("/api/states")
async def get_states():
    """Returns all supported states with display info."""
    return {"states": STATE_INFO}


@app.get("/api/suggestions")
async def get_suggestions():
    """Returns popular/suggested queries for the landing page."""
    return {"suggestions": POPULAR_SUGGESTIONS}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # 1. Smart query routing — detect business_type, state, intent from the query
    detected = extract_query_metadata(request.query)
    
    # 3. Retrieve documents
    docs = search_documents(request.query)
    
    # 4. Format context
    context = format_docs(docs)
    
    # 5. Generate response
    if os.getenv("GROQ_API_KEY") and os.getenv("GROQ_API_KEY") != "your_groq_api_key_here":
        answer = generate_response(request.query, context)
    else:
        answer = f"⚠️ **No API Key configured.** Returning retrieved context:\n\n{context}"
    
    # 6. Extract sources for metadata
    sources = [d.metadata for d in docs]
    
    # 7. Generate follow-up suggestions based on detected intent
    follow_ups = _generate_follow_ups(detected)
    
    return ChatResponse(
        answer=answer,
        sources=sources,
        detected_business_type=detected.get("business_type"),
        detected_state=detected.get("state"),
        detected_intent=detected.get("intent"),
        follow_up_questions=follow_ups
    )


def _generate_follow_ups(detected: dict) -> list[str]:
    """Generates contextual follow-up question suggestions."""
    btype = detected.get("business_type", "general")
    intent = detected.get("intent", "general")
    
    follow_up_map = {
        "sole_proprietorship": [
            "What tax returns does a sole proprietor need to file?",
            "How to convert sole proprietorship to Pvt Ltd?",
            "What are the GST rules for sole proprietors?",
        ],
        "pvt_ltd": [
            "What is the annual compliance calendar for a Pvt Ltd?",
            "How much does it cost to incorporate a Pvt Ltd?",
            "What are the penalties for non-compliance?",
        ],
        "llp": [
            "What is the difference between LLP and Pvt Ltd?",
            "What are the annual filing requirements for an LLP?",
            "Can an LLP raise funding from investors?",
        ],
        "startup": [
            "What tax exemptions do DPIIT-recognized startups get?",
            "What funding schemes are available for startups?",
            "How to apply for Startup India Seed Fund?",
        ],
        "food_business": [
            "What are the different FSSAI license categories?",
            "What additional licenses does a restaurant need?",
            "How to start a cloud kitchen business?",
        ],
        "ecommerce": [
            "Is GST mandatory for selling on Amazon/Flipkart?",
            "What are the consumer protection rules for e-commerce?",
            "How to start a D2C brand in India?",
        ],
        "freelancer": [
            "How does presumptive taxation work for freelancers?",
            "Do freelancers need GST registration?",
            "How to receive international payments as a freelancer?",
        ],
        "general": [
            "How to choose the right business structure?",
            "What are the MSME registration benefits?",
            "What funding schemes are available for new businesses?",
        ],
    }
    
    return follow_up_map.get(btype, follow_up_map["general"])
