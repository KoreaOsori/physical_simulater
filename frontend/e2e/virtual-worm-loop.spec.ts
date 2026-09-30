import { test, expect } from "@playwright/test";

/**
 * docs/41 — the closed-loop virtual worm environment. Unlike the rest of
 * this project's worm pages, this one deliberately renders the arena as
 * inline SVG (not a WebGL canvas) precisely to avoid the canvas-mount
 * flakiness this project's other e2e specs have repeatedly hit on this
 * host (see fly-circuit-render.spec.ts's documented transient failures) --
 * this test can therefore assert on plain DOM text instead of polling a
 * `window.__*` bridge.
 *
 * docs/44 added a 3D lab view (now the default) -- this spec pins the
 * compass (SVG) view via the page's remembered-view key so it stays
 * WebGL-free; the 3D view has its own spec (virtual-organism-views.spec.ts).
 */
test("stepping the virtual worm environment advances the tick counter and logs a real event", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("virtual-organism-view", "compass"));
  await page.goto("/lab/virtual-worm");

  await expect(page.getByText("가상 예쁜꼬마선충 — 환경 폐루프")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("진행된 틱", { exact: true })).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "다시 시작" }).click();
  await expect(page.getByText("아직 진행된 틱이 없습니다")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "1틱 진행" }).click();

  // A real Brian2 run happens server-side per tick (~1s in Docker) -- poll
  // rather than assume instant completion.
  await expect(page.getByText("최근 틱 로그 (1개, 최신순)")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".worm-event-badge").first()).toBeVisible();
});
