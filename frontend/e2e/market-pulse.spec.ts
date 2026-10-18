import { expect, test } from "@playwright/test";

const id = "0123456789abcdefabcd";
const impact = {
  event_id: id,
  ticker: "DAL",
  company: "Delta · synthetic test",
  impact_type: "POTENTIAL_HEADWIND",
  horizon: "NEAR_TERM",
  evidence_strength: "STRONG",
  explanation:
    "Higher fuel costs may pressure margins; not a price prediction.",
  company_exposure: "Jet fuel is a material operating cost.",
  mechanism: [
    "Oil price increase",
    "Jet fuel input cost",
    "Potential operating-margin pressure",
  ],
  confidence: "Exposure support, not price direction",
  evidence_refs: [
    {
      text: "Jet fuel is a material operating cost.",
      source_url: "https://example.org/test-filing",
      date: "2026-06-30",
      source: "Synthetic filing fixture",
    },
  ],
  watched: true,
  portfolio_context: [
    {
      investor_id: "berkshire",
      investor: "Berkshire · synthetic test",
      reporting_period: "2026-06-30",
      filing_date: "2026-08-14",
      source_url: "https://example.org/disclosure",
      source_type: "SEC Form 13F",
      note: "Reported disclosure, not confirmation of today's position",
    },
  ],
  judgment: null,
};
const event = {
  id,
  headline: "Test oil supply event",
  summary: "Synthetic browser fixture, never served by live app.",
  category: "Energy",
  source: "Test primary source",
  source_url: "https://example.org/test-event",
  published_at: "2026-09-26T10:00:00Z",
  event_time: null,
  regions: [],
  sectors: ["Energy"],
  importance: "NORMAL",
  cached_at: "2026-09-26T12:00:00Z",
  freshness: "2 HOURS AGO · STALE CACHE",
  stale: true,
  recent: true,
  what_happened: "Oil prices rose in this synthetic test fixture.",
  why_it_matters: "Oil → fuel cost → potential margin sensitivity",
  what_to_watch: "Duration and company fuel exposure.",
  generator: "Extractive fallback",
  related_sources: [],
  impacts: [impact],
  watchlist_relevant: true,
  portfolio_relevant: true,
};
const feed = {
  events: [event],
  providers: [
    {
      source: "Test primary source",
      checked_at: "2026-09-26T12:00:00Z",
      successful_at: "2026-09-26T10:00:00Z",
      error: "Source unavailable; cache retained",
      stale: true,
    },
  ],
  as_of: "2026-09-26T12:00:00Z",
  watchlist_event_count: 1,
  coverage: "Test evidence coverage",
};

test.beforeEach(async ({ page }) => {
  // Never let synthetic navigation trigger refreshes against the user's backend.
  await page.route("**/api/**", async (route) => {
    return route.fulfill({
      status: 503,
      json: { detail: "Isolated QA unavailable" },
    });
  });
  await page.route("**/api/market-pulse**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/refresh"))
      return route.fulfill({
        json: { status: "Refresh requested; cooldowns apply." },
      });
    return route.fulfill({
      json: path.endsWith(id)
        ? {
            ...event,
            reactions: [
              {
                ticker: "DAL",
                label:
                  "Observed after the event; correlation/context, not proof of causation.",
                reference_price: null,
                day_1_return: null,
                day_5_return: null,
                source_url: null,
              },
            ],
            reaction_note:
              "Timestamp-aligned price history unavailable. No reaction is estimated.",
          }
        : feed,
    });
  });
});

