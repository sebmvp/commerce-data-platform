import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

async function openContext(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Context" }).click();
}

test("overview loads and attention item can be opened", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("overview-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("environment")).toContainText("DEMO");
  await page.screenshot({
    path: path.join(root, "docs/screenshots/overview.png"),
    fullPage: true,
  });
  const row = page.locator("[data-testid^='attention-']").first();
  await expect(row).toBeVisible();
  await row.click();
  await expect(page.getByTestId("item-view")).toBeVisible();
});

test("item object view shows listing and history", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Inventory" }).click();
  await page.getByTestId("sku-input").fill("j4-military-s");
  await page.getByRole("button", { name: "Load" }).click();
  await expect(page.getByTestId("item-view")).toBeVisible();
  await expect(page.getByTestId("item-state")).toContainText("j4-military-s");
  await expect(page.getByTestId("item-timeline")).toBeVisible();
  await page.screenshot({
    path: path.join(root, "docs/screenshots/item-object.png"),
    fullPage: true,
  });
});

test("app loads a sufficient context bundle", async ({ page }) => {
  await page.goto("/");
  await openContext(page);
  await expect(page.getByTestId("sufficiency")).toContainText("SUFFICIENT", { timeout: 20_000 });
  await expect(page.getByTestId("assembled-question")).toContainText("j4-military-s");
  await expect(page.getByTestId("objects")).toBeVisible();
  await expect(page.getByTestId("relationships")).toBeVisible();
  await expect(page.getByTestId("relationship-map")).toBeVisible();
  await expect(page.getByTestId("facts")).toBeVisible();
  await expect(page.getByTestId("metrics")).toBeVisible();
  await expect(page.getByTestId("history")).toBeVisible();
  await expect(page.getByTestId("provenance")).toBeVisible();
  await expect(page.getByTestId("why")).toBeVisible();
  await expect(page.getByTestId("grounded-output")).toBeVisible({ timeout: 20_000 });
  await page.screenshot({
    path: path.join(root, "docs/screenshots/context-inspector.png"),
    fullPage: true,
  });
});

test("insufficient case makes missing context obvious", async ({ page }) => {
  await page.goto("/");
  await openContext(page);
  await page.getByTestId("question-input").fill("Should I reprice stone-cargo-l?");
  await page.getByRole("button", { name: "Assemble" }).click();
  await expect(page.getByTestId("sufficiency")).toContainText("INSUFFICIENT");
  await expect(page.getByTestId("missing-context")).toBeVisible();
  await expect(page.getByTestId("missing-context")).toContainText("listing");
});

test("relationship node opens item", async ({ page }) => {
  await page.goto("/");
  await openContext(page);
  await expect(page.getByTestId("relationship-map")).toBeVisible({ timeout: 20_000 });
  await page.getByTestId("rel-node-Item-j4-military-s").click();
  await expect(page.getByTestId("item-view")).toBeVisible();
});

test("sandbox reprice can be proposed and approved", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Inventory" }).click();
  await page.getByTestId("sku-input").fill("j4-military-s");
  await page.getByRole("button", { name: "Load" }).click();
  await expect(page.getByTestId("action-panel")).toBeVisible();
  await page.getByTestId("propose-action").click();
  await expect(page.getByTestId("pending-action")).toBeVisible();
  await page.getByTestId("approve-action").click();
  await expect(page.getByTestId("applied-action")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("item-timeline")).toContainText("price_change");
  await openContext(page);
  await page.getByTestId("question-input").fill("Should I reprice j4-military-s?");
  await expect(page.getByRole("button", { name: "Assemble" })).toBeEnabled();
  await page.getByRole("button", { name: "Assemble" }).click();
  await expect(page.getByTestId("sufficiency")).toContainText("SUFFICIENT");
});

test("evaluation reports all 20 cases", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Evaluation" }).click();
  await expect(page.getByTestId("eval-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("eval-total")).toHaveText("20");
  await expect(page.getByTestId("eval-pass")).toHaveText("20");
  await expect(page.getByTestId("eval-fail")).toHaveText("0");
  await expect(page.getByTestId("eval-skip")).toHaveText("0");
});

test("grounded answer abstains when context is insufficient", async ({ page }) => {
  await page.goto("/");
  await openContext(page);
  await page.getByTestId("question-input").fill("Should I reprice stone-cargo-l?");
  await page.getByRole("button", { name: "Assemble" }).click();
  await expect(page.getByTestId("sufficiency")).toContainText("INSUFFICIENT");
  await expect(page.getByTestId("grounded-output")).toContainText("ABSTAIN", { timeout: 20_000 });
});

test("evaluation shows lexical retrieval comparison", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Evaluation" }).click();
  await expect(page.getByTestId("eval-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("eval-compare")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("eval-compare")).toContainText("Lexical retrieval");
  await expect(page.getByTestId("eval-compare")).toContainText("Context Engine");
});

test("temporal as-of question is sufficient", async ({ page }) => {
  await page.goto("/");
  await openContext(page);
  await page
    .getByTestId("question-input")
    .fill("What was the active listing state for j4-military-s two weeks ago?");
  await page.getByRole("button", { name: "Assemble" }).click();
  await expect(page.getByTestId("sufficiency")).toContainText("SUFFICIENT");
  await expect(page.getByTestId("facts")).toContainText("listing_as_of");
});

test("data health loads", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Data Health" }).click();
  await expect(page.getByTestId("health-page")).toBeVisible({ timeout: 20_000 });
});
