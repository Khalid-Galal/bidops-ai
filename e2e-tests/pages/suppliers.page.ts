import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading, fillAndVerify } from '../utils/test-helpers';

/**
 * Suppliers Page Object Model
 */
export class SuppliersPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly suppliersTab = 'text=/^suppliers$/i, [data-testid="suppliers-tab"], a[href*="suppliers"]';
  readonly suppliersNav = 'a:has-text("Suppliers"), nav a[href*="suppliers"]';
  readonly addSupplierButton = 'button:has-text("Add Supplier"), button:has-text("New Supplier"), [data-testid="add-supplier"]';
  readonly suppliersList = '[data-testid="suppliers-list"], .suppliers-grid, table';
  readonly supplierNameInput = 'input[name="name"], input[placeholder*="supplier name" i], #supplier-name';
  readonly supplierEmailInput = 'input[name="email"], input[type="email"], #supplier-email';
  readonly supplierPhoneInput = 'input[name="phone"], input[type="tel"], #supplier-phone';
  readonly supplierCompanyInput = 'input[name="company"], input[placeholder*="company" i], #company';
  readonly supplierAddressInput = 'textarea[name="address"], input[name="address"], #address';
  readonly saveButton = 'button[type="submit"], button:has-text("Save"), button:has-text("Add")';
  readonly editButton = 'button:has-text("Edit"), [data-testid="edit-supplier"]';
  readonly deleteButton = 'button:has-text("Delete"), [data-testid="delete-supplier"]';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigateToSuppliers() {
    await this.page.goto(`${this.baseURL}/suppliers`);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step36-suppliers-page-loaded');
  }

  async navigateToSuppliersFromProject() {
    const tab = this.page.locator(this.suppliersTab);
    if (await tab.count() > 0) {
      await tab.first().click();
      await waitForLoading(this.page);
      await takeScreenshot(this.page, 'step36-suppliers-tab-opened');
    } else {
      await this.navigateToSuppliers();
    }
  }

  async verifySuppliersList() {
    const list = this.page.locator(this.suppliersList);
    await expect(list).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step37-suppliers-list-displayed');
  }

  async addSupplier(data: {
    name: string;
    email: string;
    phone: string;
    company: string;
    address?: string;
  }) {
    await this.page.click(this.addSupplierButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step38-add-supplier-modal');

    await fillAndVerify(this.page, this.supplierNameInput, data.name);
    await fillAndVerify(this.page, this.supplierEmailInput, data.email);
    await fillAndVerify(this.page, this.supplierPhoneInput, data.phone);
    await fillAndVerify(this.page, this.supplierCompanyInput, data.company);

    if (data.address) {
      const addressField = this.page.locator(this.supplierAddressInput);
      if (await addressField.count() > 0) {
        await fillAndVerify(this.page, this.supplierAddressInput, data.address);
      }
    }

    await takeScreenshot(this.page, 'step39-supplier-form-filled');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step40-supplier-added-successfully');
  }

  async verifySupplierExists(supplierName: string) {
    const supplier = this.page.locator(`text="${supplierName}"`);
    await expect(supplier.first()).toBeVisible({ timeout: 5000 });
  }

  async editSupplier(supplierName: string, newPhone: string) {
    const supplierRow = this.page.locator(`text="${supplierName}"`).locator('..').locator('..');
    await supplierRow.locator(this.editButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-edit-supplier-modal');

    await fillAndVerify(this.page, this.supplierPhoneInput, newPhone);
    await takeScreenshot(this.page, 'step-supplier-edited');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-supplier-updated');
  }

  async deleteSupplier(supplierName: string) {
    const supplierRow = this.page.locator(`text="${supplierName}"`).locator('..').locator('..');
    await supplierRow.locator(this.deleteButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-delete-supplier-confirmation');

    await this.page.click('button:has-text("Confirm"), button:has-text("Delete"):not(:disabled)');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-supplier-deleted');
  }

  async searchSupplier(searchTerm: string) {
    const searchInput = this.page.locator('input[placeholder*="Search" i], input[type="search"]');
    await searchInput.fill(searchTerm);
    await this.page.waitForTimeout(1000);
    await takeScreenshot(this.page, `step-supplier-search-${searchTerm}`);
  }

  async importSuppliers(filePath: string) {
    const importBtn = this.page.locator('button:has-text("Import"), [data-testid="import-suppliers"]');
    if (await importBtn.count() > 0) {
      await importBtn.click();
      await this.page.waitForTimeout(500);
      await takeScreenshot(this.page, 'step-import-suppliers-dialog');

      const fileInput = this.page.locator('input[type="file"]');
      await fileInput.setInputFiles(filePath);
      await this.page.waitForTimeout(2000);
      await takeScreenshot(this.page, 'step-suppliers-imported');
    }
  }
}
