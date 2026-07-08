# Testing Patterns

> **SUPERSEDED (2026-07-08):** describes the February v1; the shipped system is the root app/ FastAPI+Jinja build - see docs/reviews/2026-07-07-full-system-review.md

**Analysis Date:** 2026-02-03

## Test Framework

**Runner:**
- Playwright v1.48.0
- Config: `e2e-tests/playwright.config.ts`
- No unit test framework (Vitest, Jest) configured for frontend

**Assertion Library:**
- Playwright's built-in `expect()` API
- Assertions from `@playwright/test`

**Run Commands:**
```bash
npm run test              # Run all tests
npm run test:headed      # Run tests with visible browser
npm run test:ui          # Run tests in Playwright UI mode
npm run test:debug       # Run tests in debug mode
npm run test:report      # View HTML test report
npm run test:chrome      # Run only on Chromium
npm run test:firefox     # Run only on Firefox
npm run test:webkit      # Run only on Safari
npm run test:admin       # Run admin-e2e.spec.ts
npm run test:admin:headed    # Run admin tests with visible browser
npm run test:admin:debug     # Run admin tests in debug mode
npm run test:admin:chrome    # Run admin tests on Chromium
npm run pretest          # Auto-runs before tests; generates test files
```

## Test File Organization

**Location:**
- E2E tests in `bidops-ai/e2e-tests/` (separate from frontend source)
- Main test file: `admin-e2e.spec.ts`
- Earlier test file: `playwright-tests.spec.ts` (legacy)

**Naming:**
- Test files end with `.spec.ts` suffix
- Test data generator: `test-files/generate-test-files.js`
- Page objects end with `.page.ts` suffix

**Directory Structure:**
```
e2e-tests/
├── pages/              # Page Object Models
│   ├── login.page.ts
│   ├── dashboard.page.ts
│   ├── projects.page.ts
│   ├── documents.page.ts
│   ├── boq.page.ts
│   ├── packages.page.ts
│   ├── suppliers.page.ts
│   ├── offers.page.ts
│   ├── pricing.page.ts
│   └── admin.page.ts
├── utils/              # Test utilities
│   └── test-helpers.ts
├── test-files/         # Test data generation
│   └── generate-test-files.js
├── admin-e2e.spec.ts   # Main test suite
├── playwright-tests.spec.ts  # Legacy tests
└── playwright.config.ts    # Configuration
```

## Test Structure

**Suite Organization:**
```typescript
test.describe('Admin E2E Workflow - Complete Test Suite', () => {
  test.beforeEach(() => {
    // Setup before each test
    testData = generateTestData('E2E');
  });

  test('TC-ADMIN-001: Admin Login and Dashboard Access', async ({ page }) => {
    // Test steps
  });

  test('TC-ADMIN-002: Another test', async ({ page }) => {
    // Test steps
  });
});
```

**Patterns:**
- `test.describe()` groups related tests with descriptive names
- `test.beforeEach()` prepares test data before each test
- Test names follow pattern: `TC-[SECTION]-[NUMBER]: [Description]`
- Tests are async functions receiving `{ page }` fixture from Playwright
- Test comments document the test purpose and flow

**Example Test Structure:**
```typescript
test('TC-ADMIN-001: Admin Login and Dashboard Access', async ({ page }) => {
  const loginPage = new LoginPage(page, BASE_URL);
  const dashboardPage = new DashboardPage(page, BASE_URL);

  // Step 1: Navigate to login page
  await loginPage.navigate();

  // Step 2: Login with admin credentials
  await loginPage.login(ADMIN_USER.email, ADMIN_USER.password);

  // Step 3: Verify successful authentication
  await loginPage.verifyAuthToken();

  // Step 4: Verify dashboard loads
  await dashboardPage.verifyDashboardElements();

  // Step 5: Verify admin user role
  await dashboardPage.verifyUserRole('ADMIN');
});
```

## Page Object Model

**Framework:** Custom Page Object Model implementation (not a framework, manual pattern)

**Structure:**
```typescript
export class LoginPage {
  readonly page: Page;
  readonly baseURL: string;

  // Selectors
  readonly emailInput = 'input[name="email"], input[type="email"]';
  readonly passwordInput = 'input[name="password"], input[type="password"]';
  readonly submitButton = 'button[type="submit"], button:has-text("Login")';

  constructor(page: Page, baseURL: string = 'http://localhost:3000') {
    this.page = page;
    this.baseURL = baseURL;
  }

  // Methods for test interactions
  async navigate() { }
  async login(email: string, password: string) { }
  async verifyAuthToken() { }
}
```

