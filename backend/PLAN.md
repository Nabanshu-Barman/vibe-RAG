# Backend Build Plan — VibeRAG

## Final Stack (Confirmed)

| Layer | Tool |
|---|---|
| API | FastAPI + Uvicorn |
| Orchestration | LangChain LCEL |
| LLM | Gemini 1.5 Flash (`langchain-google-genai`) |
| Embeddings | Google `text-embedding-004` |
| Vector DB | ChromaDB (persistent) |
| YouTube Transcript | `youtube-transcript-api` |
| Instagram Transcript | `yt-dlp` + `openai-whisper` (tiny) |
| YouTube Metadata | YouTube Data API v3 |
| Instagram Metadata | `instaloader` |
| Memory | `ConversationBufferWindowMemory` (k=6) |
| Streaming | FastAPI `StreamingResponse` + SSE |

---

## Final Folder Structure (End State)

```
backend/
├── main.py                  # FastAPI app entry, CORS, router mount
├── README.md                # Tech stack decisions & engineering justification
├── PLAN.md                  # This file — phase-wise build plan
├── .env                     # API keys (gitignored)
├── .env.example             # Template
├── requirements.txt
│
├── api/
│   ├── routes/
│   │   ├── analyze.py       # POST /api/analyze
│   │   └── chat.py          # POST /api/chat (SSE)
│   └── schemas.py           # Pydantic request/response models
│
├── core/
│   ├── config.py            # Settings from env (pydantic-settings)
│   └── exceptions.py        # Custom HTTP exceptions
│
├── services/
│   ├── transcript/
│   │   ├── youtube.py       # youtube-transcript-api wrapper
│   │   └── instagram.py     # yt-dlp + Whisper wrapper
│   ├── metadata/
│   │   ├── youtube_meta.py  # YouTube Data API v3
│   │   └── instagram_meta.py# instaloader wrapper
│   ├── ingest.py            # Orchestrates: fetch → chunk → embed → store
│   ├── embedder.py          # Google text-embedding-004 via LangChain
│   └── vector_store.py      # ChromaDB session collection manager
│
├── rag/
│   ├── chain.py             # LCEL RAG chain (retriever → prompt → LLM)
│   ├── memory.py            # Session memory store
│   ├── prompts.py           # System + RAG prompt templates
│   └── streamer.py          # SSE token generator
│
└── chroma_db/               # Persistent vector store (gitignored)
```

---

## Phase 1 — Project Scaffold & Configuration ✅

**Goal:** Runnable FastAPI server with environment config, health check, and all dependencies installed.

### Tasks

- [x] **1.1** Create `backend/` directory, init `requirements.txt` with all dependencies
- [x] **1.2** Write `core/config.py` — `pydantic-settings` `Settings` class loading from `.env`
- [x] **1.3** Write `core/exceptions.py` — `VideoFetchError`, `TranscriptUnavailableError`, `EmbedError`
- [x] **1.4** Write `api/schemas.py` — all Pydantic request/response models
- [x] **1.5** Write `main.py` — FastAPI app, CORS, routers, `GET /health`
- [x] **1.6** Write stub routes (`analyze.py`, `chat.py`)
- [x] **1.7** Write `.env.example`

### Deliverable
`uvicorn main:app --reload` starts cleanly. `GET /health` returns `{"status": "ok"}`. OpenAPI docs at `/docs`.

---

## Phase 2 — Transcript & Metadata Pipeline

**Goal:** Given a YouTube URL and Instagram URL, return full transcript + all metadata fields for both.

### Tasks

**YouTube Transcript (`services/transcript/youtube.py`)**
- [ ] **2.1** Wrap `youtube-transcript-api`: extract video ID from URL (regex), call `YouTubeTranscriptApi.get_transcript(video_id)`, return list of `{text, start, duration}` dicts
- [ ] **2.2** Build `get_hook_transcript(segments, seconds=5)` — filter segments where `start < 5`, join their text
- [ ] **2.3** Build `get_full_transcript(segments)` — join all text into one string

**YouTube Metadata (`services/metadata/youtube_meta.py`)**
- [ ] **2.4** Use `googleapiclient.discovery` to call `youtube.videos().list(part="snippet,statistics,contentDetails", id=video_id)`
- [ ] **2.5** Parse response into `VideoMetadata` fields (title, creator, upload_date, views, likes, comments, hashtags, duration, thumbnail_url)
- [ ] **2.6** Subscriber count: separate `youtube.channels().list()` call

**Instagram Transcript (`services/transcript/instagram.py`)**
- [ ] **2.7** Use `yt-dlp` to extract audio to a temp `.wav` file
- [ ] **2.8** Load Whisper model once at startup (singleton via `lru_cache`)
- [ ] **2.9** Transcribe with Whisper → `{text, segments}` with timestamps
- [ ] **2.10** Extract hook: filter `segments` where `start < 5`
- [ ] **2.11** Clean up temp audio file after transcription

**Instagram Metadata (`services/metadata/instagram_meta.py`)**
- [ ] **2.12** Use `instaloader` to load `Post.from_shortcode()` — shortcode from URL regex
- [ ] **2.13** Parse: likes, comments, views, hashtags, upload_date, creator, follower_count

