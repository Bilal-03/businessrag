# Business Registration RAG System 🚀

A powerful conversational agent designed to help users navigate the complex landscape of business registration and compliance in India. Built with a state-of-the-art **Retrieval-Augmented Generation (RAG)** architecture, it delivers accurate, context-aware answers to user queries, currently specializing in food truck businesses in Telangana.

## 🌟 Key Features
- **Accurate Information Retrieval**: Uses ChromaDB and Sentence Transformers for fast, local vector search.
- **Fast Generation**: Powered by the Groq API for rapid LLM responses.
- **Modern Architecture**: Decoupled FastAPI backend and an interactive Streamlit frontend.
- **Scalable**: Easily extensible to other business types and states.

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python)
- **Frontend**: Streamlit
- **Vector Database**: ChromaDB
- **Embeddings**: Sentence Transformers (`all-MiniLM-L6-v2`)
- **LLM**: Groq API (Llama 3 or similar)

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- A Groq API Key

### Local Setup
1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd businessrag
   ```
2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables**:
   Copy `.env.example` to `.env` and add your Groq API key:
   ```bash
   cp .env.example .env
   ```

### Running the Application Locally
You need to run both the backend and frontend servers simultaneously.

**Start the Backend**:
```bash
uvicorn src.api.main:app --reload
```
The backend API will be available at `http://localhost:8000`.

**Start the Frontend**:
Open a new terminal, activate the environment, and run:
```bash
streamlit run frontend/streamlit_app.py
```
The frontend UI will be available at `http://localhost:8501`.

## 🌐 Deployment Recommendations
To make this application available online, we recommend a decoupled deployment approach:

- **Backend (FastAPI)**: Deploy on [Render](https://render.com/) (Web Service) or [Railway](https://railway.app/). They offer seamless deployment from GitHub and easy environment variable management.
- **Frontend (Streamlit)**: Deploy on [Streamlit Community Cloud](https://streamlit.io/cloud) or [Render](https://render.com/). Streamlit Community Cloud is free and specifically optimized for Streamlit apps.

## 📄 License
This project is licensed under the MIT License.
