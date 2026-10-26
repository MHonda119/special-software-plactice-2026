import {
  ApiError,
  authApi,
  clearCsrfToken,
  onUnauthorized,
} from "./apiClient.js";

export function createAuthSession({
  api = authApi,
  now = () => Date.now(),
  timers = globalThis,
  eventTarget = globalThis.window,
  visibilityTarget = globalThis.document,
} = {}) {
  let state = { status: "checking", session: null, error: null, reason: null };
  let version = 0;
  let timer;
  let pending;
  const listeners = new Set();

  function publish(next) {
    state = next;
    listeners.forEach((listener) => listener());
  }

  function clearTimer() {
    timers.clearTimeout(timer);
    timer = undefined;
  }

  function invalidate(reason = null) {
    version++;
    pending = undefined;
    clearTimer();
    clearCsrfToken();
    publish({ status: "anonymous", session: null, error: null, reason });
  }

  function checkExpiry() {
    if (state.session && Date.parse(state.session.expires_at) <= now()) {
      invalidate("expired");
      return true;
    }
    return false;
  }

  function armTimer() {
    clearTimer();
    if (!state.session) return;
    timer = timers.setTimeout(() => {
      if (!checkExpiry()) armTimer();
    }, Math.min(Date.parse(state.session.expires_at) - now(), 2_147_483_647));
  }

  function acceptSession(session, preserveExpiry) {
    if (
      !session?.user?.username ||
      !Number.isFinite(Date.parse(session.expires_at))
    ) {
      throw new ApiError("認証情報の応答が正しくありません。", 0, "response");
    }
    let expiresAt = session.expires_at;
    if (preserveExpiry && state.session?.user.id === session.user.id) {
      if (Date.parse(state.session.expires_at) < Date.parse(expiresAt)) {
        expiresAt = state.session.expires_at;
      }
    }
    if (Date.parse(expiresAt) <= now()) {
      invalidate("expired");
      return;
    }
    publish({
      status: "authenticated",
      session: { ...session, expires_at: expiresAt },
      error: null,
      reason: null,
    });
    armTimer();
  }

  function revalidate() {
    if (checkExpiry()) return Promise.resolve();
    if (pending) return pending;
    const requestVersion = version;
    const request = Promise.resolve()
      .then(() => api.me())
      .then((session) => {
        if (requestVersion === version) acceptSession(session, true);
      })
      .catch((error) => {
        if (requestVersion !== version) return;
        if (error.status === 401) {
          invalidate(state.session ? "expired" : null);
        } else {
          publish({ ...state, status: "error", error });
        }
      })
      .finally(() => {
        if (pending === request) pending = undefined;
      });
    pending = request;
    return request;
  }

  return {
    getSnapshot: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    revalidate,
    login: async (credentials) => {
      const requestVersion = ++version;
      pending = undefined;
      const session = await api.login(credentials);
      if (requestVersion === version) acceptSession(session, false);
    },
    logout: async () => {
      const requestVersion = ++version;
      pending = undefined;
      await api.logout();
      if (requestVersion === version) invalidate();
    },
    start: () => {
      const restore = () => {
        if (visibilityTarget?.visibilityState === "hidden") return;
        if (!checkExpiry() && state.status !== "anonymous") void revalidate();
      };
      const unsubscribe = onUnauthorized(() =>
        invalidate(state.session ? "expired" : null),
      );
      eventTarget?.addEventListener("focus", restore);
      visibilityTarget?.addEventListener("visibilitychange", restore);
      if (!checkExpiry()) {
        armTimer();
        void revalidate();
      }
      return () => {
        unsubscribe();
        eventTarget?.removeEventListener("focus", restore);
        visibilityTarget?.removeEventListener("visibilitychange", restore);
        version++;
        pending = undefined;
        clearTimer();
      };
    },
  };
}

export const authSession = createAuthSession();
