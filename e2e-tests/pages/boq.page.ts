import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading, fillAndVerify } from '../utils/test-helpers';

/**
 * BOQ (Bill of Quantities) Page Object Model
 */
export class BOQPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly boqTab = 'text=/^boq$/i, [data-testid="boq-tab"], a[href*="boq"]';
  readonly extractButton = 'button:has-text("Extract BOQ"), button:has-text("AI Extract"), [data-testid="extract-boq"]';
  readonly boqTable = '[data-testid="boq-table"], .boq-table, table';
  readonly addItemButton = 'button:has-text("Add Item"), [data-testid="add-boq-item"]';
  readonly editItemButton = 'button:has-text("Edit"), [data-testid="edit-boq-item"]';
  readonly deleteItemButton = 'button:has-text("Delete"), [data-testid="delete-boq-item"]';
  readonly itemCodeInput = 'input[name="code"], input[placeholder*="code" i], #item-code';
  readonly itemDescriptionInput = 'input[name="description"], textarea[name="description"], #item-description';
  readonly quantityInput = 'input[name="quantity"], input[type="number"]#quantity';
  readonly unitInput = 'input[name="unit"], select[name="unit"], #unit';
  readonly saveButton = 'button[type="submit"], button:has-text("Save")';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigateToBOQTab() {
    const tab = this.page.locator(this.boqTab);
    await tab.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step18-boq-tab-opened');
  }

  async verifyBOQTable() {
    const table = this.page.locator(this.boqTable);
    await expect(table).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step19-boq-table-displayed');
  }

  async extractBOQ() {
    const extractBtn = this.page.locator(this.extractButton);
    await extractBtn.first().click();
    await takeScreenshot(this.page, 'step20-boq-extraction-started');

    // Wait for AI extraction to complete
    await this.page.waitForTimeout(5000);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step21-boq-extraction-completed');
  }

  async addBOQItem(data: {
    code: string;
    description: string;
    quantity: string;
    unit: string;
  }) {
    await this.page.click(this.addItemButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step22-add-boq-item-modal');

    await fillAndVerify(this.page, this.itemCodeInput, data.code);
    await fillAndVerify(this.page, this.itemDescriptionInput, data.description);
    await fillAndVerify(this.page, this.quantityInput, data.quantity);

    // Handle unit input (could be select or input)
    const unitField = this.page.locator(this.unitInput);
    if ((await unitField.getAttribute('type')) === 'select') {
      await unitField.selectOption(data.unit);
    } else {
      await fillAndVerify(this.page, this.unitInput, data.unit);
    }

    await takeScreenshot(this.page, 'step23-boq-item-form-filled');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step24-boq-item-added');
  }

  async editBOQItem(itemCode: string, newDescription: string) {
    const itemRow = this.page.locator(`text="${itemCode}"`).locator('..').locator('..');
    await itemRow.locator(this.editItemButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-edit-boq-item-modal');

    await fillAndVerify(this.page, this.itemDescriptionInput, newDescription);
    await takeScreenshot(this.page, 'step-boq-item-edited');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-boq-item-updated');
  }

  async deleteBOQItem(itemCode: string) {
    const itemRow = this.page.locator(`text="${itemCode}"`).locator('..').locator('..');
    await itemRow.locator(this.deleteItemButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-delete-boq-item-confirmation');

    await this.page.click('button:has-text("Confirm"), button:has-text("Delete"):not(:disabled)');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-boq-item-deleted');
  }

  async verifyBOQItemCount(expectedCount: number) {
    const rows = this.page.locator(`${this.boqTable} tbody tr`);
    const count = await rows.count();
    expect(count).toBeGreaterThanOrEqual(expectedCount);
  }

  async verifyBOQItemExists(itemCode: string) {
    const item = this.page.locator(`text="${itemCode}"`);
    await expect(item.first()).toBeVisible({ timeout: 5000 });
  }

  async filterBOQItems(searchTerm: string) {
    const searchInput = this.page.locator('input[placeholder*="Search" i], input[type="search"]');
    await searchInput.fill(searchTerm);
    await this.page.waitForTimeout(1000);
    await takeScreenshot(this.page, `step-boq-filtered-${searchTerm}`);
  }
}
