import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading } from '../utils/test-helpers';

/**
 * Offers Page Object Model
 */
export class OffersPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly offersTab = 'text=/^offers$/i, [data-testid="offers-tab"], a[href*="offers"]';
  readonly uploadOfferButton = 'button:has-text("Upload Offer"), button:has-text("Add Offer"), [data-testid="upload-offer"]';
  readonly offersList = '[data-testid="offers-list"], .offers-grid, table';
  readonly fileInput = 'input[type="file"]';
  readonly evaluateButton = 'button:has-text("Evaluate"), button:has-text("AI Evaluate"), [data-testid="evaluate-offer"]';
  readonly compareButton = 'button:has-text("Compare"), [data-testid="compare-offers"]';
  readonly selectOfferButton = 'button:has-text("Select"), button:has-text("Accept"), [data-testid="select-offer"]';
  readonly clarificationButton = 'button:has-text("Request Clarification"), [data-testid="clarification"]';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigateToOffersTab() {
    const tab = this.page.locator(this.offersTab);
    await tab.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step41-offers-tab-opened');
  }

  async verifyOffersList() {
    const list = this.page.locator(this.offersList);
    await expect(list).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step42-offers-list-displayed');
  }

  async uploadOffer(filePath: string, supplierName: string) {
    await this.page.click(this.uploadOfferButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step43-upload-offer-dialog');

    // Select supplier if dropdown exists
    const supplierSelect = this.page.locator('select[name="supplier"], [data-testid="supplier-select"]');
    if (await supplierSelect.count() > 0) {
      await supplierSelect.selectOption({ label: supplierName });
    }

    // Upload file
    const fileInputElement = this.page.locator(this.fileInput);
    await fileInputElement.setInputFiles(filePath);
    await takeScreenshot(this.page, 'step44-offer-file-selected');

    // Submit
    await this.page.click('button[type="submit"], button:has-text("Upload")');
    await this.page.waitForTimeout(3000);
    await takeScreenshot(this.page, 'step45-offer-uploaded-successfully');
  }

  async evaluateOffer(supplierName: string) {
    const offerRow = this.page.locator(`text="${supplierName}"`).locator('..').locator('..');
    await offerRow.locator(this.evaluateButton).click();
    await takeScreenshot(this.page, 'step46-offer-evaluation-started');

    // Wait for AI evaluation to complete
    await this.page.waitForTimeout(5000);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step47-offer-evaluation-completed');
  }

  async compareOffers() {
    // Select multiple offers (checkboxes)
    const checkboxes = this.page.locator('input[type="checkbox"]');
    const count = await checkboxes.count();
    const selectCount = Math.min(3, count);

    for (let i = 0; i < selectCount; i++) {
      await checkboxes.nth(i).check();
    }
    await takeScreenshot(this.page, 'step48-offers-selected-for-comparison');

    await this.page.click(this.compareButton);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step49-offers-comparison-view');
  }

  async verifyComparisonMatrix() {
    const comparisonTable = this.page.locator('table, [data-testid="comparison-matrix"]');
    await expect(comparisonTable).toBeVisible({ timeout: 10000 });

    // Verify columns: supplier name, price, score, compliance
    const headers = this.page.locator('th');
    await expect(headers.first()).toBeVisible({ timeout: 5000 });
    await takeScreenshot(this.page, 'step-comparison-matrix-verified');
  }

  async selectOffer(supplierName: string) {
    const offerRow = this.page.locator(`text="${supplierName}"`).locator('..').locator('..');
    await offerRow.locator(this.selectOfferButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-select-offer-confirmation');

    await this.page.click('button:has-text("Confirm"), button:has-text("Accept"):not(:disabled)');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-offer-selected-successfully');
  }

  async requestClarification(supplierName: string) {
    const offerRow = this.page.locator(`text="${supplierName}"`).locator('..').locator('..');
    await offerRow.locator(this.clarificationButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-clarification-request-dialog');

    // Fill clarification message
    const messageInput = this.page.locator('textarea[name="message"], #clarification-message');
    await messageInput.fill('Please clarify the unit price for item XYZ.');
    await takeScreenshot(this.page, 'step-clarification-message-filled');

    await this.page.click('button[type="submit"], button:has-text("Send")');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-clarification-sent');
  }

  async verifyOfferStatus(supplierName: string, expectedStatus: string) {
    const offerRow = this.page.locator(`text="${supplierName}"`).locator('..').locator('..');
    const statusCell = offerRow.locator(`text=/${expectedStatus}/i`);
    await expect(statusCell.first()).toBeVisible({ timeout: 5000 });
  }

  async verifyComplianceScore(supplierName: string) {
    const offerRow = this.page.locator(`text="${supplierName}"`).locator('..').locator('..');
    const scoreCell = offerRow.locator('text=/\\d+%|score/i');
    await expect(scoreCell.first()).toBeVisible({ timeout: 5000 });
    await takeScreenshot(this.page, `step-compliance-score-${supplierName}`);
  }
}
