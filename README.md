<div align="center">
  <img src="web/public/logo.png" alt="BizGuide AI Logo" width="96" height="96" style="border-radius: 22px;" />
  <h1>BizGuide AI</h1>
  <p><strong>Your Personal Agent for Business Compliance in India</strong></p>

  <p>
    <a href="https://businessrag.vercel.app"><img src="https://img.shields.io/badge/Live%20Demo-Vercel-black?style=for-the-badge&logo=vercel" alt="Live Demo" /></a>
    <a href="https://businessrag.onrender.com/health"><img src="https://img.shields.io/badge/API%20Status-Render-46E3B7?style=for-the-badge&logo=render" alt="API on Render" /></a>
    <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react" alt="React 19" />
    <img src="https://img.shields.io/badge/FastAPI-Python-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  </p>

  <p>
    <img src="https://img.shields.io/badge/LLM-Llama%203.3%2070B-8B5CF6?style=for-the-badge" alt="Llama 3.3" />
    <img src="https://img.shields.io/badge/Embeddings-Gemini%202-4285F4?style=for-the-badge&logo=google" alt="Gemini" />
    <img src="https://img.shields.io/badge/Vector%20DB-Pinecone-00C4B4?style=for-the-badge" alt="Pinecone" />
  </p>
</div>

---

## 🌟 What is BizGuide AI?

BizGuide AI is a **multi-agent RAG (Retrieval-Augmented Generation) system** that acts as your personal guide for Indian business compliance. Whether you're registering a company, getting an FSSAI food license, filing GST, or exploring Startup India benefits — BizGuide gives you accurate, up-to-date answers grounded in Indian law.

Unlike generic AI, BizGuide:
- **Routes your query** to a specialized agent (Legal, Tax, or General)
- **Retrieves context** from your uploaded business documents using vector search
- **Answers with markdown formatting**, citing relevant laws and regulations

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **Multi-Agent AI** | Queries are routed to Legal Agent, Tax Agent, or General Agent for specialized responses |
| 🔍 **RAG Architecture** | Pinecone vector DB + Gemini Embeddings for document-grounded answers |
| 📎 **Document Upload** | Upload your business PDFs; AI answers questions based on your actual documents |
| 🏢 **My Businesses** | Manage your business profiles with quick-ask shortcuts |
| ✅ **Compliance Checklists** | 5 interactive checklists (Pvt Ltd, GST, FSSAI, Startup India, S&E Act) with progress tracking |
| 💬 **Conversation History** | All chats saved locally — click any past conversation to restore it |
| ⚙️ **Settings** | Accent color themes, API URL config, profile management |
| 🎨 **Premium Dark UI** | Glassmorphism design with smooth Framer Motion animations |

---

## 🏗️ Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│           React Frontend            │
│  (Vite · Framer Motion · Lucide)    │
│  Deployed on: Vercel                │
└──────────────┬──────────────────────┘
               │ HTTP (REST)
               ▼
┌─────────────────────────────────────┐
│         FastAPI Backend             │
│  Deployed on: Render                │
└──────┬──────────────┬───────────────┘
       │              │
       ▼              ▼
┌─────────────┐  ┌────────────────────┐
│ Routing     │  │ Pinecone Vector DB  │
│ Agent       │  │ (Gemini Embeddings) │
│ (Llama 3.3) │  │ k=4 similarity      │
└──────┬──────┘  └────────────────────┘
       │
       ▼
┌──────────────────────┐
│ Specialized Agent    │
│ ┌──────────────────┐ │
│ │  Legal Agent     │ │  → Indian Company Law, FSSAI, MCA
│ │  Tax Agent       │ │  → GST, Income Tax, Startup India
│ │  General Agent   │ │  → Business guidance & planning
│ └──────────────────┘ │
│   (Llama 3.3 70B)    │
└──────────────────────┘
```

---

## 🛠️ Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| **React 19** | UI framework |
| **Vite 8** | Build tool & dev server |
| **Framer Motion** | Animations & transitions |
| **Lucide React** | Icon library |
| **React Markdown** | Render AI markdown responses |

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | REST API framework |
| **Groq API** | LLM inference (Llama 3.3 70B) |
| **Pinecone** | Vector database for RAG |
| **Google Gemini** | Embeddings (`gemini-embedding-2`, 3072 dim) |
| **LangChain** | Document loading, splitting, vector store |
| **PyPDF** | PDF parsing |

---

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- API keys for: Groq, Pinecone, Google Gemini

### 1. Clone the repository
```bash
git clone https://github.com/Bilal-03/businessrag.git
cd businessrag
```

### 2. Backend Setup
```bash
# Copy and fill in your API keys
cp .env.example .env

