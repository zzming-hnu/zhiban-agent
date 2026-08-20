import { expect, test } from "@playwright/test";

const UNIQUE = Date.now().toString(36);

test.describe("知伴主路径", () => {
  test("注册 → 登录态保持 → 访问记忆/待办页", async ({ page }) => {
    const email = `e2e-${UNIQUE}@example.com`;
    const password = "password123";

    // 注册
    await page.goto("/login");
    await page.getByRole("button", { name: "注册" }).click();
    await page.getByLabel("邮箱").fill(email);
    await page.getByLabel("密码").fill(password);
    await page.getByRole("button", { name: "注册", exact: true }).click();

    // 跳转到聊天页，显示邮箱
    await page.waitForURL("**/chat");
    await expect(page.getByText(email)).toBeVisible();

    // 直接导航到记忆页（登录态应保持）
    await page.goto("/memories");
    await expect(page.getByText("我的记忆").first()).toBeVisible();

    // 直接导航到待办页
    await page.goto("/todos");
    await expect(page.getByText("待办与提醒").first()).toBeVisible();
  });

  test("未登录访问受保护页跳转登录", async ({ page }) => {
    await page.goto("/chat");
    await page.waitForURL("**/login");
  });
});
