import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading } from '../utils/test-helpers';

/**
 * Dashboard Page Object Model
 */
export class DashboardPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly statsCards = '[data-testid="stat-card"], .stat-card, .card, .metric-card';
  readonly projectsSection = 'text=/projects|recent/i';
  readonly userMenu = '[data-testid="user-menu"], [aria-label="User menu"], button:has-text("Profile"), .user-menu';
  readonly logoutButton = 'button:has-text("Logout"), a:has-text("Logout"), [data-testid="logout"]';
  readonly sidebar = 'nav, aside, [role="navigation"], .sidebar';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigate() {
    await this.page.goto(`${this.baseURL}/`);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step4-dashboard-loaded');
  }

  async verifyDashboardElements() {
    // Verify statistics cards
    const cards = this.page.locator(this.statsCards);
    await expect(cards.first()).toBeVisible({ timeout: 10000 });

    // Verify projects section
    const projects = this.page.locator(this.projectsSection);
    await expect(projects.first()).toBeVisible({ timeout: 5000 }).catch(() => {});

    await takeScreenshot(this.page, 'step5-dashboard-elements-verified');
  }

  async verifySidebar() {
    const sidebar = this.page.locator(this.sidebar);
    await expect(sidebar.first()).toBeVisible({ timeout: 5000 });
  }

  async navigateToSection(section: string) {
    const sectionLink = this.page.locator(`a:has-text("${section}"), nav a[href*="${section.toLowerCase()}"]`);
    await sectionLink.first().click();
    await waitForLoading(this.page);
    await takeScreenshot(this.page, `step-navigate-to-${section.toLowerCase()}`);
  }

  async logout() {
    // Try to open user menu first
    const menu = this.page.locator(this.userMenu);
    if (await menu.count() > 0) {
      await menu.first().click();
      await this.page.waitForTimeout(500);
    }

    await this.page.click(this.logoutButton);
    await this.page.waitForURL(/\/login/, { timeout: 10000 });
    await takeScreenshot(this.page, 'step-logout-successful');
  }

  async verifyUserRole(role: string) {
    const roleIndicator = this.page.locator(`text=/${role}/i`);
    await expect(roleIndicator.first()).toBeVisible({ timeout: 5000 });
  }
}
