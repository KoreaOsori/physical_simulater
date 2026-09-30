import { test, expect } from "@playwright/test";

/**
 * docs/26-worm-classic-ablation-behavior.md's feature: toggling a classic
 * ablation on should select it (and, per AblationPanel.tsx, ride along on
 * the next command as `silenced_neuron_ids` -- not asserted here, that's
 * covered by the backend's test_silencing_the_stimulated_neuron_collapses_
 * downstream_propagation). This test covers the fetch -> render -> toggle
 * chain, mirroring human-disorder-highlight.spec.ts one level down.
 */
test("toggling a classic ablation shows its description and neuron list", async ({ page }) => {
  await page.goto("/");

  const button = page.getByRole("button", { name: /후진 지휘 인터뉴런/ });
  await expect(button).toBeVisible({ timeout: 15_000 });

  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");

  const detail = page.locator(".ablation-detail");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText("AVAL");

  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "false");
  await expect(detail).toBeHidden();
});
