import { test, expect } from "@playwright/test";
import { mockAuth } from "./auth-mock";

const MENU_HEADING = "機能メニュー";

test.describe("Start page navigation", () => {
  test("renders landing page and navigates to menu", async ({ page }) => {
    await mockAuth(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const startButton = page.getByRole("button", { name: /start/i });
    await expect(startButton).toBeVisible();

    await startButton.click();
    await expect(page).toHaveURL(/\/menu$/);

    await expect(
      page.getByRole("heading", {
        name: MENU_HEADING,
      }),
    ).toBeVisible();

    await expect(
      page.getByText("シンプルチャット", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("データソース管理", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "ログアウト", exact: true }),
    ).toBeVisible();
  });
});
