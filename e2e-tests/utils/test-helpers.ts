import { Page, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

/**
 * Test Helper Utilities for BidOps AI E2E Tests
 */

// Ensure screenshots directory exists
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'tests', 'screenshots');
if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

/**
 * Take a screenshot with a descriptive name
 */
export async function takeScreenshot(page: Page, name: string): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  const filename = `${name}-${timestamp}.png`;
  const filepath = path.join(SCREENSHOTS_DIR, filename);

  await page.screenshot({
    path: filepath,
    fullPage: true
  });

  console.log(`📸 Screenshot saved: ${filename}`);
}

/**
 * Wait for API response and take screenshot
 */
export async function waitForApiAndScreenshot(
  page: Page,
  urlPattern: string | RegExp,
  screenshotName: string
): Promise<void> {
  await page.waitForResponse(urlPattern);
  await page.waitForTimeout(1000); // Wait for UI to update
  await takeScreenshot(page, screenshotName);
}

/**
 * Fill form field and verify
 */
export async function fillAndVerify(
  page: Page,
  selector: string,
  value: string
): Promise<void> {
  await page.fill(selector, value);
  const filled = await page.inputValue(selector);
  expect(filled).toBe(value);
}

/**
 * Click and wait for navigation
 */
export async function clickAndNavigate(
  page: Page,
  selector: string,
  expectedUrl?: string | RegExp
): Promise<void> {
  await page.click(selector);

  if (expectedUrl) {
    await page.waitForURL(expectedUrl, { timeout: 10000 });
  } else {
    await page.waitForLoadState('networkidle');
  }
}

/**
 * Wait for element and verify visibility
 */
export async function waitAndVerifyVisible(
  page: Page,
  selector: string,
  timeout: number = 10000
): Promise<void> {
  const element = page.locator(selector);
  await expect(element).toBeVisible({ timeout });
}

/**
 * Verify success message appears
 */
export async function verifySuccessMessage(page: Page): Promise<void> {
  const successMsg = page.locator('text=/success|successfully|created|updated|deleted|saved/i, [role="alert"], .toast, .notification').first();
  await expect(successMsg).toBeVisible({ timeout: 5000 });
}

/**
 * Verify error message appears
 */
export async function verifyErrorMessage(page: Page): Promise<void> {
  const errorMsg = page.locator('text=/error|failed|invalid|wrong/i, [role="alert"], .error, .toast-error').first();
  await expect(errorMsg).toBeVisible({ timeout: 5000 });
}

/**
 * Generate random test data
 */
export function generateTestData(prefix: string = 'Test') {
  const timestamp = Date.now();
  return {
    projectName: `${prefix} Project ${timestamp}`,
    clientName: `${prefix} Client ${timestamp}`,
    supplierName: `${prefix} Supplier ${timestamp}`,
    email: `test-${timestamp}@example.com`,
    packageName: `${prefix} Package ${timestamp}`,
    description: `Automated E2E test - ${timestamp}`,
  };
}

/**
 * Clean up test data (placeholder - implement based on your API)
 */
export async function cleanupTestData(page: Page, type: string, name: string): Promise<void> {
  console.log(`🧹 Cleanup: ${type} - ${name}`);
  // Implement actual cleanup logic based on your application
}

/**
 * Wait for loading to complete
 */
export async function waitForLoading(page: Page): Promise<void> {
  // Wait for common loading indicators to disappear
  const loadingSelectors = [
    '[data-testid="loading"]',
    '.loading',
    '.spinner',
    'text=/loading/i'
  ];

  for (const selector of loadingSelectors) {
    const element = page.locator(selector);
    if (await element.count() > 0) {
      await element.first().waitFor({ state: 'hidden', timeout: 30000 }).catch(() => {});
    }
  }

  await page.waitForLoadState('networkidle');
}

/**
 * Verify table has data
 */
export async function verifyTableHasData(page: Page, tableSelector: string = 'table'): Promise<void> {
  const table = page.locator(tableSelector);
  await expect(table).toBeVisible({ timeout: 10000 });

  const rows = table.locator('tbody tr');
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
}

/**
 * Get test file path (for upload tests)
 */
export function getTestFilePath(filename: string): string {
  return path.join(__dirname, '..', 'test-files', filename);
}

/**
 * Create test files directory if it doesn't exist
 */
export function ensureTestFilesDir(): void {
  const testFilesDir = path.join(__dirname, '..', 'test-files');
  if (!fs.existsSync(testFilesDir)) {
    fs.mkdirSync(testFilesDir, { recursive: true });
  }
}
