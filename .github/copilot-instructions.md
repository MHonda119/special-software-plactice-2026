# Copilot Instructions

## Architecture

- Full stack = Django REST backend + React/Vite frontend + Postgres + Ollama + Chroma, orchestrated via docker-compose (repo root).
- Backend lives under `/api/` per `lecture_system/urls.py`; frontend proxy config (`frontend/vite.config.js`) rewrites `/api` to the backend container, so keep API paths stable.
- `backend/entrypoint.sh` waits for Postgres, runs migrations, collects static assets, and auto-creates the admin user (admin/password) so Compose boots cleanly.

## Backend patterns

- Single Django app `core` holds models, serializers, and DRF viewsets; extend APIs by touching files inside `backend/core/*` to stay consistent.
- The LLM registry (`core/models.py` -> `LLM`) drives provider choice; `build_llm_client` (`core/llm_clients.py`) instantiates Ollama/OpenAI/Gemini clients and enforces API keys for hosted providers.
- `ChatSessionViewSet.chat` wraps `ChatInSessionUsecase` (`core/usecases.py`) which persists user + assistant messages and forwards options to the LLM; reuse this pattern for any session-scoped chat logic.
- `AgentViewSet.execute` (`core/views.py`) merges `llm.extra` → `agent.config` → request `options`, strips retrieval keys, injects a single system prompt per session, and branches BASIC_CHAT vs RAG_CHAT.
- RAG paths rely on `RagChatRunner` (`core/rag_runner.py`): embeds questions, queries Chroma, fills `context_template`, and returns citations/usage merged into the assistant message.
- Datasource APIs plus `core/datasource_store.py` manage `chromadb.PersistentClient` at `CHROMA_PERSIST_DIR` (default `/data/chroma`); chunk CRUD flows through `/api/datasources/{id}/chunks/`.
- Key env toggles (`LLM_REQUEST_TIMEOUT`, `OLLAMA_BASE_URL`, `OPENAI_BASE_URL`, `GEMINI_BASE_URL`, `CHROMA_PERSIST_DIR`) control outbound calls—set them in `.env` when introducing new providers.
- API contracts are mirrored in `backend/documents/*.md`; keep those drafts updated when changing routes or payloads.

## Frontend patterns

- React Router is defined in `frontend/src/main.jsx` (Start → Menu → Chat) with Material UI components for layout.
- API traffic funnels through `services/apiClient.js`, which mints a CSRF token via `/api/csrf/` and falls back to `services/mockApi.js` (localStorage) if the backend is unreachable—ensure new endpoints match this client.
- `MenuPage.jsx` expects `/api/llms/` and `/api/sessions/`; `ChatPage.jsx` consumes `/sessions/{uuid}/messages` and `/sessions/{uuid}/chat`, so keep those response shapes stable.
- Vite dev server already proxies `/api`; run `npm install && npm run dev` inside `frontend/` for HMR without Docker.

## Data & LLM workflows

- Before chatting, register at least one active `LLM` via Django admin (`/admin/`) and, for RAG, create Agents/Datasources per `docs/setup.md`.
- RAG agents require `config.datasource_ids` plus an embedding-capable LLM; retrieval overrides accepted via Agent execute must use the keys handled by `RagChatRunner`.
- `/api/datasources/{id}/chunks/` triggers embeddings through the Datasource's LLM provider (OpenAI `/embeddings`, Ollama `/api/embeddings`); missing `api_key` causes a 422.
- Session reuse hinges on `session_uuid`; `AgentViewSet.execute` enforces that the UUID belongs to the requested agent, so persist it client-side.

## Developer workflows

- Standard startup: `docker-compose up --build` from repo root brings up db, ollama, backend (8000), and frontend (3000); backend env values come from `.env`.
- Backend tests: `bash scripts/test-backend.sh` (uses a temporary container and the in-memory SQLite settings defined in `lecture_system/test_settings.py`; PostgreSQL and Ollama do not need to be running).
- For manual API pokes, re-use the samples under `scripts/api_basics/` or follow the specs in `backend/documents/*`.
- Frontend production build ships through `frontend/Dockerfile` (served by nginx); add `VITE_API_BASE_URL` via `.env` or Docker args when pointing at non-default APIs.
- Static assets live in `backend/staticfiles/` after `collectstatic`; `whitenoise` (settings.py) serves them, so keep filenames hashed via the default storage.

## Testing & conventions

- Backend tests under `backend/core/tests/` patch external dependencies (e.g., `generate_embedding`, `build_llm_client`) to keep suites deterministic—mirror that strategy when adding tests.
- Serializers enforce business rules (`LLMCreateUpdateSerializer` requires API keys for OpenAI/Gemini, `AgentCreateUpdateSerializer` limits `usecase_type`), so update validation before changing models/migrations.
- REST resources follow DRF router naming (`llms`, `sessions`, `agents`, `datasources`); register any new ViewSet in `core/urls.py` so the frontend proxy and docs keep working.
