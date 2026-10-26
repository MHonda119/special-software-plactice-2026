const BASE = import.meta.env?.VITE_API_BASE_URL || "/api";
let csrfToken;
let csrfRequest;
const unauthorizedListeners = new Set();

export class ApiError extends Error {
  constructor(message, status = 0, kind = "network", details = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
    this.details = details;
  }
}

export function onUnauthorized(listener) {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

export function clearCsrfToken() {
  csrfToken = undefined;
  csrfRequest = undefined;
}

function toQuery(params) {
  if (!params) return "";
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, rawValue]) => {
    if (rawValue === undefined || rawValue === null) return;
    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    values.forEach((value) => query.append(key, String(value)));
  });
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

function normalizePath(path) {
  if (!path.startsWith("/")) path = `/${path}`;
  if (!path.endsWith("/")) path = `${path}/`;
  return path;
}

function createRestResource(resourcePath) {
  const basePath = normalizePath(resourcePath);
  return {
    list: (params) => http(`${basePath}${toQuery(params)}`),
    retrieve: (id) => http(`${basePath}${id}/`),
    create: (body) => http(basePath, { method: "POST", body }),
    update: (id, body) => http(`${basePath}${id}/`, { method: "PUT", body }),
    partialUpdate: (id, body) =>
      http(`${basePath}${id}/`, { method: "PATCH", body }),
    remove: (id) => http(`${basePath}${id}/`, { method: "DELETE" }),
  };
}

async function ensureCsrf() {
  if (csrfToken) return csrfToken;
  if (!csrfRequest) {
    const request = http("/csrf/", { cache: "no-store" }).then((data) => {
      if (!data?.csrftoken) {
        throw new ApiError("CSRFトークンを取得できませんでした。", 0, "csrf");
      }
      if (csrfRequest === request) csrfToken = data.csrftoken;
      return data.csrftoken;
    });
    csrfRequest = request;
  }
  const request = csrfRequest;
  try {
    return await request;
  } finally {
    if (csrfRequest === request) csrfRequest = undefined;
  }
}

async function http(path, opts = {}) {
  const { notifyUnauthorized = true, ...fetchOptions } = opts;
  const method = (opts.method || "GET").toUpperCase();
  const headers = {
    "Content-Type": "application/json",
    ...(opts.headers || {}),
  };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    headers["X-CSRFToken"] = await ensureCsrf();
  }
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...fetchOptions,
      method,
      headers,
      credentials: "include",
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  } catch {
    throw new ApiError(
      "サーバーに接続できません。通信環境を確認してください。",
    );
  }
  if (!res.ok) {
    const details = await res.json().catch(() => null);
    if (res.status === 401) {
      if (notifyUnauthorized) {
        clearCsrfToken();
        unauthorizedListeners.forEach((listener) => listener());
      }
      throw new ApiError(
        notifyUnauthorized
          ? "セッションが終了しました。再度ログインしてください。"
          : "ユーザー名またはパスワードが正しくありません。",
        401,
        "unauthorized",
        details,
      );
    }
    if (res.status === 403) {
      clearCsrfToken();
      const csrf = /csrf/i.test(details?.detail || "");
      throw new ApiError(
        csrf
          ? "CSRFの検証に失敗しました。もう一度お試しください。"
          : "この操作の権限がありません。",
        403,
        csrf ? "csrf" : "forbidden",
        details,
      );
    }
    throw new ApiError(
      res.status === 400
        ? "入力内容を確認してください。"
        : `サーバーエラーが発生しました (${res.status})。`,
      res.status,
      "http",
      details,
    );
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return null;
}

export const authApi = {
  login: async (credentials) => {
    const session = await http("/auth/login/", {
      method: "POST",
      body: credentials,
      cache: "no-store",
      notifyUnauthorized: false,
    });
    clearCsrfToken();
    return session;
  },
  me: () => http("/auth/me/", { cache: "no-store" }),
  logout: async () => {
    await http("/auth/logout/", { method: "POST", cache: "no-store" });
    clearCsrfToken();
  },
};

export async function getLLMs() {
  return http("/llms/");
}

export async function createSession({ llm, title }) {
  return http("/sessions/", { method: "POST", body: { llm, title } });
}

export async function listSessions() {
  return http("/sessions/");
}

export async function getMessages(sessionUuid) {
  return http(`/sessions/${sessionUuid}/messages/`);
}

export async function sendMessage(sessionUuid, message, options) {
  return http(`/sessions/${sessionUuid}/chat/`, {
    method: "POST",
    body: { message, options },
  });
}

const agentResource = createRestResource("/agents/");

export const agentApi = {
  list: agentResource.list,
  retrieve: agentResource.retrieve,
  create: agentResource.create,
  update: agentResource.update,
  patch: agentResource.partialUpdate,
  remove: agentResource.remove,
  execute: (agentId, body) =>
    http(`/agents/${agentId}/execute/`, { method: "POST", body }),
};

const datasourceResource = createRestResource("/datasources/");

function datasourceChunksPath(datasourceId) {
  return `/datasources/${datasourceId}/chunks/`;
}

export const datasourceApi = {
  list: datasourceResource.list,
  retrieve: datasourceResource.retrieve,
  create: datasourceResource.create,
  update: datasourceResource.update,
  patch: datasourceResource.partialUpdate,
  remove: datasourceResource.remove,
  listChunks: (datasourceId, params) =>
    http(`${datasourceChunksPath(datasourceId)}${toQuery(params)}`),
  addChunk: (datasourceId, payload) =>
    http(datasourceChunksPath(datasourceId), { method: "POST", body: payload }),
  deleteChunk: (datasourceId, chunkId) =>
    http(`${datasourceChunksPath(datasourceId)}${chunkId}/`, {
      method: "DELETE",
    }),
};
