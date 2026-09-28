import { v4 as uuidv4 } from "uuid";

const STORAGE_KEYS = {
  sessions: "mock_sessions",
  messages: "mock_messages",
  agents: "mock_agents",
  agentSessions: "mock_agent_sessions",
  datasources: "mock_datasources",
  datasourceChunks: "mock_datasource_chunks",
};

function load(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
}

function save(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function getModels() {
  return [
    { id: "gpt-4o-mini", name: "GPT-4o mini (mock)" },
    { id: "claude-3.5", name: "Claude 3.5 (mock)" },
    { id: "local-llm", name: "Local LLM (mock)" },
  ];
}

export function getSessions() {
  const sessions = load(STORAGE_KEYS.sessions, []);
  return sessions.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
}

function seedAgentsIfNeeded() {
  const seeded = load(STORAGE_KEYS.agents, null);
  if (seeded) return seeded;
  const defaults = [
    {
      id: 1,
      name: "Docs QA (mock)",
      usecase_type: "RAG_CHAT",
      llm: 1,
      system_prompt: "You answer based on uploaded documents.",
      config: { datasource_ids: [1], top_k: 3 },
      tools: {},
      is_active: true,
    },
    {
      id: 2,
      name: "Helper Bot (mock)",
      usecase_type: "BASIC_CHAT",
      llm: 1,
      system_prompt: "You are a friendly assistant.",
      config: { temperature: 0.2 },
      tools: {},
      is_active: true,
    },
  ];
  save(STORAGE_KEYS.agents, defaults);
  return defaults;
}

export function getAgents() {
  return seedAgentsIfNeeded();
}

export function getAgentById(id) {
  return getAgents().find((a) => a.id === Number(id));
}

export function createAgent(payload) {
  const list = getAgents();
  const nextId = list.reduce((max, a) => Math.max(max, Number(a.id)), 0) + 1;
  const agent = {
    id: nextId,
    name: payload.name || `Agent ${nextId}`,
    usecase_type: payload.usecase_type || "RAG_CHAT",
    llm: payload.llm || 1,
    system_prompt: payload.system_prompt || "",
    config: payload.config || {},
    tools: payload.tools || {},
    is_active: payload.is_active !== false,
  };
  const updated = [...list, agent];
  save(STORAGE_KEYS.agents, updated);
  return agent;
}

export function updateAgent(id, payload) {
  const list = getAgents();
  const idx = list.findIndex((a) => a.id === Number(id));
  if (idx === -1) throw new Error("Agent not found");
  const updatedAgent = { ...list[idx], ...payload, id: list[idx].id };
  const updated = [...list];
  updated[idx] = updatedAgent;
  save(STORAGE_KEYS.agents, updated);
  return updatedAgent;
}

export function deleteAgent(id) {
  const list = getAgents();
  const filtered = list.filter((a) => a.id !== Number(id));
  save(STORAGE_KEYS.agents, filtered);
  return true;
}

export function getSessionById(id) {
  return getSessions().find((s) => s.id === id);
}

export async function createSession({ model }) {
  const models = getModels();
  const modelInfo = models.find((m) => m.id === model);
  const session = {
    id: uuidv4(),
    title: "New Chat",
    model,
    modelName: modelInfo?.name || model,
    createdAt: new Date().toISOString(),
  };
  const sessions = getSessions();
  sessions.push(session);
  save(STORAGE_KEYS.sessions, sessions);
  // Initialize messages store
  const messages = load(STORAGE_KEYS.messages, {});
  messages[session.id] = [];
  save(STORAGE_KEYS.messages, messages);
  return session;
}

export function getMessages(sessionId) {
  const all = load(STORAGE_KEYS.messages, {});
  return all[sessionId] || [];
}

export async function sendMessage(sessionId, content) {
  const all = load(STORAGE_KEYS.messages, {});
  const sessions = getSessions();
  if (!all[sessionId]) all[sessionId] = [];

  const userMsg = {
    id: uuidv4(),
    role: "user",
    content,
    createdAt: new Date().toISOString(),
  };
  all[sessionId].push(userMsg);
  save(STORAGE_KEYS.messages, all);

  // Mock LLM response after a short delay
  await new Promise((res) => setTimeout(res, 400));
  const assistantMsg = {
    id: uuidv4(),
    role: "assistant",
    content: `Echo: ${content}`,
    createdAt: new Date().toISOString(),
  };
  all[sessionId].push(assistantMsg);
  save(STORAGE_KEYS.messages, all);

  // Update session title on first message
  const session = sessions.find((s) => s.id === sessionId);
  if (session && session.title === "New Chat") {
    session.title = content.slice(0, 20) || "New Chat";
    save(STORAGE_KEYS.sessions, sessions);
  }

  return all[sessionId];
}

export async function executeAgent(agentId, payload = {}) {
  const agent = getAgentById(agentId);
  if (!agent) throw new Error("Agent not found");
  const input = (payload.input || "").trim();
  if (!input) throw new Error("input is required");

  const sessionUuid = payload.session_uuid;
  let targetSession = sessionUuid ? getSessionById(sessionUuid) : null;
  if (!targetSession) {
    targetSession = await createSession({ model: agent.llm });
  }

  const sessionId = targetSession.id || targetSession.uuid;
  const allMessages = load(STORAGE_KEYS.messages, {});
  if (!allMessages[sessionId]) allMessages[sessionId] = [];

  const userMsg = {
    id: uuidv4(),
    role: "user",
    content: input,
    createdAt: new Date().toISOString(),
  };
  allMessages[sessionId].push(userMsg);
  save(STORAGE_KEYS.messages, allMessages);

  await new Promise((res) => setTimeout(res, 400));

  const assistantMsg = {
    id: uuidv4(),
    role: "assistant",
    content: `[${agent.name}] ${input}`,
    createdAt: new Date().toISOString(),
  };
  const citations = (agent.config?.datasource_ids || []).map((id, idx) => ({
    doc_id: `doc-${id}-${idx}`,
    score: 0.8 - idx * 0.1,
    snippet: `Mock snippet from datasource ${id}`,
  }));
  if (citations.length) assistantMsg.citations = citations;
  allMessages[sessionId].push(assistantMsg);
  save(STORAGE_KEYS.messages, allMessages);

  const agentSessions = load(STORAGE_KEYS.agentSessions, {});
  agentSessions[sessionId] = { agentId: agent.id };
  save(STORAGE_KEYS.agentSessions, agentSessions);

  return {
    agent_id: agent.id,
    session_uuid: sessionId,
    result: {
      message: {
        id: assistantMsg.id,
        role: "assistant",
        content: assistantMsg.content,
      },
      citations,
    },
    usage: { mock_tokens: input.length },
  };
}

function seedDatasourcesIfNeeded() {
  const seeded = load(STORAGE_KEYS.datasources, null);
  if (seeded) {
    ensureChunkStoreExists();
    return seeded;
  }
  const defaults = [
    {
      id: 1,
      name: "社内Wiki (mock)",
      description: "ローカルに保存されたドキュメントセット",
      llm: 1,
      is_active: true,
    },
    {
      id: 2,
      name: "FAQ (mock)",
      description: "よくある質問をまとめたベース",
      llm: 1,
      is_active: true,
    },
  ];
  save(STORAGE_KEYS.datasources, defaults);
  seedChunkStore(defaults);
  return defaults;
}

function ensureChunkStoreExists() {
  const existing = load(STORAGE_KEYS.datasourceChunks, null);
  if (existing) return existing;
  const empty = {};
  save(STORAGE_KEYS.datasourceChunks, empty);
  return empty;
}

function seedChunkStore(datasources) {
  const store = {};
  datasources.forEach((ds, index) => {
    store[String(ds.id)] =
      index === 0
        ? [
            {
              chunk_id: uuidv4(),
              title: "サンプルチャンク",
              chunk_text: `${ds.name} に登録済みのモックチャンクです。`,
            },
          ]
        : [];
  });
  save(STORAGE_KEYS.datasourceChunks, store);
  return store;
}

function readChunkStore() {
  return ensureChunkStoreExists();
}

function writeChunkStore(store) {
  save(STORAGE_KEYS.datasourceChunks, store);
}

export function getDatasources() {
  return seedDatasourcesIfNeeded();
}

export function getDatasourceById(id) {
  return getDatasources().find((d) => d.id === Number(id));
}

export function createDatasource(payload) {
  const list = getDatasources();
  const nextId = list.reduce((max, d) => Math.max(max, Number(d.id)), 0) + 1;
  const datasource = {
    id: nextId,
    name: payload.name || `Datasource ${nextId}`,
    description: payload.description || "",
    llm: payload.llm || 1,
    is_active: payload.is_active !== false,
  };
  const updated = [...list, datasource];
  save(STORAGE_KEYS.datasources, updated);
  const store = readChunkStore();
  store[String(nextId)] = [];
  writeChunkStore(store);
  return datasource;
}

export function updateDatasource(id, payload) {
  const list = getDatasources();
  const idx = list.findIndex((d) => d.id === Number(id));
  if (idx === -1) throw new Error("Datasource not found");
  const updatedDs = {
    ...list[idx],
    ...payload,
    id: list[idx].id,
  };
  const updated = [...list];
  updated[idx] = updatedDs;
  save(STORAGE_KEYS.datasources, updated);
  return updatedDs;
}

export function deleteDatasource(id) {
  const list = getDatasources();
  const filtered = list.filter((d) => d.id !== Number(id));
  save(STORAGE_KEYS.datasources, filtered);
  const store = readChunkStore();
  delete store[String(id)];
  writeChunkStore(store);
  return true;
}

export function listDatasourceChunks(
  datasourceId,
  params = { limit: 20, offset: 0 },
) {
  const limit = Math.max(1, Math.min(100, Number(params.limit) || 20));
  const offset = Math.max(0, Number(params.offset) || 0);
  const store = readChunkStore();
  const list = store[String(datasourceId)] || [];
  const sliced = list.slice(offset, offset + limit);
  return {
    datasource_id: Number(datasourceId),
    count: sliced.length,
    limit,
    offset,
    chunks: sliced.map((chunk) => ({
      chunk_id: chunk.chunk_id,
      title: chunk.title,
      text_length: chunk.chunk_text.length,
    })),
  };
}

export function addDatasourceChunk(datasourceId, payload) {
  const ds = getDatasourceById(datasourceId);
  if (!ds) throw new Error("Datasource not found");
  const store = readChunkStore();
  const key = String(datasourceId);
  if (!store[key]) store[key] = [];
  const chunk = {
    chunk_id: uuidv4(),
    title: payload.title,
    chunk_text: payload.chunk_text,
  };
  store[key] = [chunk, ...store[key]];
  writeChunkStore(store);
  return {
    datasource_id: Number(datasourceId),
    chunk_id: chunk.chunk_id,
    title: chunk.title,
    text_length: chunk.chunk_text.length,
  };
}

export function deleteDatasourceChunk(datasourceId, chunkId) {
  const store = readChunkStore();
  const key = String(datasourceId);
  const list = store[key] || [];
  const next = list.filter((chunk) => chunk.chunk_id !== chunkId);
  if (next.length === list.length) return false;
  store[key] = next;
  writeChunkStore(store);
  return true;
}
