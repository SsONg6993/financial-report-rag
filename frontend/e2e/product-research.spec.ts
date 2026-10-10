import { test, expect } from "@playwright/test";

// Optional direct QA backend: real cached data, with source refresh disabled.
test.beforeEach(async ({ page }) => {
  if (process.env.PRODUCT_QA_API) {
    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      const response = await route.fetch({
        url: `${process.env.PRODUCT_QA_API}${url.pathname}${url.search}`,
      });
      await route.fulfill({ response });
    });
  }
});

test("META AAPL RKLB comparisons, concise risks and quote dates", async ({
  page,
}) => {
  for (const ticker of ["META", "AAPL", "RKLB"]) {
    await page.goto(`/research/${ticker}`);
    await expect(
      page.getByRole("heading", { name: "Why It Matters", exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/Quote updated/)).toBeVisible();
    await expect(page.getByText(/Previous close:/)).toBeVisible();
    await expect(page.getByText(/Previous Q[23] 2025:/).first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Key Risks", exact: true }),
    ).toBeVisible();
    const excerpts = page.getByText("View original SEC evidence", {
      exact: true,
    });
    expect(await excerpts.count()).toBeLessThanOrEqual(5);
    if (await excerpts.count()) {
      await expect(excerpts.first().locator("..")).not.toHaveAttribute(
        "open",
        "",
      );
      await excerpts.first().click();
      await expect(excerpts.first().locator("..").locator("p")).toBeVisible();
      await excerpts.first().click();
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    await page.screenshot({
      path: `test-results/product-${ticker}-${test.info().project.name}.png`,
      fullPage: true,
    });
  }
});

test("Ask has structured fallback with sources collapsed and no invented motive", async ({
  page,
}) => {
  await page.goto("/ask");
  await page
    .getByLabel("What would you like to investigate?")
    .fill("Why did Berkshire reduce AAPL?");
  await page
    .getByRole("button", { name: "Ask ThesisLens", exact: true })
    .click();
  for (const title of [
    "Short Answer",
    "Why",
    "Numbers That Matter",
    "What To Watch",
  ]) {
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
  }
  await expect(page.getByText(/does not provide the reason/)).toBeVisible();
  await expect(
    page.getByText(/Sources & evidence/).locator(".."),
  ).not.toHaveAttribute("open", "");
  await page.screenshot({
    path: `test-results/product-ask-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("general AI is intent-routed and identifies a stopped local service", async ({
  page,
}) => {
  await page.goto("/ask");
  await page
    .getByLabel("What would you like to investigate?")
    .fill("How do you think medical AI will develop in the future?");
  await page
    .getByRole("button", { name: "Ask ThesisLens", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "General AI response", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("alert")
      .getByText("Ollama service is not running", { exact: true }),
  ).toBeVisible();
  const response = page.getByRole("article");
  await expect(
    response.getByText(/AAPL|Apple financial statements/i),
  ).toHaveCount(0);
  await expect(
    response.getByText(
      /No private workspace data was sent to an external model/,
    ),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/v31-general-ai-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("holdings preserve verified navigation and explain unknown cost", async ({
  page,
}) => {
  await page.goto("/discover/berkshire");
  const holding = page.locator("article.holding-grid").filter({
    hasText: "APPLE INC",
  });
  await expect(holding.getByRole("link", { name: "Research" })).toHaveAttribute(
    "href",
    "/research/AAPL",
  );
  await holding.getByText(/Estimated entry price/).click();
  await expect(
    holding.getByText(/Actual purchase cost is unknown/),
  ).toBeVisible();

  await page.goto("/discover/pershing");
  const unmapped = page.locator("article.holding-grid").filter({
    hasText: "SYNTHETIC LONG ISSUER NAME WITHOUT VERIFIED TICKER MAPPING",
  });
  await expect(unmapped.getByText("Unmapped security")).toBeVisible();
  await expect(
    unmapped.getByText("No verified research mapping"),
  ).toBeVisible();
  await expect(unmapped.getByRole("link", { name: "Research" })).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/v31-holdings-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("historical chart exposes real periods, top holdings, and source", async ({
  page,
}) => {
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", {
      name: "Historical disclosed concentration",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "2026-03-31", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Berkshire Hathaway · 2026-03-31",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("No interpolation across missing periods"),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Original source ↗" }).last(),
  ).toHaveAttribute("href", /sec\.gov/);
  await page.screenshot({
    path: `test-results/v31-history-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("Ask quarterly numbers and annual context stay separate", async ({
  page,
}) => {
  for (const [ticker, quarter, cash] of [
    ["RKLB", "Q2 2026", "6M 2026 YTD"],
    ["META", "Q2 2026", "6M 2026 YTD"],
    ["AAPL", "Q3 2026", "9M 2026 YTD"],
  ]) {
    await page.goto("/ask");
    await page
      .getByLabel("What would you like to investigate?")
      .fill(`What changed in ${ticker}'s latest quarter?`);
    await page
      .getByRole("button", { name: "Ask ThesisLens", exact: true })
      .click();
    const numbers = page
      .getByRole("heading", { name: "Numbers That Matter", exact: true })
      .locator("..");
    await expect(numbers).toContainText(quarter);
    await expect(numbers).toContainText(cash);
    await expect(numbers).not.toContainText("FY2025");
    await expect(
      page
        .getByRole("heading", { name: "Annual context", exact: true })
        .locator(".."),
    ).toContainText("FY2025");
    await expect(
      page
        .getByRole("heading", { name: "Short Answer", exact: true })
        .locator(".."),
    ).not.toContainText("FY2025");
  }
});

test("runtime dashboard explains dependency state", async ({ page }) => {
  await page.route("**/api/readiness", (route) =>
    route.fulfill({
      json: {
        status: "ready",
        service: "ThesisLens Backend",
        api_version: "0.1.0",
        build_commit: "abc123",
        checked_at: "2026-10-10T00:00:00Z",
        backend: { status: "ready" },
        database: { status: "ready", accessible: true },
        cache: { status: "ready", accessible: true },
        market_pulse: {
          status: "stale_cache",
          detail: "Using retained cache.",
        },
        ollama: {
          status: "model_missing",
          model: "qwen3:4b",
          model_available: false,
          detail: "Download requires approval.",
        },
      },
    }),
  );
  await page.goto("/status");
  await expect(
    page.getByRole("heading", { name: "System status" }),
  ).toBeVisible();
  await expect(page.getByTestId("runtime-market-pulse")).toContainText(
    "Stale cache",
  );
  await expect(page.getByTestId("runtime-general-ai")).toContainText(
    "Model missing",
  );
  await expect(
    page.getByRole("button", { name: "Refresh status" }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/runtime-dashboard-${test.info().project.name}.png`,
    fullPage: true,
  });
});
