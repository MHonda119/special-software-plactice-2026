import assert from "node:assert/strict";
import { afterEach, beforeEach, mock, test } from "node:test";
import {
  agentApi,
  authApi,
  clearCsrfToken,
  createSession,
  datasourceApi,
  getLLMs,
  getMessages,
  listSessions,
  onUnauthorized,
  sendMessage,
} from "./apiClient.js";

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

beforeEach(() => clearCsrfToken());
afterEach(() => mock.restoreAll());

test("login uses the response CSRF token without a readable cookie and rotates it", async () => {
  const calls = [];
  let tokenCount = 0;
  const session = {
    user: { id: 1, username: "alice" },
    expires_at: "2026-10-27T00:00:00Z",
  };
  mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, ...options });
    if (url.endsWith("/csrf/"))
      return json({ csrftoken: `token-${++tokenCount}` });
    if (url.endsWith("/auth/login/")) return json(session);
    return new Response(null, { status: 204 });
  });

  assert.deepEqual(
    await authApi.login({ username: "alice", password: "secret" }),
    session,
  );
  await authApi.logout();
  const posts = calls.filter((call) => call.method === "POST");
  assert.equal(posts[0].headers["X-CSRFToken"], "token-1");
  assert.equal(posts[1].headers["X-CSRFToken"], "token-2");
  assert.deepEqual(JSON.parse(posts[0].body), {
    username: "alice",
    password: "secret",
  });
  assert.ok(
    calls.every(
      (call) => call.credentials === "include" && call.cache === "no-store",
    ),
  );
});

test("me is uncached and preserves the server session contract", async () => {
  mock.method(globalThis, "fetch", async (_url, options) => {
    assert.equal(options.cache, "no-store");
    return json({
      user: { id: 2, username: "bob" },
      expires_at: "2026-10-27T00:00:00Z",
    });
  });
  assert.equal((await authApi.me()).user.username, "bob");
});

test("every existing business API rejects 401 instead of returning mock data", async () => {
  let notifications = 0;
  const unsubscribe = onUnauthorized(() => notifications++);
  mock.method(globalThis, "fetch", async (url) =>
    url.endsWith("/csrf/")
      ? json({ csrftoken: "token" })
      : json({ detail: "Unauthenticated" }, 401),
  );
  const operations = [
    () => getLLMs(),
    () => createSession({ llm: 1 }),
    () => listSessions(),
    () => getMessages("session"),
    () => sendMessage("session", "hello"),
    ...[agentApi, datasourceApi].flatMap((resource) => [
      () => resource.list(),
      () => resource.retrieve(1),
      () => resource.create({}),
      () => resource.update(1, {}),
      () => resource.patch(1, {}),
      () => resource.remove(1),
    ]),
    () => agentApi.execute(1, {}),
    () => datasourceApi.listChunks(1),
    () => datasourceApi.addChunk(1, {}),
    () => datasourceApi.deleteChunk(1, 2),
  ];
  try {
    for (const operation of operations) {
      await assert.rejects(operation, { status: 401, kind: "unauthorized" });
    }
    assert.equal(notifications, operations.length);
  } finally {
    unsubscribe();
  }
});

test("invalid credentials do not broadcast an expired session", async () => {
  const unsubscribe = onUnauthorized(() =>
    assert.fail("Unexpected unauthorized event"),
  );
  mock.method(globalThis, "fetch", async (url) =>
    url.endsWith("/csrf/")
      ? json({ csrftoken: "token" })
      : json({ detail: "Invalid" }, 401),
  );
  try {
    await assert.rejects(
      () => authApi.login({ username: "alice", password: "bad" }),
      {
        status: 401,
        message: "ユーザー名またはパスワードが正しくありません。",
      },
    );
  } finally {
    unsubscribe();
  }
});

test("CSRF, permission denial and network failures remain distinct errors", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () =>
    json({ detail: "CSRF Failed" }, 403),
  );
  await assert.rejects(() => getLLMs(), { status: 403, kind: "csrf" });
  fetchMock.mock.mockImplementation(async () =>
    json({ detail: "Permission denied" }, 403),
  );
  await assert.rejects(() => listSessions(), {
    status: 403,
    kind: "forbidden",
  });
  fetchMock.mock.mockImplementation(async () => {
    throw new TypeError("Failed to fetch");
  });
  await assert.rejects(() => getLLMs(), { status: 0, kind: "network" });
});

test("CSRF acquisition failure stops the mutation and can be retried", async () => {
  const fetchMock = mock.method(globalThis, "fetch", async () => {
    throw new TypeError("offline");
  });
  await assert.rejects(() => createSession({ llm: 1 }), { kind: "network" });
  assert.equal(fetchMock.mock.callCount(), 1);
  fetchMock.mock.mockImplementation(async (url) =>
    url.endsWith("/csrf/")
      ? json({ csrftoken: "retry-token" })
      : json({ uuid: "new-session" }),
  );
  assert.deepEqual(await createSession({ llm: 1 }), { uuid: "new-session" });
});
