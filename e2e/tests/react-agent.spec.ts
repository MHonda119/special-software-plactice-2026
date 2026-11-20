import { test, expect, type Page } from "@playwright/test";
import { mockAuth } from "./auth-mock";

const sessionUuid = "550e8400-e29b-41d4-a716-446655440002";
const chatPath = "/chat?agentId=1&agentName=Stationery&usecaseType=REACT_CHAT";

async function mockReAct(page: Page) {
  await mockAuth(page);
  const state = {
    agent: {
      id: 1,
      name: "Stationery",
      usecase_type: "REACT_CHAT",
      llm: 1,
      system_prompt: "日本語で回答する。",
      config: { max_steps: 8 },
      is_active: true,
    },
    messages: [] as Array<{
      id: number;
      role: string;
      content: string;
      usage?: object;
    }>,
    executions: [] as Array<{ input: string; session_uuid?: string }>,
    saved: [] as Array<{
      usecase_type: string;
      config: { max_steps?: number; temperature?: number };
    }>,
    status: 200,
    pending: null as Promise<void> | null,
  };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/llms/")
      return route.fulfill({
        json: [
          {
            id: 1,
            name: "GPT-6 luna",
            provider: "OPENAI",
            model: "gpt-6-luna",
            is_active: true,
          },
          {
            id: 2,
            name: "Gemma",
            provider: "OLLAMA",
            model: "gemma3:270m",
            is_active: true,
          },
        ],
      });
    if (path === "/api/datasources/") return route.fulfill({ json: [] });
    if (path === "/api/agents/" || path === "/api/agents/1/") {
      if (["POST", "PATCH"].includes(request.method())) {
        const body = request.postDataJSON();
        state.saved.push(body);
        state.agent = { ...state.agent, ...body };
        return route.fulfill({
          status: request.method() === "POST" ? 201 : 200,
          json: state.agent,
        });
      }
      return route.fulfill({
        json: path === "/api/agents/" ? [state.agent] : state.agent,
      });
    }
    if (path === "/api/sessions/")
      return route.fulfill({
        json: state.messages.length
          ? [{ uuid: sessionUuid, llm: 1, agent: 1, title: "文房具の会話" }]
          : [],
      });
    if (path === `/api/sessions/${sessionUuid}/messages/`)
      return route.fulfill({ json: state.messages });
    if (path === "/api/agents/1/execute/") {
      const body = request.postDataJSON();
      state.executions.push(body);
      if (state.pending) await state.pending;
      if (state.status !== 200)
        return route.fulfill({
          status: state.status,
          json: { detail: "ReAct execution failed" },
        });
      const usage = { input_tokens: 8, output_tokens: 4, total_tokens: 12 };
      const answer = {
        id: state.messages.length + 2,
        role: "assistant",
        content: body.input.includes("ペン")
          ? "お釣りは260円です。"
          : "お釣りは250円です。",
        usage,
      };
      state.messages.push(
        { id: state.messages.length + 1, role: "user", content: body.input },
        answer,
      );
      return route.fulfill({
        json: {
          agent_id: 1,
          session_uuid: sessionUuid,
          result: { message: answer },
          usage,
        },
      });
    }
    return route.fallback();
  });
  return state;
}

