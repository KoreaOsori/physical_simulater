import { defineConfig, devices } from "@playwright/test";

/**
 * E2E regression tests (docs/24-e2e-regression-tests.md) — targets the
 * already-running app (dev server or the docker-compose stack), same as
 * this project's own "실제 브라우저로 확인" convention, just automated.
 *
 * Run against `pnpm dev` (default, http://localhost:3000) or against the
 * docker-compose stack by setting PLAYWRIGHT_BASE_URL:
 *
 *   pnpm exec playwright test
 *   PLAYWRIGHT_BASE_URL=http://localhost:3000 pnpm exec playwright test
 *
 * Does NOT start the app itself (no `webServer` block) -- the backend must
 * already be reachable too (worm/fly/human WS + REST), which only the
 * docker-compose stack or `pnpm dev` + `uvicorn` together provide, so
 * auto-starting just the frontend here would produce confusing failures.
 */
export default defineConfig({
  testDir: "./e2e",
  // The worm test alone polls up to 25s for a real staggered command
  // sequence to land (see worm-locomotion.spec.ts's timing note) -- default
  // 30s leaves too little margin once page load/WS handshake is added on
  // top, especially under host CPU contention from unrelated processes.
  timeout: 60_000,
  fullyParallel: false, // shares one backend's WS connections; keep runs simple/serial
  workers: 1, // one shared Brian2 backend -- concurrent HH runs would skew timing-sensitive specs
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
