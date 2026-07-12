import streamlit as st
import requests
import time

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BizGuide India — Business Registration & Compliance Assistant",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Premium CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── Global Overrides ─────────────────────────────────────── */
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #111827 50%, #0f172a 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ── Sidebar ──────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #1e293b 100%);
        border-right: 1px solid rgba(99, 102, 241, 0.15);
    }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown li {
        color: #94a3b8 !important;
    }
    [data-testid="stSidebar"] label {
        color: #cbd5e1 !important;
    }

    /* ── Hero Section ─────────────────────────────────────────── */
    .hero-container {
        text-align: center;
        padding: 2rem 1rem 1.5rem;
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #818cf8, #6366f1, #a78bfa, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        line-height: 1.2;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        font-weight: 400;
        max-width: 600px;
        margin: 0 auto 0.5rem;
        line-height: 1.6;
    }
    .hero-badge {
        display: inline-block;
        padding: 0.3rem 0.9rem;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 20px;
        color: #a5b4fc;
        font-size: 0.75rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        margin-top: 0.5rem;
    }

    /* ── Category Cards ───────────────────────────────────────── */
    .category-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        gap: 0.75rem;
        padding: 0.5rem 0;
    }
    .category-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.1);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        backdrop-filter: blur(10px);
    }
    .category-card:hover {
        background: rgba(99, 102, 241, 0.15);
        border-color: rgba(99, 102, 241, 0.4);
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(99, 102, 241, 0.15);
    }
    .category-icon {
        font-size: 1.8rem;
        margin-bottom: 0.4rem;
    }
    .category-label {
        font-size: 0.78rem;
        color: #e2e8f0;
        font-weight: 500;
        line-height: 1.3;
    }

    /* ── Suggestion Chips ─────────────────────────────────────── */
    .suggestions-container {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        justify-content: center;
        padding: 0.5rem 0;
    }
    .suggestion-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.5rem 1rem;
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(99, 102, 241, 0.15);
        border-radius: 20px;
        color: #cbd5e1;
        font-size: 0.8rem;
        font-weight: 400;
        cursor: pointer;
        transition: all 0.2s ease;
        text-decoration: none;
    }
    .suggestion-chip:hover {
        background: rgba(99, 102, 241, 0.2);
        border-color: rgba(99, 102, 241, 0.4);
        color: #e2e8f0;
    }

    /* ── Chat Messages ────────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        background: rgba(30, 41, 59, 0.4) !important;
        border: 1px solid rgba(99, 102, 241, 0.08) !important;
        border-radius: 16px !important;
        backdrop-filter: blur(10px) !important;
        padding: 1rem !important;
        margin-bottom: 0.75rem !important;
    }
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span {
        color: #e2e8f0 !important;
    }
    [data-testid="stChatMessage"] strong {
        color: #a5b4fc !important;
    }
    [data-testid="stChatMessage"] h1,
    [data-testid="stChatMessage"] h2,
    [data-testid="stChatMessage"] h3 {
        color: #c4b5fd !important;
    }
    [data-testid="stChatMessage"] code {
        color: #fbbf24 !important;
        background: rgba(251, 191, 36, 0.1) !important;
    }
    [data-testid="stChatMessage"] a {
        color: #818cf8 !important;
    }
    [data-testid="stChatMessage"] blockquote {
        border-left: 3px solid #6366f1;
        padding-left: 1rem;
        color: #94a3b8 !important;
        background: rgba(99, 102, 241, 0.05);
        border-radius: 0 8px 8px 0;
        padding: 0.5rem 1rem;
    }

    /* ── Chat Input ───────────────────────────────────────────── */
    [data-testid="stChatInput"] {
        border-color: rgba(99, 102, 241, 0.3) !important;
    }
    [data-testid="stChatInput"] textarea {
        background: rgba(30, 41, 59, 0.8) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(99, 102, 241, 0.2) !important;
        border-radius: 12px !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: rgba(99, 102, 241, 0.5) !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1) !important;
    }

    /* ── Expander (Sources) ───────────────────────────────────── */
    .streamlit-expanderHeader {
        background: rgba(30, 41, 59, 0.6) !important;
        border: 1px solid rgba(99, 102, 241, 0.15) !important;
        border-radius: 10px !important;
        color: #a5b4fc !important;
    }
    .streamlit-expanderContent {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(99, 102, 241, 0.1) !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
    }

    /* ── Source Card ───────────────────────────────────────────── */
    .source-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(99, 102, 241, 0.12);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
    }
    .source-card:hover {
        border-color: rgba(99, 102, 241, 0.3);
        background: rgba(99, 102, 241, 0.08);
    }
    .source-authority {
        color: #818cf8;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .source-meta {
        color: #64748b;
        font-size: 0.72rem;
        margin-top: 0.2rem;
    }
    .source-link {
        color: #6366f1;
        font-size: 0.75rem;
        text-decoration: none;
    }
    .source-link:hover {
        color: #818cf8;
        text-decoration: underline;
    }

    /* ── Follow-up Chips ──────────────────────────────────────── */
    .followup-container {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
        padding-top: 0.75rem;
        border-top: 1px solid rgba(99, 102, 241, 0.1);
    }
    .followup-label {
        color: #94a3b8;
        font-size: 0.78rem;
        font-weight: 500;
        width: 100%;
        margin-bottom: 0.25rem;
    }
    .followup-chip {
        display: inline-block;
        padding: 0.4rem 0.85rem;
        background: rgba(99, 102, 241, 0.1);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 18px;
        color: #a5b4fc;
        font-size: 0.78rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .followup-chip:hover {
        background: rgba(99, 102, 241, 0.2);
        border-color: rgba(99, 102, 241, 0.4);
    }

    /* ── Stats Bar ────────────────────────────────────────────── */
    .stats-bar {
        display: flex;
        justify-content: center;
        gap: 2rem;
        padding: 1rem 0;
        margin: 0.5rem 0;
    }
    .stat-item {
        text-align: center;
    }
    .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #818cf8;
    }
    .stat-label {
        font-size: 0.7rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }

    /* ── Section Headers ──────────────────────────────────────── */
    .section-header {
        color: #94a3b8;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 1rem 0 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid rgba(99, 102, 241, 0.1);
    }

    /* ── Detected Intent Badge ────────────────────────────────── */
    .intent-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.2rem 0.6rem;
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 12px;
        color: #a5b4fc;
        font-size: 0.7rem;
        font-weight: 500;
        margin: 0.15rem;
    }

    /* ── Selectbox styling ────────────────────────────────────── */
    [data-testid="stSelectbox"] label {
        color: #cbd5e1 !important;
    }

    /* ── Divider ──────────────────────────────────────────────── */
    hr {
        border-color: rgba(99, 102, 241, 0.1) !important;
    }

    /* ── Quick Action Buttons ─────────────────────────────────── */
    .quick-action {
        display: block;
        width: 100%;
        padding: 0.6rem 0.8rem;
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(99, 102, 241, 0.12);
        border-radius: 8px;
        color: #cbd5e1;
        font-size: 0.78rem;
        text-align: left;
        cursor: pointer;
        transition: all 0.2s ease;
        margin-bottom: 0.4rem;
        text-decoration: none;
    }
    .quick-action:hover {
        background: rgba(99, 102, 241, 0.15);
        border-color: rgba(99, 102, 241, 0.35);
        color: #e2e8f0;
    }
    .quick-action-icon {
        margin-right: 0.4rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── API Config ────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

def fetch_api(endpoint, method="GET", json_data=None):
    """Helper to call the backend API."""
    try:
        if method == "GET":
            resp = requests.get(f"{API_BASE}{endpoint}", timeout=30)
        else:
            resp = requests.post(f"{API_BASE}{endpoint}", json=json_data, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None

# ─── Load dynamic data from API ───────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_business_types():
    data = fetch_api("/api/business-types")
    if data:
        return data.get("business_types", [])
    return []

@st.cache_data(ttl=300)
def load_states():
    data = fetch_api("/api/states")
    if data:
        return data.get("states", [])
    return []

@st.cache_data(ttl=300)
def load_suggestions():
    data = fetch_api("/api/suggestions")
    if data:
        return data.get("suggestions", [])
    return []

# ─── Session State Init ───────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_query" not in st.session_state:
    st.session_state.selected_query = None

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🇮🇳 BizGuide India")
    st.markdown('<p style="color: #64748b; font-size: 0.8rem;">AI-powered business registration & compliance assistant</p>', unsafe_allow_html=True)

    st.markdown("---")
    

    
    # Quick Actions
    st.markdown('<div class="section-header">⚡ Quick Actions</div>', unsafe_allow_html=True)
    
    quick_actions = [
        ("🏢", "Register a Pvt Ltd Company"),
        ("📊", "GST registration steps"),
        ("📋", "Choose right business structure"),
        ("🚀", "Startup India benefits"),
        ("💰", "Funding schemes for new businesses"),
        ("⚖️", "LLP vs Pvt Ltd comparison"),
    ]
    
    for icon, action in quick_actions:
        if st.button(f"{icon}  {action}", key=f"qa_{action}", use_container_width=True):
            st.session_state.selected_query = action

    st.markdown("---")
    
    # Info
    st.markdown("""
    <div style="padding: 0.75rem; background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.15); border-radius: 10px; margin-top: 0.5rem;">
        <p style="color: #a5b4fc; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.3rem;">📌 Coverage</p>
        <p style="color: #64748b; font-size: 0.7rem; margin: 0; line-height: 1.5;">
            15+ business types • 5 states + national<br>
            GST • Income Tax • Labour Law • IP • Funding
        </p>
    </div>
    """, unsafe_allow_html=True)


# ─── Main Content ─────────────────────────────────────────────────────────────

# Show hero + categories only if no messages yet
if not st.session_state.messages:
    # Hero
    st.markdown("""
    <div class="hero-container">
        <div class="hero-title">BizGuide India</div>
        <div class="hero-subtitle">
            Your AI-powered assistant for business registration, licensing, taxation & compliance across India
        </div>
        <div class="hero-badge">✨ Powered by RAG • 15+ Business Types • 5+ States</div>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    st.markdown("""
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-value">15+</div>
            <div class="stat-label">Business Types</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">90+</div>
            <div class="stat-label">Knowledge Chunks</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">5+</div>
            <div class="stat-label">States Covered</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">20+</div>
            <div class="stat-label">Govt Authorities</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Category Cards
    st.markdown('<div class="section-header">🗂️ Explore by Business Type</div>', unsafe_allow_html=True)
    
    display_categories = [
        ("🏢", "Pvt Ltd Company", "pvt_ltd"),
        ("⚖️", "LLP", "llp"),
        ("👤", "Sole Proprietorship", "sole_proprietorship"),
        ("🍽️", "Food Business", "food_business"),
        ("🛒", "E-Commerce", "ecommerce"),
        ("💻", "Freelancer", "freelancer"),
        ("🚀", "Startup India", "startup"),
        ("🏭", "Manufacturing", "manufacturing"),
        ("🏥", "Healthcare", "healthcare"),
        ("📚", "Education", "education"),
        ("🏗️", "Real Estate", "real_estate"),
        ("💡", "IT / Software", "it_software"),
    ]
    
    cols = st.columns(6)
    for i, (icon, label, btype) in enumerate(display_categories):
        with cols[i % 6]:
            if st.button(f"{icon}\n{label}", key=f"cat_{btype}", use_container_width=True):
                st.session_state.selected_query = f"What are the requirements to start a {label} in India?"

    st.markdown("")
    
    # Popular Suggestions
    st.markdown('<div class="section-header">💡 Popular Questions</div>', unsafe_allow_html=True)
    
    suggestions = load_suggestions()
    if suggestions:
        # Show in rows of 3
        suggestion_cols = st.columns(3)
        for i, sugg in enumerate(suggestions[:9]):
            with suggestion_cols[i % 3]:
                if st.button(f"{sugg['icon']}  {sugg['query'][:60]}{'...' if len(sugg['query']) > 60 else ''}", 
                           key=f"sugg_{i}", use_container_width=True):
                    st.session_state.selected_query = sugg["query"]

# ─── Chat History ─────────────────────────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Show sources if present
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander("📚 Sources Consulted", expanded=False):
                for src in message["sources"]:
                    authority = src.get('authority', 'Unknown')
                    biz_type = src.get('business_type', 'N/A').replace('_', ' ').title()
                    state = src.get('state', 'N/A')
                    url = src.get('source_url', '#')
                    doc_type = src.get('doc_type', 'N/A').title()
                    st.markdown(f"""
                    <div class="source-card">
                        <div class="source-authority">{authority}</div>
                        <div class="source-meta">{biz_type} • {state} • {doc_type}</div>
                        <a class="source-link" href="{url}" target="_blank">🔗 {url}</a>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Show follow-up questions
        if message["role"] == "assistant" and message.get("follow_ups"):
            st.markdown('<div class="followup-label">📌 Related questions:</div>', unsafe_allow_html=True)
            fu_cols = st.columns(len(message["follow_ups"]))
            for j, fq in enumerate(message["follow_ups"]):
                with fu_cols[j]:
                    if st.button(f"→ {fq[:50]}{'...' if len(fq) > 50 else ''}", 
                               key=f"fu_{message.get('idx', 0)}_{j}", use_container_width=True):
                        st.session_state.selected_query = fq

# ─── Handle selected query (from buttons) ─────────────────────────────────────
prompt = st.chat_input("Ask anything about starting or running a business in India...")

# If a query was selected from a button, use it
if st.session_state.selected_query:
    prompt = st.session_state.selected_query
    st.session_state.selected_query = None

if prompt:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        # Animated loading
        with st.spinner("🔍 Analyzing your query & retrieving relevant information..."):
            # Build API request
            payload = {"query": prompt}
            
            try:
                response = requests.post(f"{API_BASE}/api/chat", json=payload, timeout=60)
                response.raise_for_status()
                data = response.json()
                
                answer = data.get("answer", "I couldn't find a relevant answer. Please try rephrasing your question.")
                sources = data.get("sources", [])
                follow_ups = data.get("follow_up_questions", [])
                detected_biz = data.get("detected_business_type")
                detected_state = data.get("detected_state")
                detected_intent = data.get("detected_intent")
                
                # Show detected intent badges
                intent_info = ""
                if detected_biz and detected_biz != "general":
                    intent_info += f'<span class="intent-badge">🏢 {detected_biz.replace("_", " ").title()}</span>'
                if detected_state and detected_state != "national":
                    intent_info += f'<span class="intent-badge">📍 {detected_state}</span>'
                if detected_intent and detected_intent != "general":
                    intent_info += f'<span class="intent-badge">🎯 {detected_intent.title()}</span>'
                
                if intent_info:
                    st.markdown(f'<div style="margin-bottom: 0.5rem;">{intent_info}</div>', unsafe_allow_html=True)
                
                # Display answer
                message_placeholder.markdown(answer)
                
                # Show sources
                if sources:
                    unique_sources = []
                    seen = set()
                    for s in sources:
                        key = s.get('authority', '') + s.get('source_url', '')
                        if key not in seen:
                            seen.add(key)
                            unique_sources.append(s)
                    
                    with st.expander("📚 Sources Consulted", expanded=False):
                        for src in unique_sources:
                            authority = src.get('authority', 'Unknown')
                            biz_type = src.get('business_type', 'N/A').replace('_', ' ').title()
                            state = src.get('state', 'N/A')
                            url = src.get('source_url', '#')
                            doc_type = src.get('doc_type', 'N/A').title()
                            st.markdown(f"""
                            <div class="source-card">
                                <div class="source-authority">{authority}</div>
                                <div class="source-meta">{biz_type} • {state} • {doc_type}</div>
                                <a class="source-link" href="{url}" target="_blank">🔗 {url}</a>
                            </div>
                            """, unsafe_allow_html=True)
                
                # Add disclaimer
                st.markdown("""
                > ⚠️ *Disclaimer: This information is AI-generated from official sources and is for guidance only. 
                > Always verify with official government portals and consult a CA/CS/legal advisor before acting on this information.*
                """)
                
                # Follow-up questions
                if follow_ups:
                    st.markdown('<div class="followup-label">📌 You might also want to know:</div>', unsafe_allow_html=True)
                    fu_cols = st.columns(min(len(follow_ups), 3))
                    msg_idx = len(st.session_state.messages)
                    for j, fq in enumerate(follow_ups):
                        with fu_cols[j % 3]:
                            if st.button(f"→ {fq}", key=f"fu_new_{msg_idx}_{j}", use_container_width=True):
                                st.session_state.selected_query = fq
                                st.rerun()
                
                # Save to session
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": unique_sources if sources else [],
                    "follow_ups": follow_ups,
                    "idx": len(st.session_state.messages)
                })
                
            except requests.exceptions.ConnectionError:
                error_msg = "🔴 **Cannot connect to the backend server.**\n\nPlease make sure FastAPI is running:\n```bash\nbash run_api.sh\n```"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except Exception as e:
                error_msg = f"⚠️ **Error:** {str(e)}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# ─── Footer ───────────────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 1rem; color: #475569; font-size: 0.72rem;">
        Built with ❤️ using RAG (Retrieval-Augmented Generation) • FastAPI • ChromaDB • Groq LLM<br>
        Always verify information with official government portals
    </div>
    """, unsafe_allow_html=True)
