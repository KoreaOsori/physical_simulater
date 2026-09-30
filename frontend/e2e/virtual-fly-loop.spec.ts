import { test, expect } from "@playwright/test";

/**
 * docs/42 — the closed-loop virtual fly environment, same SVG-not-WebGL
 * rendering choice as virtual-worm-loop.spec.ts and for the same reason.
 * Per-tick cost is higher here than the worm's (~5s vs ~0.7s in Docker --
 * this circuit has ~2,452 neurons vs the worm's 302), hence the longer
 * timeout. Pinned to the compass (SVG) view -- see virtual-worm-loop.spec.ts.
 */
// docs/45: 호스트 CPU 포화(측정 99.8%) 상황에선 초파리 한 틱이 28-32초까지 걸렸다 -- 원래
// 25초 예산(Docker에서 틱당 ~5초 기준)으론 부족해 넉넉히 늘림. 코드 회귀가 아니라 환경 여유분.
test.setTimeout(180_000);

test("stepping the virtual fly environment advances the tick counter and logs a real event", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("virtual-organism-view", "compass"));
  await page.goto("/lab/virtual-fly");

  await expect(page.getByText("가상 초파리 — 환경 폐루프")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("진행된 틱", { exact: true })).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "다시 시작" }).click();
  await expect(page.getByText("아직 진행된 틱이 없습니다")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "1틱 진행" }).click();

  await expect(page.getByText("최근 틱 로그 (1개, 최신순)")).toBeVisible({ timeout: 120_000 });
  await expect(page.locator(".worm-event-badge").first()).toBeVisible();
});
