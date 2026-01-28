import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading } from '../utils/test-helpers';

/**
 * Pricing Page Object Model
 */
export class PricingPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly pricingTab = 'text=/^pricing$/i, [data-testid="pricing-tab"], a[href*="pricing"]';
  readonly pricingSummary = '[data-testid="pricing-summary"], .pricing-summary, .summary-card';
  readonly exportButton = 'button:has-text("Export"), [data-testid="export-pricing"]';
  readonly exportToExcelButton = 'button:has-text("Export to Excel"), button:has-text("Excel")';
  readonly exportToPDFButton = 'button:has-text("Export to PDF"), button:has-text("PDF")';
  readonly populateButton = 'button:has-text("Populate"), button:has-text("Auto-Fill"), [data-testid="populate-pricing"]';
  readonly priceTable = '[data-testid="price-table"], .pricing-table, table';
  readonly totalCost = '[data-testid="total-cost"], .total-cost';
  readonly adjustPriceButton = 'button:has-text("Adjust"), [data-testid="adjust-price"]';
  readonly approveButton = 'button:has-text("Approve"), [data-testid="approve-pricing"]';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigateToPricingTab() {
    const tab = this.page.locator(this.pricingTab);
    await tab.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step64-pricing-tab-opened');
  }

  async verifyPricingSummary() {
    const summary = this.page.locator(this.pricingSummary);
    await expect(summary).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step65-pricing-summary-displayed');
  }

  async verifyPriceTable() {
    const table = this.page.locator(this.priceTable);
    await expect(table).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step66-price-table-displayed');
  }

  async populatePricing() {
    await this.page.click(this.populateButton);
    await takeScreenshot(this.page, 'step67-populate-pricing-started');

    // Wait for auto-population to complete
    await this.page.waitForTimeout(3000);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step68-pricing-populated-successfully');
  }

  async verifyTotalCost() {
    const total = this.page.locator(this.totalCost);
    await expect(total).toBeVisible({ timeout: 5000 });

    // Verify it contains a number
    const totalText = await total.first().textContent();
    expect(totalText).toMatch(/\d+/);
    await takeScreenshot(this.page, 'step69-total-cost-verified');
  }

  async exportToExcel() {
    await this.page.click(this.exportButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step70-export-options-displayed');

    // Handle download
    const downloadPromise = this.page.waitForEvent('download');
    await this.page.click(this.exportToExcelButton);
    const download = await downloadPromise;

    await takeScreenshot(this.page, 'step71-export-to-excel-successful');

    // Verify download
    expect(download.suggestedFilename()).toContain('.xlsx');
    console.log(`Downloaded: ${download.suggestedFilename()}`);
  }

  async exportToPDF() {
    await this.page.click(this.exportButton);
    await this.page.waitForTimeout(500);

    // Handle download
    const downloadPromise = this.page.waitForEvent('download');
    await this.page.click(this.exportToPDFButton);
    const download = await downloadPromise;

    await takeScreenshot(this.page, 'step-export-to-pdf-successful');

    // Verify download
    expect(download.suggestedFilename()).toContain('.pdf');
    console.log(`Downloaded: ${download.suggestedFilename()}`);
  }

  async adjustPrice(itemCode: string, newPrice: string) {
    const itemRow = this.page.locator(`text="${itemCode}"`).locator('..').locator('..');
    await itemRow.locator(this.adjustPriceButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step72-adjust-price-modal');

    const priceInput = this.page.locator('input[name="price"], input[type="number"]#price');
    await priceInput.fill(newPrice);
    await takeScreenshot(this.page, 'step73-price-adjusted');

    await this.page.click('button[type="submit"], button:has-text("Save")');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step74-price-saved-successfully');
  }

  async approvePricing() {
    await this.page.click(this.approveButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step75-approve-pricing-confirmation');

    await this.page.click('button:has-text("Confirm"), button:has-text("Approve"):not(:disabled)');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step76-pricing-approved-successfully');
  }

  async verifyPriceComparison() {
    const comparisonSection = this.page.locator('[data-testid="price-comparison"], .price-comparison');
    if (await comparisonSection.count() > 0) {
      await expect(comparisonSection).toBeVisible({ timeout: 5000 });
      await takeScreenshot(this.page, 'step-price-comparison-verified');
    }
  }

  async filterByPriceRange(min: string, max: string) {
    const minInput = this.page.locator('input[name="min-price"], #min-price');
    const maxInput = this.page.locator('input[name="max-price"], #max-price');

    if (await minInput.count() > 0) {
      await minInput.fill(min);
      await maxInput.fill(max);
      await this.page.waitForTimeout(1000);
      await takeScreenshot(this.page, `step-filtered-by-price-${min}-${max}`);
    }
  }
}