# Create and activate a Python virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r api/requirements.txt

# Start the FastAPI server
uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### 3. Frontend Setup
```bash
cd web
npm install
npm run dev
```

The app will open at `http://localhost:5173`

> **Note:** By default the frontend points to `https://businessrag.onrender.com`. To use your local backend, go to **Settings → API & Data** and change the URL to `http://localhost:8000`.

---

## 🔑 Environment Variables

Create a `.env` file in the root directory:

```env
# LLM Inference (Groq)
GROQ_API_KEY=gsk_...

# Vector Database (Pinecone)
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=bizguide-index

# Embeddings (Google Gemini)
GEMINI_API_KEY=...
```

See [`.env.example`](.env.example) for the full template.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Send a query, get AI response |
| `POST` | `/api/documents/upload` | Upload a PDF for RAG indexing |
| `GET` | `/health` | Health check |

### Chat Request
```json
POST /api/chat
{
  "query": "How do I register a Private Limited Company in India?"
}
```

### Chat Response
```json
{
  "answer": "**Legal Agent Response:**\n\n## Company Registration Steps\n\n1. Obtain DSC for all directors..."
}
```

### Document Upload
```bash
curl -X POST https://businessrag.onrender.com/api/documents/upload \
  -F "file=@your-document.pdf"
```

---

## 🗂️ Project Structure

```
businessrag/
├── api/
│   ├── main.py              # FastAPI app — routing, agents, RAG
│   └── requirements.txt     # Python dependencies
├── web/
│   ├── public/
│   │   └── logo.png         # BizGuide AI logo
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar.jsx       # Navigation with conversation history
│   │   │   ├── Logo.jsx          # Logo component
│   │   │   ├── MyBusinesses.jsx  # Business profile manager
│   │   │   ├── UploadDocuments.jsx # Drag-drop PDF upload
│   │   │   ├── Checklists.jsx    # Compliance checklists
│   │   │   └── Settings.jsx      # App settings
│   │   ├── App.jsx          # Root — view routing, chat logic
│   │   ├── App.css          # All component styles
│   │   ├── index.css        # Global styles & design tokens
│   │   └── main.jsx         # React entry point
│   ├── index.html
│   └── package.json
├── .env.example             # Environment variable template
├── Dockerfile               # Container configuration
└── README.md
```

---

## 🧩 Compliance Checklists

BizGuide includes interactive, checkable compliance checklists for:

1. **Private Limited Company Registration** — DSC, DIN, SPICe+ form, COI
2. **GST Registration** — REG-01, Aadhaar auth, GSTIN
3. **FSSAI Food License** — Basic/State/Central, FoSCoS portal
4. **Startup India (DPIIT)** — Recognition, 80-IAC tax exemption
5. **Shop & Establishment Act** — State-wise registration

All checklist progress is saved in your browser's localStorage.

---

## 🚢 Deployment

### Frontend — Vercel
The React frontend is deployed on **Vercel** with automatic deployments on every push to `main`.

**Live URL:** `https://businessrag.vercel.app`

### Backend — Render
The FastAPI backend is deployed on **Render** (free tier).

**API URL:** `https://businessrag.onrender.com`

> ⚠️ **Note on Render Free Tier:** The backend may take 30–60 seconds to respond on the first request after a period of inactivity (cold start). Subsequent requests are fast.

### Docker
```bash
docker build -t bizguide-api .
docker run -p 8000:8000 --env-file .env bizguide-api
```

---

## 🛣️ Roadmap

- [ ] User authentication (Supabase)
- [ ] Multi-language support (Hindi, Telugu, Tamil)
- [ ] Real-time government notification scraper
- [ ] Business document templates (MOA, AOA, MoU)
- [ ] Chartered Accountant referral network integration
- [ ] Mobile app (React Native)

---

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

```bash
# Fork the repo, then:
git checkout -b feature/your-feature
git commit -m "feat: add your feature"
git push origin feature/your-feature
# Open a Pull Request
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <p>Built with ❤️ for Indian entrepreneurs navigating the complex world of business compliance.</p>
  <br/>
  <p>
    <strong>Created by <a href="https://github.com/Bilal-03">Bilal</a></strong>
  </p>
  <p>
    <a href="https://businessrag.vercel.app">🌐 Live Demo</a> ·
    <a href="https://github.com/Bilal-03">👤 GitHub</a> ·
    <a href="https://github.com/Bilal-03/businessrag/issues">🐛 Report Bug</a> ·
    <a href="https://github.com/Bilal-03/businessrag/issues">💡 Request Feature</a>
  </p>
</div>