**Engagement Rate**
- [ ] **2.14** `engagement_rate = (likes + comments) / views * 100` in `ingest.py`

### Deliverable
`ingest.fetch_video_data(yt_url, ig_url)` returns two fully populated `VideoMetadata` objects. Tested standalone.

---

## Phase 3 — Chunking, Embedding & Vector Store

**Goal:** Take a transcript string + video metadata, chunk it, embed it, and store in ChromaDB tagged with `video_id` and `session_id`.

### Tasks

**Chunker (`services/ingest.py`)**
- [ ] **3.1** Use `RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)`
- [ ] **3.2** Build `Document` per chunk with metadata: `video_id`, `session_id`, `chunk_index`, `chunk_label`, `creator`, `platform`
- [ ] **3.3** `derive_label(i, total)`: `i==0` → `"Hook (0–5s)"`, `i==total-1` → `"Conclusion"`, else `"Chunk {i}"`

**Embedder (`services/embedder.py`)**
- [ ] **3.4** `GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")`
- [ ] **3.5** Singleton getter via `lru_cache`

**Vector Store (`services/vector_store.py`)**
- [ ] **3.6** `langchain_chroma.Chroma` with `persist_directory`
- [ ] **3.7** Per-session collection: `collection_name=f"session_{session_id}"`
- [ ] **3.8** `add_documents(docs)` for all chunks from both videos
- [ ] **3.9** Retriever: `as_retriever(search_kwargs={"k": 4})`

**Ingest Orchestrator**
- [ ] **3.10** `async def run_ingestion(yt_url, ig_url)` → fetch (concurrent) → chunk → embed → store → return `(VideoMetadata, VideoMetadata, session_id)`

### Deliverable
ChromaDB collection created with expected chunk count. `collection.count()` verifiable.

---

## Phase 4 — RAG Chain, Memory & Streaming

**Goal:** Given session_id + message, retrieve chunks, stream Gemini response with citations.

### Tasks

- [ ] **4.1** Init LLM: `ChatGoogleGenerativeAI(model="gemini-1.5-flash", streaming=True, temperature=0.3)`
- [ ] **4.2** Write system prompt with video metadata injection (`rag/prompts.py`)
- [ ] **4.3** Write RAG prompt template: context + chat_history + question
- [ ] **4.4** Session memory store: `Dict[session_id, ConversationBufferWindowMemory(k=6)]` (`rag/memory.py`)
- [ ] **4.5** Build LCEL chain: `RunnableParallel` → prompt → LLM → `StrOutputParser`
- [ ] **4.6** Citation extraction: pull `video_id`, `chunk_label`, `chunk_index` from retrieved docs
- [ ] **4.7** SSE streamer: yield `{"token": "..."}` per token, then `{"citations": [...], "done": true}`
- [ ] **4.8** `POST /api/chat` → `StreamingResponse` with SSE headers

### Deliverable
`curl -N -X POST http://localhost:8000/api/chat` streams Gemini tokens with citations at the end.

---

## Phase 5 — Full API Wiring, Error Handling & Integration Readiness

**Goal:** Wire all phases into clean API endpoints. Backend ready to plug into frontend.

### Tasks

- [ ] **5.1** `POST /api/analyze` → calls `run_ingestion()` → returns `AnalyzeResponse`
- [ ] **5.2** URL validation (fast-fail regex) before any external calls
- [ ] **5.3** Typed error responses: 400, 422, 429 with clear messages
- [ ] **5.4** Concurrent yt + ig pipeline with `asyncio.gather`
- [ ] **5.5** `DELETE /api/session/{session_id}` — cleans ChromaDB collection + memory
- [ ] **5.6** `GZipMiddleware` added to `main.py`
- [ ] **5.7** Structured logging with session_id context and timing spans
- [ ] **5.8** Verify response shapes match frontend service layer contracts exactly

### Deliverable
Full end-to-end: two real URLs → analysis → streaming RAG chat. Zero mocks.

---

## Phase Timeline

| Phase | Focus | Est. Time |
|---|---|---|
| Phase 1 | Scaffold + config + stubs | ~1 hr |
| Phase 2 | Transcript + metadata pipeline | ~2.5 hrs |
| Phase 3 | Chunking + embedding + ChromaDB | ~1.5 hrs |
| Phase 4 | RAG chain + memory + SSE streaming | ~2.5 hrs |
| Phase 5 | API wiring + error handling + integration | ~1.5 hrs |
| **Total** | | **~9 hrs** |

---

## Backend–Frontend Integration Map

| Frontend calls | Backend endpoint | Data contract |
|---|---|---|
| `services/videoService.ts` `analyzeVideos()` | `POST /api/analyze` | `AnalyzeRequest` → `AnalyzeResponse` |
| `services/chatService.ts` `sendChatMessage()` | `POST /api/chat` | `ChatRequest` → SSE stream of `ChatChunk` |
| Reset button | `DELETE /api/session/{id}` | session_id path param |

> Integration = uncomment the real `fetch()` calls in `frontend/services/` + set `NEXT_PUBLIC_API_URL=http://localhost:8000`. Zero component changes needed.
