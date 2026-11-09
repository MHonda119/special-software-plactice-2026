import { test, expect } from "@playwright/test";
import { fillLogin, mockAuth } from "./auth-mock";

const protectedPaths = [
  "/",
  "/menu",
  "/simple-chat",
  "/agent",
  "/agent/new",
  "/agent/1/edit",
  "/datasources",
  "/datasources/1/chunks",
  "/data-registration",
  "/chat",
  "/chat/session",
];

for (const path of protectedPaths) {
  test(`unauthenticated ${path} redirects to login before business requests`, async ({
    page,
  }) => {
    const auth = await mockAuth(page, { authenticated: false });
    await page.goto(path);
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "ログイン", exact: true }),
    ).toBeVisible();
    expect(
      auth.requests.every(
        (request) => new URL(request.url()).pathname === "/api/auth/me/",
      ),
    ).toBeTruthy();
  });
}

test("login shows a pending state, returns to the requested screen and rotates HttpOnly CSRF", async ({
  page,
}) => {
  const auth = await mockAuth(page, { authenticated: false });
  let releaseLogin = () => {};
  const pendingLogin = new Promise<void>((resolve) => {
    releaseLogin = resolve;
  });
  await page.route("**/api/auth/login/", async (route) => {
    await pendingLogin;
    await route.fallback();
  });
  await page.goto("/menu");
  await fillLogin(page);
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "ログイン中…" }),
  ).toBeDisabled();
  await expect(page.getByLabel("ユーザー名")).toBeDisabled();
  releaseLogin();
  await expect(page).toHaveURL(/\/menu$/);
  await expect(
    page.getByRole("heading", { name: "機能メニュー" }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.cookie)).not.toContain("csrftoken");
  await page.getByRole("button", { name: "ログアウト", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(auth.authenticated).toBeFalsy();
  expect(auth.csrfCalls).toBe(2);
  const login = auth.requests.find((request) =>
    request.url().endsWith("/auth/login/"),
  );
  const logout = auth.requests.find((request) =>
    request.url().endsWith("/auth/logout/"),
  );
  expect(login?.postDataJSON()).toEqual({
    username: "alice",
    password: "correct-password",
  });
  expect(login?.headers()["x-csrftoken"]).toBe("csrf-1");
  expect(logout?.headers()["x-csrftoken"]).toBe("csrf-2");
});

test("invalid credentials stay on login and clear the password", async ({
  page,
}) => {
  const auth = await mockAuth(page, { authenticated: false });
  await page.goto("/login");
  await fillLogin(page, "incorrect");
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "ユーザー名またはパスワードが正しくありません",
  );
  await expect(page.getByLabel("パスワード")).toHaveValue("");
  await expect(page).toHaveURL(/\/login$/);
  expect(auth.authenticated).toBeFalsy();
});

test("login input errors are distinct from authentication errors", async ({
  page,
}) => {
  await mockAuth(page, { authenticated: false });
  await page.route("**/api/auth/login/", (route) =>
    route.fulfill({
      status: 400,
      json: { username: ["Invalid username"] },
    }),
  );
  await page.goto("/login");
  await fillLogin(page);
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "入力内容を確認してください。",
  );
});

test("a visible session expires at the server deadline without navigation or another API request", async ({
  page,
}) => {
  const auth = await mockAuth(page, {
    expiresAt: new Date(Date.now() + 4_000).toISOString(),
  });
  await page.goto("/menu");
  await expect(
    page.getByRole("heading", { name: "機能メニュー" }),
  ).toBeVisible();
  const requests = auth.requests.length;
  await expect(page).toHaveURL(/\/login$/, { timeout: 10_000 });
  await expect(page.getByRole("alert")).toContainText("有効期限が切れました");
  expect(auth.requests).toHaveLength(requests);
});

test("reload confirms me and rejects an invalidated server session", async ({
  page,
}) => {
  const auth = await mockAuth(page);
  await page.goto("/menu");
  await expect(
    page.getByRole("heading", { name: "機能メニュー" }),
  ).toBeVisible();
  const beforeReload = auth.meCalls;
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "機能メニュー" }),
  ).toBeVisible();
  expect(auth.meCalls).toBeGreaterThan(beforeReload);
  auth.authenticated = false;
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "機能メニュー" }),
  ).not.toBeVisible();
});