test("ReAct form validates OPENAI and step limits and preserves edits", async ({
  page,
}) => {
  const state = await mockReAct(page);
  await page.goto("/agent/new");
  await page.getByLabel("エージェント名").fill("Stationery");
  await page
    .getByRole("combobox", { name: "ユースケース", exact: true })
    .click();
  await page
    .getByRole("option", { name: "ReActチャット", exact: true })
    .click();
  await expect(page.getByLabel("temperature", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("データソース", { exact: true })).toHaveCount(0);
  await page.getByRole("combobox", { name: "LLM", exact: true }).click();
  await expect(page.getByRole("option", { name: /Gemma/ })).toBeDisabled();
  await page.getByRole("option", { name: /GPT-6 luna/ }).click();
  const limit = page.getByLabel("モデル問い合わせ上限 (max_steps)");
  await expect(limit).toHaveValue("8");
  await limit.fill("9");
  await expect(
    page.getByRole("button", { name: "作成する", exact: true }),
  ).toBeDisabled();
  await limit.fill("1.5");
  await expect(
    page.getByRole("button", { name: "作成する", exact: true }),
  ).toBeDisabled();
  await limit.fill("6");
  await page.getByRole("button", { name: "作成する", exact: true }).click();
  await expect(page).toHaveURL(/\/agent$/);
  expect(state.saved[0].usecase_type).toBe("REACT_CHAT");
  expect(state.saved[0].config).toEqual({ max_steps: 6 });
  await page.goto("/agent/1/edit");
  await expect(limit).toHaveValue("6");
  await limit.fill("8");
  await page.getByRole("button", { name: "更新する", exact: true }).click();
  await expect(page).toHaveURL(/\/agent$/);
  expect(state.saved[1].config).toEqual({ max_steps: 8 });
});

test("ReAct waits, prevents duplicate sends, resumes the Agent and reloads usage", async ({
  page,
}) => {
  const state = await mockReAct(page);
  let release = () => {};
  state.pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.goto(chatPath);
  await expect(page.getByRole("status")).toContainText("ReAct: 待機中");
  await page
    .getByLabel("メッセージ", { exact: true })
    .fill("ノート3冊を買って1000円を支払うと？");
  await page.getByRole("button", { name: "送信", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("ReAct: 実行中");
  await expect(
    page.getByRole("button", { name: "送信", exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel("メッセージ", { exact: true })).toBeDisabled();
  await page.keyboard.press("Enter");
  await expect.poll(() => state.executions.length).toBe(1);
  release();
  await expect(
    page.getByText("お釣りは250円です。", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("ReAct: 完了");
  await expect(page).toHaveURL(
    new RegExp(`/chat/${sessionUuid}.*usecaseType=REACT_CHAT`),
  );
  await page.goto("/simple-chat");
  await page.getByRole("button", { name: "文房具の会話", exact: true }).click();
  await expect(page).toHaveURL(
    new RegExp(`/chat/${sessionUuid}.*agentId=1.*usecaseType=REACT_CHAT`),
  );
  await page
    .getByLabel("メッセージ", { exact: true })
    .fill("ではペン2本を買って500円なら？");
  await page.getByRole("button", { name: "送信", exact: true }).click();
  await expect(
    page.getByText("お釣りは260円です。", { exact: true }),
  ).toBeVisible();
  expect(state.executions[1].session_uuid).toBe(sessionUuid);
  expect(state.messages).toHaveLength(4);
  await page.reload();
  await expect(page.getByRole("status")).toContainText("ReAct: 完了");
  await expect(
    page.getByText("入力 8 / 出力 4 tokens", { exact: true }),
  ).toHaveCount(2);
  await page.screenshot({
    path: "/tmp/react-agent-desktop.png",
    fullPage: true,
  });
  await expect
    .poll(async () => {
      const title = await page
        .getByRole("heading", { name: "Stationery", exact: true })
        .boundingBox();
      const authBar = await page.locator("header").first().boundingBox();
      return Boolean(title && authBar && title.y >= authBar.y + authBar.height);
    })
    .toBeTruthy();
  const composer = await page
    .getByLabel("メッセージ", { exact: true })
    .locator("..")
    .locator("..")
    .boundingBox();
  expect(composer).not.toBeNull();
  expect(composer!.y + composer!.height).toBeLessThanOrEqual(
    page.viewportSize()!.height,
  );
});

for (const status of [422, 502, 504]) {
  test(`ReAct ${status} restores input without a phantom message and allows retry`, async ({
    page,
  }) => {
    const state = await mockReAct(page);
    state.status = status;
    await page.goto(chatPath);
    const question = "ノート3冊のお釣りは？";
    await page.getByLabel("メッセージ", { exact: true }).fill(question);
    await page.getByRole("button", { name: "送信", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("ReAct: 失敗");
    await expect(page.getByRole("alert")).toContainText(String(status));
    await expect(page.getByLabel("メッセージ", { exact: true })).toHaveValue(
      question,
    );
    await expect(page.getByText(question, { exact: true })).toHaveCount(0);
    expect(state.messages).toHaveLength(0);
    state.status = 200;
    await page.getByRole("button", { name: "送信", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("ReAct: 完了");
    expect(state.messages).toHaveLength(2);
  });
}

test("ReAct mobile fits and blocks input over 2000 characters", async ({
  page,
}) => {
  await mockReAct(page);
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(chatPath);
  const input = page.getByLabel("メッセージ", { exact: true });
  await input.fill("x".repeat(2001));
  await expect(
    page.getByRole("button", { name: "送信", exact: true }),
  ).toBeDisabled();
  await input.fill("ノート3冊のお釣りは？");
  await page.getByRole("button", { name: "送信", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("ReAct: 完了");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  const composer = await input.locator("..").locator("..").boundingBox();
  expect(composer).not.toBeNull();
  expect(composer!.y + composer!.height).toBeLessThanOrEqual(
    page.viewportSize()!.height,
  );
  await page.screenshot({
    path: "/tmp/react-agent-mobile.png",
    fullPage: true,
  });
});
