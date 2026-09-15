import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

async function ask(page: import("@playwright/test").Page, question: string) {
  await page.getByTestId("question-input").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

test("overview loads and attention rows deep-link to object view", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("overview-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("environment")).toHaveAttribute("data-env", "demo");
  await expect(page.locator("[data-testid^='attention-']").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.locator("[data-testid^='attention-']").first()).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(root, "docs/screenshots/overview.png"), fullPage: true });
  const row = page.locator("[data-testid^='attention-']").first();
  await row.click();
  await expect(page.getByTestId("item-view")).toBeVisible();
  await expect(page).toHaveURL(/\/inventory\//);
});

test("browser back and forward navigate routes", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-inventory").click();
  await expect(page.getByTestId("inventory-page")).toBeVisible();
  await page.getByTestId("nav-librarian").click();
  await expect(page.getByTestId("librarian-page")).toBeVisible();
  await page.goBack();
  await expect(page.getByTestId("inventory-page")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("librarian-page")).toBeVisible();
});

test("deep link opens object view after refresh", async ({ page }) => {
  await page.goto("/inventory/j4-military-s");
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await page.reload();
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("item-state")).toBeVisible();
  await expect(page.getByTestId("item-timeline")).toBeVisible();
  await page.screenshot({ path: path.join(root, "docs/screenshots/item-object.png"), fullPage: true });
});

test("inventory search and status filter work via URL", async ({ page }) => {
  await page.goto("/inventory?status=owned");
  await expect(page.getByTestId("inventory-page")).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/status=owned/);
  await expect(page.locator("[data-testid^='inv-row-']").first()).toBeVisible();
  const ownedCount = await page.locator("[data-testid^='inv-row-']").count();
  expect(ownedCount).toBeGreaterThan(0);

  await page.getByTestId("inventory-search").fill("Jordan");
  const filteredCount = await page.locator("[data-testid^='inv-row-']").count();
  expect(filteredCount).toBeLessThan(ownedCount);

  await page.getByTestId("inv-filter-sold").click();
  await expect(page).toHaveURL(/status=sold/);
  await expect(page.locator("[data-testid^='inv-row-']").first()).toBeVisible();
});

test("librarian answers a bound sufficient question", async ({ page }) => {
  await page.goto("/librarian/j4-military-s");
  await expect(page.getByTestId("bound-chip")).toBeVisible();
  await ask(page, "Should I reprice j4-military-s?");
  await expect(page.getByTestId("sufficiency")).toContainText("sufficient", { timeout: 25_000 });
  await expect(page.getByTestId("assembled-question")).toContainText("j4-military-s");
  await expect(page.getByTestId("cited-evidence")).toContainText(/Watch rate|Watchers|Listing age|Asking price/i);
  await expect(page.getByTestId("relationship-map")).toBeVisible();
  await expect(page.getByTestId("facts")).toBeVisible();
  await expect(page.getByTestId("metrics")).toBeVisible();
  await expect(page.getByTestId("history")).toBeVisible();
  await expect(page.getByTestId("provenance")).toBeVisible();
  await page.screenshot({ path: path.join(root, "docs/screenshots/librarian.png"), fullPage: true });
});

test("insufficient case makes missing context obvious with remediation", async ({ page }) => {
  await page.goto("/librarian/stone-cargo-l");
  await ask(page, "Should I reprice stone-cargo-l?");
  await expect(page.getByTestId("missing-context")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId("missing-context")).toContainText("listing");
  await expect(page.getByTestId("missing-context")).toContainText("Inspect this object");
});

test("unbound Librarian answers a temporal as-of question", async ({ page }) => {
  await page.goto("/librarian");
  await ask(page, "What was the active listing state for j4-military-s two weeks ago?");
  await expect(page.getByTestId("sufficiency")).toContainText("sufficient", { timeout: 25_000 });
  await expect(page.getByTestId("facts")).toContainText(/listing as-of/i);
});

test("relationship node opens the item object view", async ({ page }) => {
  await page.goto("/librarian/j4-military-s");
  await ask(page, "Should I reprice j4-military-s?");
  await expect(page.getByTestId("relationship-map")).toBeVisible({ timeout: 25_000 });
  await page.getByTestId("rel-node-Item-j4-military-s").click();
  await expect(page.getByTestId("item-view")).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/inventory\/j4-military-s/);
});

test("sandbox reprice can be proposed and approved", async ({ page }) => {
  await page.goto("/inventory/j4-military-s");
  await expect(page.getByTestId("action-panel")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("sandbox-price").fill("620");
  await page.getByTestId("propose-action").click();
  await expect(page.getByTestId("pending-action")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("approve-action").click();
  await expect(page.getByTestId("applied-action")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId("item-timeline")).toContainText(/price/i);
  // next Librarian query sees the new state
  await page.getByTestId("ask-librarian").click();
  await expect(page).toHaveURL(/\/librarian\/j4-military-s/);
  await ask(page, "Should I reprice j4-military-s?");
  await expect(page.getByTestId("sufficiency")).toContainText("sufficient", { timeout: 25_000 });
});

test("evaluation reports every gold case with layer cards", async ({ page }) => {
  await page.goto("/evaluation");
  await expect(page.getByTestId("eval-summary")).toBeVisible({ timeout: 40_000 });
  await expect(page.getByTestId("eval-compare")).toContainText("Context assembly");
  await expect(page.getByTestId("lexical")).toContainText("Lexical retrieval");
  await expect(page.locator("[data-testid^='eval-case-']").first()).toBeVisible();
});

test("data health shows trust banner and sources", async ({ page }) => {
  await page.goto("/data-health");
  await expect(page.getByTestId("health-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("trust-banner")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("coverage")).toBeVisible();
});

test("loading shows skeletons instead of raw Loading", async ({ page }) => {
  await page.goto("/inventory");
  await expect(page.getByTestId("inventory-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Loading", { exact: true })).toHaveCount(0);
});