**Patterns:**
- Selectors stored as class properties with multiple fallbacks for robustness
- Methods encapsulate page interactions and assertions
- Navigation methods verify page load with `waitForLoadState()`
- Each action followed by screenshot for debugging
- Verification methods use Playwright's `expect()` for assertions

**File Locations:**
- `e2e-tests/pages/login.page.ts` - Login flow
- `e2e-tests/pages/dashboard.page.ts` - Dashboard verification
- `e2e-tests/pages/projects.page.ts` - Project management
- `e2e-tests/pages/documents.page.ts` - Document upload
- `e2e-tests/pages/boq.page.ts` - BOQ extraction
- `e2e-tests/pages/packages.page.ts` - Package creation
- `e2e-tests/pages/suppliers.page.ts` - Supplier management
- `e2e-tests/pages/offers.page.ts` - Offer evaluation
- `e2e-tests/pages/pricing.page.ts` - Pricing workflows
- `e2e-tests/pages/admin.page.ts` - Admin-specific features

## Test Helpers

**Location:** `e2e-tests/utils/test-helpers.ts`

**Functions:**

```typescript
// Screenshot management
export async function takeScreenshot(page: Page, name: string): Promise<void>

// API waiting
export async function waitForApiAndScreenshot(
  page: Page,
  urlPattern: string | RegExp,
  screenshotName: string
): Promise<void>

// Form operations
export async function fillAndVerify(
  page: Page,
  selector: string,
  value: string
): Promise<void>

// Navigation
export async function clickAndNavigate(
  page: Page,
  selector: string,
  expectedUrl?: string | RegExp
): Promise<void>

// Element visibility
export async function waitAndVerifyVisible(
  page: Page,
  selector: string,
  timeout?: number
): Promise<void>
```

**Patterns:**
- Screenshots include timestamp: `${name}-${timestamp}.png`
- Screenshots saved to `tests/screenshots/` directory
- Each action takes screenshot for debugging failed tests
- Helper functions combine Playwright actions with verification steps

## Test Data

**Generation:**
- Pre-test hook runs `generate-test-files.js` before each test run
- Script: `npm run pretest` or `npm run generate:files`
- Test data generated fresh for each test execution
- Cleanup: `npm run clean:screenshots` removes old screenshots

**Test Data Factory:**
```typescript
export function generateTestData(prefix: string) {
  // Returns: {
  //   projectName: string
  //   projectCode: string
  //   supplierEmail: string
  //   ... other test data
  // }
}
```

**Usage:**
```typescript
let testData: ReturnType<typeof generateTestData>;

test.beforeEach(() => {
  testData = generateTestData('E2E');
});
```

## Mocking