test("event → mechanism → evidence → research, with stale and disclosure labels", async ({
  page,
}) => {
  await page.goto("/market-pulse");
  await expect(
    page.getByRole("heading", { name: "Events. Exposure. Evidence." }),
  ).toBeVisible();
  await expect(page.getByText("2 HOURS AGO · STALE CACHE")).toBeVisible();
  await page.getByLabel("Watchlist only").check();
  await expect(page.getByTestId("pulse-event")).toHaveCount(1);
  await page.getByRole("link", { name: "View impact & evidence" }).click();
  await expect(
    page.getByRole("heading", { name: "Potentially affected companies" }),
  ).toBeVisible();
  await expect(
    page.getByText("potential headwind", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("View company exposure & supporting evidence", { exact: true })
    .click();
  await expect(
    page.getByText("Evidence date 2026-06-30", { exact: false }),
  ).toBeVisible();
  await page
    .getByText("Followed public portfolio context", { exact: true })
    .click();
  await expect(
    page.getByText(/not confirmation of today's position/),
  ).toBeVisible();
  await page
    .getByText("Observed market reaction · observation, not causality", {
      exact: true,
    })
    .click();
  await expect(page.getByText(/No reaction is estimated/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await page.screenshot({
    path: `test-results/pulse-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Research DAL", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/research/DAL\\?event=${id}`));
  await expect(
    page.getByRole("complementary", { name: "Market Pulse research context" }),
  ).toContainText("Test oil supply event");
});

test("empty feed and earlier coverage are not presented as latest", async ({
  page,
}) => {
  await page.route("**/api/market-pulse", (route) =>
    route.fulfill({ json: { ...feed, events: [], watchlist_event_count: 0 } }),
  );
  await page.goto("/market-pulse");
  await expect(
    page.getByRole("heading", { name: "No recent events cached yet" }),
  ).toBeVisible();
  await page.getByLabel("Watchlist only").check();
  await expect(
    page.getByRole("heading", { name: "No supported watchlist matches yet" }),
  ).toBeVisible();
});

test("source failure is distinct from an empty successful cache", async ({
  page,
}) => {
  await page.route("**/api/market-pulse", (route) =>
    route.fulfill({
      json: {
        ...feed,
        events: [],
        watchlist_event_count: 0,
        status: "source_unavailable",
        diagnostic:
          "Market Pulse sources are unavailable and no successful cached events exist.",
        skipped_candidate_count: 0,
      },
    }),
  );
  await page.goto("/market-pulse");
  await expect(
    page.getByRole("heading", {
      name: "Market Pulse sources are unavailable",
    }),
  ).toBeVisible();
  await expect(
    page.getByText(/no successful cached events exist/i),
  ).toBeVisible();
});

test("live cached Pulse page has source labels without causal claims", async ({
  page,
}) => {
  test.skip(!process.env.PRODUCT_QA_API, "Needs isolated real cached backend");
  await page.unroute("**/api/market-pulse**");
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const response = await route.fetch({
      url: `${process.env.PRODUCT_QA_API}${url.pathname}${url.search}`,
    });
    await route.fulfill({ response });
  });
  await page.goto("/market-pulse");
  await expect(
    page.getByRole("heading", { name: "Events. Exposure. Evidence." }),
  ).toBeVisible();
  await expect(page.getByTestId("pulse-event").first()).toBeVisible();
  await expect(page.getByText(/Published/).first()).toBeVisible();
  await expect(page.getByText(/Event time:/).first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/pulse-live-${test.info().project.name}.png`,
    fullPage: true,
  });
  const response = await page.request.get(
    `${process.env.PRODUCT_QA_API}/api/market-pulse`,
  );
  const cached = await response.json();
  const ai = cached.events.find(
    (item: { category: string }) => item.category === "Artificial Intelligence",
  );
  if (ai) {
    await page.goto(`/market-pulse/${ai.id}`);
    await expect(
      page.getByRole("heading", { name: ai.headline, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Research NVDA", exact: true }),
    ).toBeVisible();
    const nvda = page.getByTestId("pulse-impact").filter({
      has: page.getByRole("link", { name: "Research NVDA", exact: true }),
    });
    await nvda
      .getByText("View company exposure & supporting evidence", { exact: true })
      .click();
    await expect(nvda.getByText(/Evidence date/).first()).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    await page.screenshot({
      path: `test-results/pulse-live-detail-${test.info().project.name}.png`,
      fullPage: true,
    });
  }
});