for (const event of ["focus", "visibilitychange"]) {
  test(`${event} checks server invalidation before the local deadline`, async ({
    page,
  }) => {
    const auth = await mockAuth(page);
    await page.goto("/menu");
    await expect(
      page.getByRole("heading", { name: "機能メニュー" }),
    ).toBeVisible();
    auth.authenticated = false;
    await page.evaluate((name) => {
      (name === "focus" ? window : document).dispatchEvent(new Event(name));
    }, event);
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "機能メニュー" }),
    ).not.toBeVisible();
  });

  test(`${event} checks elapsed wall time even if the expiry timer was suspended`, async ({
    page,
  }) => {
    const auth = await mockAuth(page);
    await page.goto("/menu");
    await expect(
      page.getByRole("heading", { name: "機能メニュー" }),
    ).toBeVisible();
    const meCalls = auth.meCalls;
    await page.evaluate((name) => {
      const future = Date.now() + 13 * 60 * 60 * 1000;
      Date.now = () => future;
      (name === "focus" ? window : document).dispatchEvent(new Event(name));
    }, event);
    await expect(page).toHaveURL(/\/login$/);
    expect(auth.meCalls).toBe(meCalls);
  });
}

test("a business 401 never becomes mock data and unmounts protected content", async ({
  page,
}) => {
  const auth = await mockAuth(page);
  auth.businessStatus = 401;
  await page.goto("/simple-chat");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("combobox", { name: "モデル" }),
  ).not.toBeVisible();
  expect(
    auth.requests.some((request) => request.url().endsWith("/llms/")),
  ).toBeTruthy();
});

for (const failure of ["permission", "network"]) {
  test(`business ${failure} is displayed without mock data or logout`, async ({
    page,
  }) => {
    const auth = await mockAuth(page);
    auth.businessStatus = failure === "permission" ? 403 : 200;
    auth.businessOffline = failure === "network";
    await page.goto("/simple-chat");
    await expect(page.getByRole("alert")).toHaveText(
      failure === "permission"
        ? "この操作の権限がありません。"
        : "サーバーに接続できません。通信環境を確認してください。",
    );
    await expect(page).toHaveURL(/\/simple-chat$/);
    await page.getByRole("combobox", { name: "モデル" }).click();
    await expect(page.getByRole("option")).toHaveCount(0);
  });

  test(`me ${failure} hides protected content and supports retry`, async ({
    page,
  }) => {
    const auth = await mockAuth(page);
    auth.meStatus = failure === "permission" ? 403 : 200;
    auth.meOffline = failure === "network";
    await page.goto("/menu");
    await expect(page.getByRole("alert")).toContainText(
      failure === "permission" ? "権限" : "接続できません",
    );
    await expect(
      page.getByRole("heading", { name: "機能メニュー" }),
    ).not.toBeVisible();
    auth.meStatus = 200;
    auth.meOffline = false;
    await page.getByRole("button", { name: "再試行" }).click();
    await expect(
      page.getByRole("heading", { name: "機能メニュー" }),
    ).toBeVisible();
  });
}

test("CSRF login failure is shown and a retry obtains a fresh token", async ({
  page,
}) => {
  const auth = await mockAuth(page, { authenticated: false });
  let rejectLogin = true;
  await page.route("**/api/auth/login/", (route) =>
    rejectLogin
      ? route.fulfill({ status: 403, json: { detail: "CSRF Failed" } })
      : route.fallback(),
  );
  await page.goto("/login");
  await fillLogin(page);
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "CSRFの検証に失敗しました。もう一度お試しください。",
  );
  rejectLogin = false;
  await fillLogin(page);
  await page.getByRole("button", { name: "ログイン", exact: true }).click();
  await expect(page).toHaveURL(/\/menu$/);
  expect(auth.csrfCalls).toBe(2);
});

test("a failed logout retains authentication until the server confirms invalidation", async ({
  page,
}) => {
  const auth = await mockAuth(page);
  auth.logoutOffline = true;
  await page.goto("/menu");
  await page.getByRole("button", { name: "ログアウト", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("接続できません");
  await expect(
    page.getByRole("heading", { name: "機能メニュー" }),
  ).toBeVisible();
  auth.logoutOffline = false;
  await page.getByRole("button", { name: "ログアウト", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "ログイン", exact: true }),
  ).toBeVisible();
  expect(auth.authenticated).toBeFalsy();
});

test("login fits a narrow mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await mockAuth(page, { authenticated: false });
  await page.goto("/login");
  await expect(page.getByLabel("ユーザー名")).toBeVisible();
  await expect(page.getByLabel("パスワード")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "ログイン", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
