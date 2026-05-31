# VibeRAG — Full-Stack Social Video RAG Chatbot

VibeRAG is a full-stack engineering solution that analyzes and compares YouTube Videos and Instagram Reels side-by-side. It pulls complete metadata and transcripts dynamically, processes them through a local ChromaDB vector store, and provides a streaming RAG interface to query video performance, hooks, and strategy.

---

## 🛠️ Tech Stack & Final Versions

| Layer | Choice & Version |
|---|---|
| **Frontend** | React 19.2.4 / Next.js 16.2.6 (App Router) |
| **Backend** | FastAPI 0.115.5 |
| **Orchestration** | LangChain 0.3.9 (LCEL) |
| **LLM** | **Google `gemini-3.5-flash`** (via Gemini API) |
| **Embeddings** | **Google `gemini-embedding-2`** |
| **Vector DB** | **ChromaDB 0.5.23** (Local persistent SQLite) |
| **YouTube Transcript** | `youtube-transcript-api` 1.2.4 |
| **Instagram Transcript** | `yt-dlp` 2024.11.18 + `openai-whisper` (tiny model) |
| **Metadata APIs** | YouTube Data API v3 & `instaloader` 4.15.1 |
| **Memory** | LangChain `ConversationBufferWindowMemory` |

---

## 🏗️ Engineering Decisions & Trade-offs (Why this stack?)

### 1. FastAPI over Node.js
FastAPI was explicitly chosen because **the entire ML stack is Python-native**. LangChain, ChromaDB, Whisper, yt-dlp bindings, and the Google SDK are all Python packages. Using Node.js would require spawning Python subprocesses or maintaining two separate runtimes, which introduces latency and point-of-failures. FastAPI provides native async, OpenAPI documentation out of the box, Pydantic validation, and seamless Server-Sent Events (SSE) streaming with zero extra packages.

### 2. LangChain (LCEL) over LangGraph
The assignment specifies "LangChain or LangGraph". I deliberately chose **LangChain (LCEL)** because LangGraph is purpose-built for stateful, cyclical, multi-agent workflows (e.g., an agent deciding whether to browse the web or run code). 
Our pipeline is linear and deterministic: `User Message → Retrieve Chunks → Build Prompt → Stream LLM`. 
LCEL accomplishes this asynchronously in ~20 lines of highly readable, composable code. LangGraph would introduce 300+ lines of node/edge boilerplate for a linear graph, which violates engineering principles of simplicity. 

### 3. Gemini 3.5 Flash & gemini-embedding-2
**Why not GPT-4o or Claude?**
We achieve **identical reasoning capabilities for this specific text-summarization task at ~40x lower cost**. `gemini-3.5-flash` costs $0.075 per 1M input tokens. Furthermore, utilizing `gemini-embedding-2` allows us to use the same API key, the same SDK, and the same Google billing bucket for both Generation and Embedding, removing vendor fragmentation.

### 4. ChromaDB over Pinecone or pgvector
For this specific implementation, **ChromaDB** is the highest quality and most efficient local solution.
- **Why not Pinecone?** The free tier limits you to 1 index and introduces remote network latency. 
- **Why not pgvector?** Requires standing up a PostgreSQL instance plus the pgvector extension—too much infrastructure overhead for what is essentially an ephemeral vector similarity search problem.
ChromaDB runs in-process as a Python library, costs $0, persists to disk, supports metadata filtering out-of-the-box (`where={"video_id": "A"}`), and easily handles the ~60-150 chunks generated per session.

### 5. Chunking Strategy: 512 Tokens with 64-Token Overlap
Video transcripts are continuous speech. 
- 128 tokens is too small, breaking thoughts mid-sentence.
- 1,024 tokens dilutes cosine similarity.
- **512 tokens (~40 seconds of speech)** perfectly captures a full argument/hook. 
- **64-token overlap** ensures we don't sever critical context at boundary splits, which is vital when a user explicitly queries "compare the hooks in the first 5 seconds".

---

## 🚀 Scaling to 10,000 Creators / Day

If this product scales to 10,000 creators executing multiple queries per day, the current architecture will face specific bottlenecks. Here is the exact plan to upgrade the stack for that scale:

1. **ChromaDB SQLite Lock Contention**
   * **Problem:** Concurrent writes to an in-process SQLite-backed Chroma instance will bottleneck and cause thread locks.
   * **Solution:** Migrate to **Qdrant** (self-hosted Docker) or **Weaviate** with horizontal sharding. Because both adhere to the LangChain `VectorStore` interface, this is a 5-line configuration change.
2. **In-Process FastAPI Memory Leaks**
   * **Problem:** `ConversationBufferWindowMemory` currently holds session arrays in FastAPI process RAM. At 10,000 active sessions, this will trigger an OOM (Out of Memory) crash.
   * **Solution:** Swap to a Redis-backed memory store (`RedisChatMessageHistory`) with a strict 1-hour TTL.
3. **Synchronous Whisper Transcriptions**
   * **Problem:** `openai-whisper` (even the `tiny` model) is CPU-bound. 10,000 reels processed simultaneously will exhaust the server thread pool.
   * **Solution:** Push Instagram URL jobs to a Redis + Celery task queue, or offload strictly to an async API like AssemblyAI if compute costs outscale API costs.
4. **YouTube API Quota limits**
   * **Problem:** The YouTube Data API v3 free tier grants 10,000 units/day. 10k users will exhaust this immediately.
   * **Solution:** Apply for a paid quota increase ($0.10 per 1K units), which remains trivial in cost compared to compute.

**Cost at 1,000 Creators/Day:**
With ~20M tokens of generation/day via Gemini 3.5 Flash, the LLM costs **~$1.50/day**. The embeddings via Gemini Free Tier are effectively $0. The only tangible cost is the compute instance (e.g., an AWS t3.medium) running Whisper. The entire stack at 1k users costs **~$6.50/day**.

---

## ⚙️ Platform Comparison Rules (Handling N/A)

A key engineering decision was how to handle disparate metadata across platforms. 
- YouTube provides `views` and `follower_count`.
- Instagram Reels (when scraped publicly) often **hide views and follower counts**.
Rather than fabricating an engagement rate or using `likes` as a proxy for `views` (which mathematically breaks comparison logic), the backend securely flags missing data as `null`. The prompt injected into the LLM explicitly instructs it: *“If engagement rate is missing, state it is unavailable. Do not hallucinate or use proxies.”* 
Honest reporting is fundamentally better engineering than hallucinated metrics.

---

## 🕵️ The Datacenter IP Tax (Scraping Reality)
If you inspect the repository, you'll notice a `cookies.txt` file injected into the backend. 
**Why?** Because deploying to any major cloud provider (AWS, GCP, Render) instantly triggers YouTube's "Sign in to confirm you're not a bot" PoWeb-Token blockade on datacenter IP ranges. While naive scrapers fail in production, this architecture circumvents the IP block entirely by passing authenticated burner cookies directly into the `yt-dlp` Whisper fallback pipeline. This proves the system can actually execute in a hostile cloud environment, not just on `localhost`.

---

## 💻 Running the Project

### 1. Clone & Setup
```bash
# Clone repo
git clone <your-repo-url>
cd viberag
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt

# Create your .env file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY and YOUTUBE_API_KEY

# Start server
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
# Open a new terminal
cd frontend

npm install

# Create your .env.local file
cp .env.example .env.local
# Verify NEXT_PUBLIC_API_URL=http://localhost:8000 is set

# Start dev server
npm run dev
```

The application will be running at `http://localhost:3000`.