**Framework:** No explicit mocking library used (Playwright doesn't require it)

**Patterns:**
- Playwright automatically intercepts network requests via `page.waitForResponse()`
- API calls exercised live against backend (no HTTP mocking)
- Auth tokens stored in localStorage/sessionStorage
- Page state verified through UI assertions rather than state mocking

**What to Mock:**
- External third-party APIs (not mocked in current suite)
- File uploads (tested via actual form submission)
- Authenticated requests (real token flow tested)

**What NOT to Mock:**
- Backend APIs (tests run against live API)
- Browser navigation (tested as users experience it)
- Database state (rely on test data generation)

## Fixtures and Factories

**Test Data:**
```typescript
const ADMIN_USER = {
  email: 'admin@bidops.test',
  password: 'Admin@123'
};

const BASE_URL = 'http://localhost:3000';

// Reused across multiple tests
const testData = generateTestData('E2E');
```

**Location:**
- Test data hardcoded in test file headers
- Credentials stored as constants
- Dynamic data generated by `generateTestData()` utility

**Factory Pattern:**
```typescript
test.beforeEach(() => {
  testData = generateTestData('E2E');  // Fresh data for each test
});
```

## Configuration

**File:** `e2e-tests/playwright.config.ts`

**Key Settings:**
```typescript
{
  testDir: './',
  fullyParallel: false,           // Run tests sequentially
  forbidOnly: !!process.env.CI,   // CI fails if test.only found
  retries: process.env.CI ? 2 : 0, // Retry on CI
  workers: process.env.CI ? 1 : undefined, // Single worker on CI
  timeout: 60000,                 // 60s per test

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',      // Collect traces on retry
    screenshot: 'only-on-failure', // Screenshots on failure
    video: 'retain-on-failure',   // Videos on failure
    actionTimeout: 15000,          // 15s per action
    navigationTimeout: 30000,      // 30s per navigation
    viewport: { width: 1920, height: 1080 },
  },

  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
    ['json', { outputFile: 'test-results.json' }]
  ],

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
    { name: 'Mobile Safari', use: { ...devices['iPhone 12'] } },
  ],
}
```

## Coverage

**Requirements:** No coverage requirements enforced

**View Results:**
```bash
npm run test:report  # Opens HTML report with test results
```

**Reports Generated:**
- HTML report: `playwright-report/index.html`
- JSON results: `test-results.json`
- Screenshots on failure: `tests/screenshots/`
- Videos on failure: stored with test results

## Test Types

**E2E Tests (Primary):**
- Full workflow testing from login to feature completion
- Tests exercise entire application stack
- Validates user journeys end-to-end
- Files: `admin-e2e.spec.ts`, `playwright-tests.spec.ts`
- Scope: Authentication, project management, document upload, pricing, admin features

**Unit Tests:**
- Not implemented in frontend
- No test runner configured (no Jest/Vitest)
- Focus is on E2E coverage

**Integration Tests:**
- Implicitly tested in E2E suite
- API integration tested live
- Database persistence verified through UI

## Common Patterns

**Async Testing:**
```typescript
test('TC-ADMIN-001: Test Name', async ({ page }) => {
  // All operations are async
  await loginPage.navigate();
  await loginPage.login(email, password);
  await dashboardPage.verifyDashboardElements();
});
```

**Waiting Patterns:**
```typescript
// Wait for navigation
await page.waitForURL(`${baseURL}/`, { timeout: 10000 });

// Wait for network
await page.waitForLoadState('networkidle');

// Wait for response
await page.waitForResponse(urlPattern);

// Wait for element
await expect(error).toBeVisible({ timeout: 5000 });

// Explicit delay
await page.waitForTimeout(2000);
```

**Error Testing:**
```typescript
test('TC-ADMIN-002: Invalid Login Attempt', async ({ page }) => {
  const loginPage = new LoginPage(page, BASE_URL);

  await loginPage.navigate();
  await loginPage.loginWithInvalidCredentials('invalid@test.com', 'wrongpassword');
  await loginPage.verifyErrorMessage();    // Error displayed
  await loginPage.verifyOnLoginPage();     // Still on login page
  await loginPage.verifyNoAuthToken();     // No auth token exists
});
```

**Form Interaction:**
```typescript
async login(email: string, password: string) {
  await this.page.fill(this.emailInput, email);
  await this.page.fill(this.passwordInput, password);
  await takeScreenshot(this.page, 'step2-login-credentials-filled');

  await this.page.click(this.submitButton);
  await this.page.waitForURL(`${this.baseURL}/`, { timeout: 10000 });
  await takeScreenshot(this.page, 'step3-login-successful');
}
```

**Verification Patterns:**
```typescript
// Check localStorage token
const token = await this.page.evaluate(() =>
  window.localStorage.getItem('auth-token')
);
expect(token).not.toBeNull();

// Check URL
expect(this.page.url()).toContain('/login');

// Check element visibility
const error = this.page.locator(this.errorMessage).first();
await expect(error).toBeVisible({ timeout: 5000 });
```

## Test Categories

**Authentication & Authorization:**
- Admin login and dashboard access (TC-ADMIN-001)
- Invalid login attempts (TC-ADMIN-002)
- Protected route access without auth (TC-ADMIN-003)
- Role-based access control

**Project Management:**
- Create new project
- View project list
- Update project details
- Delete project
- Ingest project documents

**Document Processing:**
- Upload documents
- View document list
- Document category assignment
- Processing status tracking

**BOQ Extraction:**
- Extract BOQ from documents
- View extracted data
- Edit BOQ entries

**Supplier Management:**
- Create suppliers
- View supplier list
- Send RFQs

**Offer Evaluation:**
- Receive supplier offers
- Evaluate offers
- Compare pricing

**Pricing & Export:**
- Generate pricing reports
- Export to Excel/PDF

**Admin Features:**
- User management
- Audit logs
- Permission management

---

*Testing analysis: 2026-02-03*
