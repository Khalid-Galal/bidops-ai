import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading, waitAndVerifyVisible } from '../utils/test-helpers';

/**
 * Documents Page Object Model
 */
export class DocumentsPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly documentsTab = 'text=/^documents$/i, [data-testid="documents-tab"], a[href*="documents"]';
  readonly uploadButton = 'button:has-text("Upload"), [data-testid="upload-document"]';
  readonly fileInput = 'input[type="file"]';
  readonly documentsList = '[data-testid="documents-list"], .documents-grid, .documents-table, table';
  readonly documentItem = '[data-testid="document-item"], .document-card, tbody tr';
  readonly deleteDocButton = 'button:has-text("Delete"), [data-testid="delete-document"]';
  readonly viewDocButton = 'button:has-text("View"), [data-testid="view-document"]';
  readonly reprocessButton = 'button:has-text("Reprocess"), [data-testid="reprocess-document"]';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigateToDocumentsTab() {
    const tab = this.page.locator(this.documentsTab);
    await tab.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step13-documents-tab-opened');
  }

  async verifyDocumentsList() {
    const list = this.page.locator(this.documentsList);
    await expect(list).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step14-documents-list-displayed');
  }

  async uploadDocument(filePath: string) {
    // Click upload button
    const uploadBtn = this.page.locator(this.uploadButton);
    await uploadBtn.first().click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step15-upload-dialog-opened');

    // Set file
    const fileInputElement = this.page.locator(this.fileInput);
    await fileInputElement.setInputFiles(filePath);
    await takeScreenshot(this.page, 'step16-file-selected');

    // Wait for upload to complete
    await this.page.waitForTimeout(3000);
    await takeScreenshot(this.page, 'step17-document-uploaded-successfully');
  }

  async verifyDocumentUploaded(filename: string) {
    const doc = this.page.locator(`text="${filename}"`);
    await expect(doc.first()).toBeVisible({ timeout: 10000 });
  }

  async viewDocument(documentName: string) {
    const docRow = this.page.locator(`text="${documentName}"`).locator('..').locator('..');
    await docRow.locator(this.viewDocButton).click();
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-document-viewer-opened');
  }

  async deleteDocument(documentName: string) {
    const docRow = this.page.locator(`text="${documentName}"`).locator('..').locator('..');
    await docRow.locator(this.deleteDocButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-delete-document-confirmation');

    // Confirm deletion
    await this.page.click('button:has-text("Confirm"), button:has-text("Delete"):not(:disabled)');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-document-deleted-successfully');
  }

  async reprocessDocument(documentName: string) {
    const docRow = this.page.locator(`text="${documentName}"`).locator('..').locator('..');
    await docRow.locator(this.reprocessButton).click();
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-document-reprocessed');
  }

  async verifyDocumentCount(expectedCount: number) {
    const items = this.page.locator(this.documentItem);
    const count = await items.count();
    expect(count).toBe(expectedCount);
  }

  async verifyUploadProgress() {
    const progressBar = this.page.locator('[role="progressbar"], .progress-bar, .upload-progress');
    if (await progressBar.count() > 0) {
      await expect(progressBar.first()).toBeVisible({ timeout: 5000 });
      await takeScreenshot(this.page, 'step-upload-in-progress');
    }
  }
}
