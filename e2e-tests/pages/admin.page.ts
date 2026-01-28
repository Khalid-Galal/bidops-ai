import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading, fillAndVerify } from '../utils/test-helpers';

/**
 * Admin Page Object Model for User Management and Admin Features
 */
export class AdminPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly adminNav = 'a:has-text("Admin"), nav a[href*="admin"], [data-testid="admin-nav"]';
  readonly usersTab = 'text=/^users$/i, [data-testid="users-tab"], a[href*="users"]';
  readonly auditLogsTab = 'text=/^audit/i, [data-testid="audit-tab"], a[href*="audit"]';
  readonly settingsTab = 'text=/^settings$/i, [data-testid="settings-tab"], a[href*="settings"]';
  readonly addUserButton = 'button:has-text("Add User"), button:has-text("New User"), [data-testid="add-user"]';
  readonly usersList = '[data-testid="users-list"], .users-grid, table';
  readonly userEmailInput = 'input[name="email"], input[type="email"], #user-email';
  readonly userNameInput = 'input[name="name"], input[placeholder*="name" i], #user-name';
  readonly userPhoneInput = 'input[name="phone"], input[type="tel"], #user-phone';
  readonly userRoleSelect = 'select[name="role"], [data-testid="role-select"], #role';
  readonly saveButton = 'button[type="submit"], button:has-text("Save"), button:has-text("Add")';
  readonly editButton = 'button:has-text("Edit"), [data-testid="edit-user"]';
  readonly deleteButton = 'button:has-text("Delete"), [data-testid="delete-user"]';
  readonly disableButton = 'button:has-text("Disable"), [data-testid="disable-user"]';
  readonly enableButton = 'button:has-text("Enable"), [data-testid="enable-user"]';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigateToAdmin() {
    const adminLink = this.page.locator(this.adminNav);
    await adminLink.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step50-admin-page-loaded');
  }

  async navigateToUsers() {
    await this.navigateToAdmin();
    const usersTab = this.page.locator(this.usersTab);
    if (await usersTab.count() > 0) {
      await usersTab.first().click();
      await waitForLoading(this.page);
    }
    await takeScreenshot(this.page, 'step51-users-management-opened');
  }

  async verifyUsersList() {
    const list = this.page.locator(this.usersList);
    await expect(list).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step52-users-list-displayed');
  }

  async addUser(data: {
    email: string;
    name: string;
    phone: string;
    role: 'ADMIN' | 'TENDER_MANAGER' | 'ESTIMATOR' | 'VIEWER';
  }) {
    await this.page.click(this.addUserButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step53-add-user-modal');

    await fillAndVerify(this.page, this.userEmailInput, data.email);
    await fillAndVerify(this.page, this.userNameInput, data.name);
    await fillAndVerify(this.page, this.userPhoneInput, data.phone);

    // Select role
    const roleSelect = this.page.locator(this.userRoleSelect);
    await roleSelect.selectOption(data.role);
    await takeScreenshot(this.page, 'step54-user-form-filled');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step55-user-added-successfully');
  }

  async verifyUserExists(userEmail: string) {
    const user = this.page.locator(`text="${userEmail}"`);
    await expect(user.first()).toBeVisible({ timeout: 5000 });
  }

  async verifyUserRole(userEmail: string, expectedRole: string) {
    const userRow = this.page.locator(`text="${userEmail}"`).locator('..').locator('..');
    const roleCell = userRow.locator(`text=/${expectedRole}/i`);
    await expect(roleCell.first()).toBeVisible({ timeout: 5000 });
    await takeScreenshot(this.page, `step-user-role-verified-${expectedRole}`);
  }

  async editUserRole(userEmail: string, newRole: string) {
    const userRow = this.page.locator(`text="${userEmail}"`).locator('..').locator('..');
    await userRow.locator(this.editButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step56-edit-user-modal');

    const roleSelect = this.page.locator(this.userRoleSelect);
    await roleSelect.selectOption(newRole);
    await takeScreenshot(this.page, 'step57-user-role-changed');

    await this.page.click(this.saveButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step58-user-updated-successfully');
  }

  async disableUser(userEmail: string) {
    const userRow = this.page.locator(`text="${userEmail}"`).locator('..').locator('..');
    await userRow.locator(this.disableButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step59-disable-user-confirmation');

    await this.page.click('button:has-text("Confirm"), button:has-text("Disable"):not(:disabled)');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step60-user-disabled');
  }

  async enableUser(userEmail: string) {
    const userRow = this.page.locator(`text="${userEmail}"`).locator('..').locator('..');
    await userRow.locator(this.enableButton).click();
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-user-enabled');
  }

  async navigateToAuditLogs() {
    await this.navigateToAdmin();
    const auditTab = this.page.locator(this.auditLogsTab);
    await auditTab.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step61-audit-logs-opened');
  }

  async verifyAuditLogs() {
    const auditTable = this.page.locator('table, [data-testid="audit-logs"]');
    await expect(auditTable).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step62-audit-logs-displayed');
  }

  async filterAuditLogs(action: string) {
    const filterSelect = this.page.locator('select[name="action"], [data-testid="action-filter"]');
    if (await filterSelect.count() > 0) {
      await filterSelect.selectOption(action);
      await this.page.waitForTimeout(1000);
      await takeScreenshot(this.page, `step-audit-logs-filtered-${action}`);
    }
  }

  async navigateToSettings() {
    await this.navigateToAdmin();
    const settingsTab = this.page.locator(this.settingsTab);
    await settingsTab.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step63-settings-opened');
  }

  async verifyAdminOnlyAccess() {
    // Verify admin-specific elements are visible
    const adminElements = this.page.locator(this.usersTab);
    await expect(adminElements.first()).toBeVisible({ timeout: 5000 });
    await takeScreenshot(this.page, 'step-admin-access-verified');
  }

  async deleteUser(userEmail: string) {
    const userRow = this.page.locator(`text="${userEmail}"`).locator('..').locator('..');
    await userRow.locator(this.deleteButton).click();
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-delete-user-confirmation');

    await this.page.click('button:has-text("Confirm"), button:has-text("Delete"):not(:disabled)');
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-user-deleted');
  }
}
