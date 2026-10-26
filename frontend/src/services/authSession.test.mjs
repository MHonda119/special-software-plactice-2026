import assert from "node:assert/strict";
import { test } from "node:test";
import { ApiError } from "./apiClient.js";
import { createAuthSession } from "./authSession.js";

function setup() {
  let time = Date.parse("2026-10-26T00:00:00Z");
  let callback;
  let delay;
  let meCalls = 0;
  const session = {
    user: { id: 1, username: "alice" },
    expires_at: "2026-10-26T12:00:00Z",
  };
  const api = {
    me: async () => {
      meCalls++;
      return session;
    },
    login: async () => session,
    logout: async () => {},
  };
  const events = new EventTarget();
  const visibility = new EventTarget();
  visibility.visibilityState = "visible";
  const store = createAuthSession({
    api,
    now: () => time,
    timers: {
      setTimeout: (handler, wait) => {
        callback = handler;
        delay = wait;
        return 1;
      },
      clearTimeout: () => {
        callback = undefined;
      },
    },
    eventTarget: events,
    visibilityTarget: visibility,
  });
  return {
    api,
    store,
    events,
    visibility,
    session,
    meCalls: () => meCalls,
    delay: () => delay,
    advance: (milliseconds) => {
      time += milliseconds;
    },
    fireTimer: () => callback?.(),
  };
}

test("reload starts with me, restores the session and schedules its absolute expiry", async () => {
  const context = setup();
  const stop = context.store.start();
  await context.store.revalidate();
  assert.equal(context.meCalls(), 1);
  assert.equal(context.store.getSnapshot().status, "authenticated");
  assert.equal(context.delay(), 12 * 60 * 60 * 1000);
  stop();
});

test("the displayed session expires after 12 hours without another request", async () => {
  const context = setup();
  await context.store.login({});
  context.advance(12 * 60 * 60 * 1000);
  context.fireTimer();
  assert.equal(context.store.getSnapshot().status, "anonymous");
  assert.equal(context.store.getSnapshot().session, null);
  assert.equal(context.store.getSnapshot().reason, "expired");
  assert.equal(context.meCalls(), 0);
});

test("focus and visibility restore recheck me without sliding the expiry", async () => {
  const context = setup();
  const stop = context.store.start();
  await context.store.revalidate();
  context.api.me = async () => ({
    ...context.session,
    expires_at: "2026-10-27T00:00:00Z",
  });
  context.advance(60_000);
  context.events.dispatchEvent(new Event("focus"));
  await context.store.revalidate();
  assert.equal(
    context.store.getSnapshot().session.expires_at,
    context.session.expires_at,
  );
  context.visibility.visibilityState = "hidden";
  context.visibility.dispatchEvent(new Event("visibilitychange"));
  context.advance(12 * 60 * 60 * 1000);
  context.visibility.visibilityState = "visible";
  context.visibility.dispatchEvent(new Event("visibilitychange"));
  assert.equal(context.store.getSnapshot().status, "anonymous");
  stop();
});

test("focus discovers a server-invalidated session before its local deadline", async () => {
  const context = setup();
  const stop = context.store.start();
  await context.store.revalidate();
  context.api.me = async () => {
    throw new ApiError("Expired", 401, "unauthorized");
  };
  context.events.dispatchEvent(new Event("focus"));
  await context.store.revalidate();
  assert.equal(context.store.getSnapshot().status, "anonymous");
  stop();
});

test("403 and network failures hide protected content without masquerading as logout", async () => {
  const context = setup();
  for (const error of [
    new ApiError("Denied", 403, "forbidden"),
    new ApiError("Offline"),
  ]) {
    context.api.me = async () => {
      throw error;
    };
    await context.store.revalidate();
    assert.equal(context.store.getSnapshot().status, "error");
    assert.equal(context.store.getSnapshot().error, error);
  }
  context.api.me = async () => context.session;
  await context.store.revalidate();
  assert.equal(context.store.getSnapshot().status, "authenticated");
});

test("logout clears state only when the server confirms invalidation", async () => {
  const context = setup();
  await context.store.login({});
  context.api.logout = async () => {
    throw new ApiError("Offline");
  };
  await assert.rejects(() => context.store.logout(), { kind: "network" });
  assert.equal(context.store.getSnapshot().status, "authenticated");
  context.api.logout = async () => {};
  await context.store.logout();
  assert.equal(context.store.getSnapshot().status, "anonymous");
  context.advance(12 * 60 * 60 * 1000);
  context.fireTimer();
  assert.equal(context.store.getSnapshot().reason, null);
});

test("a stale me response cannot restore a session after logout", async () => {
  const context = setup();
  await context.store.login({});
  let complete;
  context.api.me = () =>
    new Promise((resolve) => {
      complete = resolve;
    });
  const pending = context.store.revalidate();
  await Promise.resolve();
  await context.store.logout();
  complete(context.session);
  await pending;
  assert.equal(context.store.getSnapshot().status, "anonymous");
});

test("an expired me response never authenticates the page", async () => {
  const context = setup();
  context.advance(13 * 60 * 60 * 1000);
  await context.store.revalidate();
  assert.equal(context.store.getSnapshot().status, "anonymous");
  assert.equal(context.store.getSnapshot().reason, "expired");
});
