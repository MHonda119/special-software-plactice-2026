import type { Page, Request } from "@playwright/test";

export async function mockAuth(
  page: Page,
  options: { authenticated?: boolean; expiresAt?: string } = {},
) {
  const state = {
    authenticated: options.authenticated ?? true,
    expiresAt:
      options.expiresAt ??
      new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString(),
    meStatus: 200,
    meOffline: false,
    businessStatus: 200,
    businessOffline: false,
    logoutOffline: false,
    logoutStatus: 204,
    csrfStatus: 200,
    csrfCalls: 0,
    meCalls: 0,
    requests: [] as Request[],
  };
  const session = () => ({
    user: { id: 1, username: "alice" },
    expires_at: state.expiresAt,
  });

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    state.requests.push(request);
    const path = new URL(request.url()).pathname;
    const headers = { "Cache-Control": "no-store" };
    const respond = (body: unknown, status = 200, extraHeaders = {}) =>
      route.fulfill({
        status,
        headers: { ...headers, ...extraHeaders },
        json: body,
      });

    if (path === "/api/csrf/") {
      state.csrfCalls++;
      return respond(
        { csrftoken: `csrf-${state.csrfCalls}` },
        state.csrfStatus,
        {
          "Set-Cookie": `csrftoken=csrf-${state.csrfCalls}; Path=/; HttpOnly; SameSite=Lax`,
        },
      );
    }
    if (path === "/api/auth/me/") {
      state.meCalls++;
      if (state.meOffline) return route.abort("failed");
      if (state.meStatus !== 200)
        return respond({ detail: "Permission denied" }, state.meStatus);
      return state.authenticated
        ? respond(session())
        : respond({ detail: "Unauthenticated" }, 401);
    }
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) {
      if (
        request.headers()["x-csrftoken"] !== `csrf-${state.csrfCalls}` ||
        !state.csrfCalls
      ) {
        return respond({ detail: "CSRF Failed" }, 403);
      }
    }
    if (path === "/api/auth/login/") {
      const credentials = request.postDataJSON();
      if (
        credentials.username !== "alice" ||
        credentials.password !== "correct-password"
      ) {
        return respond({ detail: "Invalid credentials" }, 401);
      }
      state.authenticated = true;
      return respond(session(), 200, {
        "Set-Cookie": "csrftoken=rotated; Path=/; HttpOnly; SameSite=Lax",
      });
    }
    if (path === "/api/auth/logout/") {
      if (state.logoutOffline) return route.abort("failed");
      if (state.logoutStatus !== 204)
        return respond({ detail: "CSRF Failed" }, state.logoutStatus);
      state.authenticated = false;
      return route.fulfill({ status: 204, headers });
    }
    if (state.businessOffline) return route.abort("failed");
    if (state.businessStatus !== 200)
      return respond({ detail: "Permission denied" }, state.businessStatus);
    if (!state.authenticated)
      return respond({ detail: "Unauthenticated" }, 401);
    if (path === "/api/llms/") {
      return respond([
        {
          id: 1,
          name: "実APIモデル",
          provider: "OLLAMA",
          model: "test",
          is_active: true,
        },
      ]);
    }
    return respond([]);
  });
  return state;
}

export async function fillLogin(page: Page, password = "correct-password") {
  await page.getByLabel("ユーザー名").fill("alice");
  await page.getByLabel("パスワード").fill(password);
}
