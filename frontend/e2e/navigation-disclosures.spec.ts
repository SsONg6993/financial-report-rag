import { expect, test } from "@playwright/test";

test("primary navigation stays concise and old Discover URLs remain compatible", async ({
  page,
}) => {
  await page.goto("/discover");
  await expect(page).toHaveURL(/\/explore$/);

  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  await expect(navigation.getByRole("link")).toHaveCount(4);
  for (const name of ["Home", "Explore", "Intelligence", "Ask AI"]) {
    await expect(
      navigation.getByRole("link", { name, exact: true }),
    ).toBeVisible();
  }
  await expect(
    page.getByRole("link", { name: "System status and settings" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Explore sections" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/navigation-${test.info().project.name}.png`,
  });
});

test("public disclosure card separates verified rows from review diagnostics", async ({
  page,
}) => {
  await page.route("**/api/public-officials", async (route) => {
    await route.fulfill({
      json: [
        {
          person: "Example Official",
          disclosure_type: "Periodic transaction report (OGE 278-T)",
          filing_date: "",
          source_document_date: "2026-05-08",
          certification_date: "2026-05-13",
          source_url: "https://www.oge.gov/example-278t.pdf",
          notes: ["Ranges are preserved."],
          records: [
            {
              asset_name: "Example Security",
              transaction_type: "Purchase",
              amount_range: "$1,001 - $15,000",
              transaction_date: "2026-03-27",
              filing_date: "",
              source_url: "https://www.oge.gov/example-278t.pdf",
              page: 2,
              source_text: "1 | Example Security | Purchase",
              confidence: "high",
            },
          ],
          extraction: {
            status: "partial_verified",
            method: "layout_aware_table",
            text_layer_status: "degraded",
            ocr_used: false,
            pages_total: 3,
            pages_with_text: 3,
            pages_with_tables: 2,
            raw_fragment_count: 8,
            candidate_count: 2,
            verified_count: 1,
            rejected_count: 1,
            deduplicated_count: 0,
            coverage_rate: 0.5,
            confidence: "moderate",
            rejection_reasons: { invalid_transaction_date: 1 },
          },
        },
      ],
    });
  });

  await page.goto("/explore");
  const card = page.getByTestId("public-disclosure-card");
  await expect(card.getByText("Example Official")).toBeVisible();
  await expect(card.getByText("Filing date not verified", { exact: false })).toBeVisible();
  await expect(card.getByText("50.0%", { exact: true })).toBeVisible();
  await expect(card.getByRole("cell", { name: "Example Security" })).toBeVisible();
  await card.getByText("Technical extraction details").click();
  await expect(card.getByText("invalid transaction date: 1")).toBeVisible();
  await page.addStyleTag({ content: "header { visibility: hidden !important; }" });
  await card.screenshot({
    path: `test-results/public-disclosure-${test.info().project.name}.png`,
  });

  await card.getByPlaceholder("Filter by asset").fill("missing");
  await expect(card.getByText("Showing 0 of 1 verified rows")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true);
});

test("zero verified rows is review-required, not a no-transactions claim", async ({
  page,
}) => {
  await page.route("**/api/public-officials", async (route) => {
    await route.fulfill({
      json: [
        {
          person: "Example Official",
          disclosure_type: "Periodic transaction report (OGE 278-T)",
          filing_date: "",
          source_document_date: "2026-05-08",
          certification_date: "",
          source_url: "https://www.oge.gov/example-278t.pdf",
          notes: [],
          records: [],
          extraction: {
            status: "review_required",
            method: "layout_aware_table",
            text_layer_status: "unusable",
            ocr_used: false,
            pages_total: 2,
            pages_with_text: 0,
            pages_with_tables: 0,
            raw_fragment_count: 0,
            candidate_count: 0,
            verified_count: 0,
            rejected_count: 0,
            deduplicated_count: 0,
            coverage_rate: 0,
            confidence: "low",
            rejection_reasons: {},
          },
        },
      ],
    });
  });

  await page.goto("/explore");
  await expect(page.getByText("Review required", { exact: true })).toBeVisible();
  await expect(
    page.getByText("This does not mean no transactions occurred", {
      exact: false,
    }),
  ).toBeVisible();
});
