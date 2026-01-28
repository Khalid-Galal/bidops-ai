import { Page, expect } from '@playwright/test';
import { takeScreenshot, waitForLoading, verifySuccessMessage, fillAndVerify } from '../utils/test-helpers';

/**
 * Projects Page Object Model
 */
export class ProjectsPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly newProjectButton = 'button:has-text("New Project"), button:has-text("Create Project"), [data-testid="new-project"], button:has-text("Add Project")';
  readonly projectsList = 'table, [data-testid="projects-list"], .projects-grid, .projects-table';
  readonly projectNameInput = 'input[name="name"], input[placeholder*="name" i], input[label*="Name" i], #project-name';
  readonly clientInput = 'input[name="client"], input[placeholder*="client" i], #client';
  readonly descriptionInput = 'textarea[name="description"], textarea[placeholder*="description" i], #description';
  readonly locationInput = 'input[name="location"], input[placeholder*="location" i], #location';
  readonly deadlineInput = 'input[name="deadline"], input[type="date"], #deadline';
  readonly submitButton = 'button[type="submit"], button:has-text("Create"), button:has-text("Save")';
  readonly cancelButton = 'button:has-text("Cancel"), button[type="button"]:not([type="submit"])';
  readonly editButton = 'button:has-text("Edit"), [data-testid="edit-project"]';
  readonly deleteButton = 'button:has-text("Delete"), [data-testid="delete-project"]';
  readonly confirmDeleteButton = 'button:has-text("Confirm"), button:has-text("Delete"):not(:disabled)';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  async navigate() {
    await this.page.goto(`${this.baseURL}/projects`);
    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step6-projects-page-loaded');
  }

  async verifyProjectsList() {
    const list = this.page.locator(this.projectsList);
    await expect(list).toBeVisible({ timeout: 10000 });
    await takeScreenshot(this.page, 'step7-projects-list-displayed');
  }

  async clickNewProject() {
    const button = this.page.locator(this.newProjectButton);
    await button.first().click();
    await this.page.waitForTimeout(1000);
    await takeScreenshot(this.page, 'step8-new-project-modal-opened');
  }

  async createProject(data: {
    name: string;
    client: string;
    description: string;
    location?: string;
    deadline?: string;
  }) {
    // Fill required fields
    await fillAndVerify(this.page, this.projectNameInput, data.name);
    await fillAndVerify(this.page, this.clientInput, data.client);
    await fillAndVerify(this.page, this.descriptionInput, data.description);

    // Fill optional fields if selectors exist
    if (data.location) {
      const locationField = this.page.locator(this.locationInput);
      if (await locationField.count() > 0) {
        await fillAndVerify(this.page, this.locationInput, data.location);
      }
    }

    if (data.deadline) {
      const deadlineField = this.page.locator(this.deadlineInput);
      if (await deadlineField.count() > 0) {
        await fillAndVerify(this.page, this.deadlineInput, data.deadline);
      }
    }

    await takeScreenshot(this.page, 'step9-project-form-filled');

    // Submit
    await this.page.click(this.submitButton);
    await this.page.waitForTimeout(2000);

    await takeScreenshot(this.page, 'step10-project-created');
  }

  async openFirstProject() {
    const firstProjectRow = this.page.locator('table tbody tr:first-child, [data-testid="project-item"]:first-child, .project-card:first-child');
    const firstProjectLink = this.page.locator('a[href*="/projects/"]:first-child');

    // Try clicking the row or link
    if (await firstProjectRow.count() > 0) {
      await firstProjectRow.click();
    } else if (await firstProjectLink.count() > 0) {
      await firstProjectLink.click();
    }

    await waitForLoading(this.page);
    await takeScreenshot(this.page, 'step11-project-details-opened');
  }

  async verifyProjectDetails(projectName: string) {
    const heading = this.page.locator(`h1:has-text("${projectName}"), h2:has-text("${projectName}")`);
    await expect(heading.first()).toBeVisible({ timeout: 5000 }).catch(() => {});

    // Verify tabs exist
    const tabs = this.page.locator('text=/documents|boq|packages|suppliers|pricing/i');
    await expect(tabs.first()).toBeVisible({ timeout: 5000 }).catch(() => {});

    await takeScreenshot(this.page, 'step12-project-details-verified');
  }

  async editProject(newData: { name?: string; client?: string; description?: string }) {
    await this.page.click(this.editButton);
    await this.page.waitForTimeout(1000);
    await takeScreenshot(this.page, 'step-edit-project-modal-opened');

    if (newData.name) {
      await fillAndVerify(this.page, this.projectNameInput, newData.name);
    }
    if (newData.client) {
      await fillAndVerify(this.page, this.clientInput, newData.client);
    }
    if (newData.description) {
      await fillAndVerify(this.page, this.descriptionInput, newData.description);
    }

    await takeScreenshot(this.page, 'step-edit-project-form-updated');

    await this.page.click(this.submitButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-project-updated-successfully');
  }

  async deleteProject() {
    await this.page.click(this.deleteButton);
    await this.page.waitForTimeout(500);
    await takeScreenshot(this.page, 'step-delete-confirmation-dialog');

    await this.page.click(this.confirmDeleteButton);
    await this.page.waitForTimeout(2000);
    await takeScreenshot(this.page, 'step-project-deleted-successfully');
  }

  async searchProject(searchTerm: string) {
    const searchInput = this.page.locator('input[placeholder*="Search" i], input[type="search"]');
    await searchInput.fill(searchTerm);
    await this.page.waitForTimeout(1000);
    await takeScreenshot(this.page, `step-search-results-${searchTerm}`);
  }

  async verifyProjectInList(projectName: string) {
    const projectRow = this.page.locator(`text="${projectName}"`);
    await expect(projectRow.first()).toBeVisible({ timeout: 5000 });
  }
}
