# 🧠 Agora AI Debate Engine

An AI-powered debate system that simulates real-world competitive debating with intelligent agents.

---

## 🚀 Features (Phase 1)

* ✅ Create debate matches via API
* ✅ AI-powered case preparation (Prep Coach)
* ✅ Structured argument generation (JSON)
* ✅ Embedding generation using Cohere
* ✅ Vector storage using pgvector
* ✅ PostgreSQL-backed data models
* ✅ Clean layered architecture (API → Service → Repository → AI)

---

## 🏗️ Tech Stack

* **Backend:** FastAPI
* **Database:** PostgreSQL + SQLAlchemy
* **Vector DB:** pgvector
* **LLM:** Groq (LLaMA 3)
* **Embeddings:** Cohere
* **Cache/Queue (future):** Redis
* **Migrations:** Alembic

---

## 📂 Project Structure

```
src/
 ├── api/           # FastAPI routes
 ├── ai/            # Agents, prompts, LLM clients
 ├── core/          # Config, DB, Redis
 ├── models/        # SQLAlchemy models
 ├── repositories/  # DB logic
 ├── services/      # Business logic
 ├── workers/       # Background jobs (future)
```

---

## ⚙️ Setup Instructions

### 1. Clone repo

```bash
git clone https://github.com/YOUR_USERNAME/agora-ai-engine.git
cd agora-ai-engine
```

---

### 2. Create virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Setup environment variables

Create `.env` file:

```
DATABASE_URL=your_postgres_url
REDIS_URL=your_redis_url

OPENAI_API_KEY=...
COHERE_API_KEY=...
GROQ_API_KEY=...
```

---

### 5. Run server

```bash
uvicorn main:app --reload
```

---

## 📡 API Endpoints

### ▶ Start Match

**POST** `/matches/start`

```json
{
  "motion_text": "Ban AI in education",
  "side": "Opposition",
  "format": "Asian Parliamentary",
  "user_id": "UUID"
}
```

---

## 🧠 How It Works

1. User starts a match
2. System creates:

   * Motion
   * Debate Session
   * Case Prep
3. AI Prep Coach:

   * Generates arguments (LLM)
   * Stores structured JSON
4. Embeddings generated via Cohere
5. Stored in pgvector

---

## 🧪 Testing

```bash
pytest
```

---

## 📌 Phase Roadmap

### ✅ Phase 1 (Completed)

* Core backend
* AI prep system
* Embeddings

### 🚧 Phase 2 (Next)

* Real-time debate engine
* AI opponent
* Turn system

---

## 👨‍💻 Author

Built by **Maha Kisore**
B.Tech CSE (AI Specialization)

---

## ⭐ Future Scope

* Live debate UI
* Speech-to-text integration
* AI adjudicator
* Performance analytics

---  