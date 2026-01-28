import { Page, expect } from '@playwright/test';
import { takeScreenshot } from '../utils/test-helpers';

/**
 * Login Page Object Model
 */
export class LoginPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly emailInput = 'input[name="email"], input[type="email"]';
  readonly passwordInput = 'input[name="password"], input[type="password"]';
  readonly submitButton = 'button[type="submit"], button:has-text("Login"), button:has-text("Sign In")';
  readonly errorMessage = 'text=/error|invalid|wrong|failed/i';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigate() {
    await this.page.goto(`${this.baseURL}/login`);
    await this.page.waitForLoadState('networkidle');
    await takeScreenshot(this.page, 'step1-login-page');
  }

  async login(email: string, password: string) {
    await this.page.fill(this.emailInput, email);
    await this.page.fill(this.passwordInput, password);
    await takeScreenshot(this.page, 'step2-login-credentials-filled');

    await this.page.click(this.submitButton);
    await this.page.waitForURL(`${this.baseURL}/`, { timeout: 10000 });
    await takeScreenshot(this.page, 'step3-login-successful');
  }

  async loginWithInvalidCredentials(email: string, password: string) {
    await this.page.fill(this.emailInput, email);
    await this.page.fill(this.passwordInput, password);
    await takeScreenshot(this.page, 'step-invalid-credentials-filled');

    await this.page.click(this.submitButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-login-error-displayed');
  }

  async verifyErrorMessage() {
    const error = this.page.locator(this.errorMessage).first();
    await expect(error).toBeVisible({ timeout: 5000 });
  }

  async verifyOnLoginPage() {
    expect(this.page.url()).toContain('/login');
  }

  async clearStorage() {
    await this.page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  }

  async verifyAuthToken() {
    const token = await this.page.evaluate(() =>
      window.localStorage.getItem('auth-token') || window.localStorage.getItem('token')
    );
    expect(token).not.toBeNull();
  }

  async verifyNoAuthToken() {
    const token = await this.page.evaluate(() =>
      window.localStorage.getItem('auth-token') || window.localStorage.getItem('token')
    );
    expect(token).toBeNull();
  }
}
