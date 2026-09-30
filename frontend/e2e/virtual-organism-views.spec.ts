import { test, expect } from "@playwright/test";

/**
 * docs/44/45 — compass / 3D lab views, real-time manual piloting, source
 * placement and flight on the closed-loop virtual organism pages. The 3D
 * check only asserts the WebGL canvas mounts (no pixel assertions -- see
 * fly-circuit-render.spec.ts for this host's canvas-timing history); the
 * rest runs in the compass view so the keyboard/sensing round trip is
 * checked without WebGL.
 */
// 틱 계산이 호스트 부하에 따라 수 초~수십 초까지 걸린다(docs/45 측정) -- 넉넉히.
test.setTimeout(240_000);

test("3D lab view mounts a WebGL canvas and can switch back to the compass view", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("virtual-organism-view", "lab3d"));
  await page.goto("/lab/virtual-worm");
  await expect(page.getByText("진행된 틱", { exact: true })).toBeVisible({ timeout: 60_000 });

  await expect(page.locator(".vo-stage.lab3d canvas")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "추적 카메라" })).toBeVisible();

  await page.getByRole("button", { name: "나침반" }).click();
  await expect(page.locator(".vo-compass-wrap svg")).toBeVisible();
  await expect(page.locator(".vo-stage canvas")).toHaveCount(0);
});

test("manual piloting moves the worm in real time with W while the real network keeps sensing", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("virtual-organism-view", "compass"));
  await page.goto("/lab/virtual-worm");
  await expect(page.getByText("진행된 틱", { exact: true })).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "다시 시작" }).click();
  await expect(page.getByText("아직 진행된 틱이 없습니다")).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "수동 조종" }).click();
  await expect(page.getByRole("button", { name: "1틱 진행" })).toBeDisabled();
  await page.getByRole("button", { name: "20×" }).click();
  // 조종 중 Space/방향키가 포커스된 버튼을 누르거나 페이지를 스크롤하지 않아야 한다
  await page.getByRole("button", { name: "20×" }).focus();
  await page.keyboard.press(" ");
  await expect(page.getByRole("button", { name: "자동 재생" })).toHaveAttribute("aria-pressed", "false");

  await page.keyboard.down("w");
  await page.waitForTimeout(2000);
  await page.keyboard.up("w");

  // 수동 감지 루프가 스스로 서버 틱을 돌린다(버튼 없이) -- 이동 거리가 실제로 기록된다
  await expect(page.locator(".lab-event-row").first()).toContainText("수동", { timeout: 90_000 });
  await expect(async () => {
    const text = await page.locator(".vo-stats .lab-metric").nth(1).locator("strong").innerText();
    expect(parseFloat(text)).toBeGreaterThan(1);
  }).toPass({ timeout: 90_000 });
  await expect(page.locator(".vo-brain-note")).toContainText("뇌의 결정");

  await page.getByRole("button", { name: "자동(커넥톰)" }).click();
  await expect(page.getByRole("button", { name: "1틱 진행" })).toBeEnabled({ timeout: 60_000 });
});

test("placing the odor source by clicking the arena moves it and restarts the episode", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("virtual-organism-view", "compass"));
  await page.goto("/lab/virtual-worm");
  await expect(page.getByText("진행된 틱", { exact: true })).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "냄새원 옮기기" }).click();
  await expect(page.locator(".vo-hud-place")).toBeVisible();
  const svg = page.locator(".vo-compass-wrap svg");
  const box = (await svg.boundingBox())!;
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2); // 아레나 중앙
  await expect(page.locator(".vo-hud-place")).toHaveCount(0);
  await expect(async () => {
    const cx = parseFloat((await svg.locator('circle[r="0.03"]').getAttribute("cx")) ?? "9");
    const cy = parseFloat((await svg.locator('circle[r="0.03"]').getAttribute("cy")) ?? "9");
    expect(Math.hypot(cx, cy)).toBeLessThan(0.05);
  }).toPass({ timeout: 15_000 });
});

test("the fly takes off while Space is held in manual mode", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("virtual-organism-view", "compass"));
  await page.goto("/lab/virtual-fly");
  await expect(page.getByText("진행된 틱", { exact: true })).toBeVisible({ timeout: 60_000 });

  await page.getByRole("button", { name: "수동 조종" }).click();
  await page.keyboard.down(" ");
  await expect(page.getByText(/비행 중 · 고도/)).toBeVisible({ timeout: 5_000 });
  await page.keyboard.up(" ");
  // 떼면 서서히 내려와 착지
  await expect(page.getByText(/비행 중 · 고도/)).toHaveCount(0, { timeout: 15_000 });
  await page.getByRole("button", { name: "자동(커넥톰)" }).click();
});
