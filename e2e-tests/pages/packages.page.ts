import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading, fillAndVerify } from '../utils/test-helpers';

/**
 * Packages Page Object Model
 */
export class PackagesPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly packagesTab = 'text=/^packages$/i, [data-testid="packages-tab"], a[href*="packages"]';
  readonly createPackageButton = 'button:has-text("Create Package"), button:has-text("New Package"), [data-testid="create-package"]';
  readonly smartPackagingButton = 'button:has-text("Smart Packaging"), button:has-text("AI Package"), [data-testid="smart-packaging"]';
  readonly packagesList = '[data-testid="packages-list"], .packages-grid, table';
  readonly packageNameInput = 'input[name="name"], input[placeholder*="package name" i], #package-name';
  readonly packageDescriptionInput = 'textarea[name="description"], #package-description';
  readonly selectItemsCheckbox = 'input[type="checkbox"]';
  readonly saveButton = 'button[type="submit"], button:has-text("Save"), button:has-text("Create")';
  readonly sendRFQButton = 'button:has-text("Send RFQ"), [data-testid="send-rfq"]';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigateToPackagesTab() {
    const tab = this.page.locator(this.packagesTab);
    await tab.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step25-packages-tab-opened');
  }

  async verifyPackagesList() {
    const list = this.page.locator(this.packagesList);
    await expect(list).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step26-packages-list-displayed');
  }

  async createPackageManually(data: { name: string; description: string }) {
    await this.page.click(this.createPackageButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step27-create-package-modal');

    await fillAndVerify(this.page, this.packageNameInput, data.name);
    await fillAndVerify(this.page, this.packageDescriptionInput, data.description);
    await takeScreenshot(this.page, 'step28-package-details-filled');

    // Select some BOQ items (first 3 checkboxes)
    const checkboxes = this.page.locator(this.selectItemsCheckbox);
    const count = await checkboxes.count();
    const selectCount = Math.min(3, count);

    for (let i = 0; i < selectCount; i++) {
      await checkboxes.nth(i).check();
    }
    await takeScreenshot(this.page, 'step29-boq-items-selected');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step30-package-created');
  }

  async createSmartPackaging() {
    await this.page.click(this.smartPackagingButton);
    await takeScreenshot(this.page, 'step31-smart-packaging-started');

    // Wait for AI packaging to complete
    await this.page.waitForTimeout(5000);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step32-smart-packaging-completed');
  }

  async openPackage(packageName: string) {
    const packageRow = this.page.locator(`text="${packageName}"`);
    await packageRow.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, `step-package-details-${packageName}`);
  }

  async verifyPackageDetails(packageName: string) {
    const heading = this.page.locator(`h1:has-text("${packageName}"), h2:has-text("${packageName}")`);
    await expect(heading.first()).toBeVisible({ timeout: 5000 });
    await takeScreenshot(this.page, 'step-package-details-verified');
  }

  async sendRFQ(packageName: string) {
    const packageRow = this.page.locator(`text="${packageName}"`).locator('..').locator('..');
    await packageRow.locator(this.sendRFQButton).first().click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step33-send-rfq-dialog');

    // Select suppliers (assuming checkboxes for supplier selection)
    const supplierCheckboxes = this.page.locator('input[type="checkbox"]');
    const count = await supplierCheckboxes.count();
    if (count > 0) {
      await supplierCheckboxes.first().check();
    }
    await takeScreenshot(this.page, 'step34-suppliers-selected');

    await this.page.click('button:has-text("Send"), button[type="submit"]');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step35-rfq-sent-successfully');
  }

  async verifyPackageExists(packageName: string) {
    const pkg = this.page.locator(`text="${packageName}"`);
    await expect(pkg.first()).toBeVisible({ timeout: 5000 });
  }

  async editPackage(packageName: string, newDescription: string) {
    const packageRow = this.page.locator(`text="${packageName}"`).locator('..').locator('..');
    await packageRow.locator('button:has-text("Edit")').click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-edit-package-modal');

    await fillAndVerify(this.page, this.packageDescriptionInput, newDescription);
    await takeScreenshot(this.page, 'step-package-edited');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-package-updated');
  }
}
