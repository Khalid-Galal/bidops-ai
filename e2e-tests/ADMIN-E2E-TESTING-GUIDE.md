# BidOps AI - Admin E2E Testing Guide

## 📋 Table of Contents
- [Overview](#overview)
- [Test Coverage](#test-coverage)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Screenshots](#screenshots)
- [Troubleshooting](#troubleshooting)
- [Test Results](#test-results)

---

## 🎯 Overview

This comprehensive End-to-End (E2E) test suite validates the complete BidOps AI application workflow from an **ADMIN user perspective**. The tests simulate real user interactions with the browser, validating every important step with screenshots.

### Key Features
✅ **Complete Admin Workflow Testing** - From login to project completion
✅ **Screenshot at Every Step** - Visual documentation of test execution
✅ **Page Object Model** - Maintainable and reusable test code
✅ **Comprehensive Coverage** - Authentication, CRUD operations, AI features, permissions
✅ **Multiple Browser Support** - Chrome, Firefox, Safari, Mobile devices

---

## 🧪 Test Coverage

### 1. Authentication & Authorization
- ✅ Admin login with valid credentials
- ✅ Invalid login attempts and error handling
- ✅ Protected route access without authentication
- ✅ Session management and logout

### 2. Project Management (CRUD)
- ✅ Create new projects with all fields
- ✅ View projects list and details
- ✅ Edit project information
- ✅ Search and filter projects
- ✅ Delete projects (with confirmation)

### 3. Document Processing
- ✅ Navigate to documents section
- ✅ Upload documents (PDF, Word, Excel)
- ✅ View uploaded documents
- ✅ Delete documents
- ✅ Document reprocessing

### 4. BOQ (Bill of Quantities) Management
- ✅ Navigate to BOQ section
- ✅ AI-powered BOQ extraction
- ✅ Add BOQ items manually
- ✅ Edit BOQ items
- ✅ Delete BOQ items
- ✅ Filter and search BOQ items

### 5. Package Management
- ✅ Create procurement packages manually
- ✅ AI-powered smart packaging
- ✅ View package details
- ✅ Edit packages
- ✅ Send RFQ to suppliers

### 6. Supplier Management
- ✅ Add new suppliers
- ✅ Edit supplier information
- ✅ Search and filter suppliers
- ✅ Import suppliers from Excel
- ✅ Delete suppliers

### 7. Offer Evaluation
- ✅ Upload supplier offers
- ✅ AI-powered offer evaluation
- ✅ Compare multiple offers
- ✅ Compliance checking
- ✅ Select winning offer
- ✅ Request clarifications

### 8. Pricing & Export
- ✅ View pricing summary
- ✅ Populate pricing automatically
- ✅ Adjust individual prices
- ✅ Export to Excel
- ✅ Export to PDF
- ✅ Approve pricing

### 9. Admin-Specific Features
- ✅ User management (add, edit, delete users)
- ✅ Role management (ADMIN, TENDER_MANAGER, ESTIMATOR, VIEWER)
- ✅ User activation/deactivation
- ✅ Audit logs access
- ✅ System settings management

### 10. Permissions & RBAC
- ✅ Verify admin has access to all features
- ✅ Role-based access control validation
- ✅ Permission-based feature visibility

### 11. Form Validations
- ✅ Required field validations
- ✅ Email format validation
- ✅ Phone number format validation
- ✅ Date format validation
- ✅ Numeric field validation

### 12. Navigation & UI
- ✅ Sidebar navigation
- ✅ Tab navigation within projects
- ✅ Breadcrumb navigation
- ✅ Responsive design (desktop, tablet, mobile)

---

## 📦 Prerequisites

Before running the tests, ensure you have:

### 1. Backend Running
```bash
cd ../backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Running
```bash
cd ../frontend
npm install
npm run dev  # Should run on http://localhost:3000
```

### 3. Database Setup
- PostgreSQL 16 running
- Redis 7 running
- Qdrant vector database running (optional for AI features)

### 4. Admin User Created
Run the admin creation script:
```bash
cd ../backend
python create_admin.py
```

**Default Admin Credentials:**
- Email: `admin@bidops.test`
- Password: `Admin@123`

---

## 🚀 Installation

### 1. Install Dependencies
```bash
cd e2e-tests
npm install
```

### 2. Install Playwright Browsers
```bash
npx playwright install
```

### 3. Generate Test Files
```bash
npm run generate:files
```

This creates sample test files in `test-files/` directory.

---

## ▶️ Running Tests

### Run All Tests
```bash
npm test
```

### Run Admin E2E Tests Only
```bash
npm run test:admin
```

### Run Tests in Headed Mode (See Browser)
```bash
npm run test:admin:headed
```

### Run Tests in Debug Mode
```bash
npm run test:admin:debug
```

### Run Tests in UI Mode (Interactive)
```bash
npm run test:ui
```

### Run Tests on Specific Browser
```bash
# Chrome only
npm run test:admin:chrome

# Firefox only
npm run test:firefox

# Safari only
npm run test:webkit
```

### Run Single Test
```bash
# Run specific test by name
npx playwright test -g "TC-ADMIN-001"

# Run specific test file
npx playwright test admin-e2e.spec.ts
```

---

## 📁 Test Structure

```
e2e-tests/
├── pages/                          # Page Object Models
│   ├── login.page.ts              # Login page actions
│   ├── dashboard.page.ts          # Dashboard page actions
│   ├── projects.page.ts           # Projects page actions
│   ├── documents.page.ts          # Documents page actions
│   ├── boq.page.ts                # BOQ page actions
│   ├── packages.page.ts           # Packages page actions
│   ├── suppliers.page.ts          # Suppliers page actions
│   ├── offers.page.ts             # Offers page actions
│   ├── pricing.page.ts            # Pricing page actions
│   └── admin.page.ts              # Admin features page actions
│
├── utils/                         # Helper utilities
│   └── test-helpers.ts           # Common test functions
│
├── test-files/                    # Sample test files
│   ├── sample-tender.txt         # Sample tender document
│   ├── sample-boq.csv            # Sample BOQ spreadsheet
│   ├── sample-offer.txt          # Sample supplier offer
│   ├── sample-specification.txt  # Sample specification
│   └── generate-test-files.js   # Test file generator
│
├── tests/screenshots/             # Test screenshots (auto-generated)
│   ├── step1-login-page.png
│   ├── step2-login-credentials-filled.png
│   ├── step3-login-successful.png
│   └── ... (many more screenshots)
│
├── admin-e2e.spec.ts             # Main admin E2E test suite
├── playwright-tests.spec.ts      # Original test suite
├── playwright.config.ts          # Playwright configuration
├── package.json                  # Dependencies and scripts
└── README.md                     # This file
```

---

## 📸 Screenshots

### Automatic Screenshot Capture

Every test automatically captures screenshots at important steps:

1. **Step 1**: Login page loaded
2. **Step 2**: Credentials filled
3. **Step 3**: Login successful
4. **Step 4**: Dashboard loaded
5. **Step 5**: Dashboard elements verified
6. **Step 6**: Projects page loaded
7. **Step 7**: Projects list displayed
8. **Step 8**: New project modal opened
9. **Step 9**: Project form filled
10. **Step 10**: Project created
... and so on for every important action

### Screenshot Location

All screenshots are saved in:
```
e2e-tests/tests/screenshots/
```

Screenshot naming pattern:
```
step{number}-{description}-{timestamp}.png
```

Example:
```
step1-login-page-2026-01-28T10-30-45.png
```

### Viewing Screenshots

Screenshots are automatically embedded in the HTML test report:
```bash
npm run test:report
```

---

## 🧰 Troubleshooting

### Issue: Tests failing to connect to backend

**Solution:**
1. Ensure backend is running on `http://localhost:8000`
2. Check backend health endpoint: `http://localhost:8000/api/v1/health`
3. Verify database connection

### Issue: Tests failing to connect to frontend

**Solution:**
1. Ensure frontend is running on `http://localhost:3000`
2. Check if Vite dev server started successfully
3. Try accessing manually in browser

### Issue: Admin user not found

**Solution:**
1. Create admin user using: `python backend/create_admin.py`
2. Verify credentials match those in test file
3. Check database for user existence

### Issue: Screenshots not being captured

**Solution:**
1. Check directory permissions for `tests/screenshots/`
2. Ensure helper function `takeScreenshot()` is called correctly
3. Verify disk space available

### Issue: Tests timeout

**Solution:**
1. Increase timeout in `playwright.config.ts`:
   ```typescript
   timeout: 120000  // 2 minutes
   ```
2. Check network speed and backend response time
3. Disable parallel test execution:
   ```typescript
   fullyParallel: false
   ```

### Issue: Element not found errors

**Solution:**
1. Check if application UI has changed
2. Update selectors in page object files
3. Use Playwright Inspector to identify correct selectors:
   ```bash
   npm run test:debug
   ```

### Issue: File upload tests failing

**Solution:**
1. Ensure test files exist in `test-files/` directory
2. Run: `npm run generate:files`
3. Check file permissions

---

## 📊 Test Results

### HTML Report

After running tests, view the HTML report:
```bash
npm run test:report
```

This opens an interactive report showing:
- Test execution summary
- Pass/fail status for each test
- Screenshots of each step
- Test execution time
- Error details for failed tests

### JSON Report

Test results are also saved as JSON:
```
e2e-tests/test-results.json
```

### Test Artifacts

Test artifacts are saved in:
```
e2e-tests/test-results/
├── traces/       # Playwright traces for debugging
├── videos/       # Test execution videos (on failure)
└── screenshots/  # Failure screenshots
```

### Viewing Traces

For failed tests, you can view the trace:
```bash
npx playwright show-trace test-results/path-to-trace.zip
```

---

## 🎯 Test Scenarios

### Complete Admin Workflow Test (TC-ADMIN-100)

This is the main comprehensive test that validates the entire workflow:

1. **Login** as admin
2. **Create** a new project
3. **Upload** documents
4. **Extract** BOQ using AI
5. **Create** procurement packages
6. **Add** suppliers
7. **Send** RFQs
8. **Upload** and evaluate offers
9. **View** pricing summary
10. **Export** results

**Expected Duration:** 2-3 minutes

### Individual Feature Tests

Each feature has dedicated test cases:

- **TC-ADMIN-001 to TC-ADMIN-003**: Authentication tests
- **TC-ADMIN-010 to TC-ADMIN-012**: Project management tests
- **TC-ADMIN-020 to TC-ADMIN-022**: BOQ management tests
- **TC-ADMIN-030 to TC-ADMIN-032**: Supplier management tests
- **TC-ADMIN-040 to TC-ADMIN-044**: Admin features tests
- **TC-ADMIN-050 to TC-ADMIN-051**: Form validation tests
- **TC-ADMIN-060 to TC-ADMIN-061**: Navigation tests
- **TC-ADMIN-070**: Permissions tests

---

## 📝 Writing New Tests

### Using Page Object Model

Example of creating a new test:

```typescript
import { test } from '@playwright/test';
import { LoginPage } from './pages/login.page';
import { ProjectsPage } from './pages/projects.page';

test('My New Test', async ({ page }) => {
  const loginPage = new LoginPage(page);
  const projectsPage = new ProjectsPage(page);

  // Step 1: Login
  await loginPage.navigate();
  await loginPage.login('admin@bidops.test', 'Admin@123');

  // Step 2: Navigate to projects
  await projectsPage.navigate();

  // Step 3: Verify projects list
  await projectsPage.verifyProjectsList();
});
```

### Adding New Page Objects

1. Create new file in `pages/` directory
2. Extend base page functionality
3. Add selectors and actions
4. Include screenshot calls at important steps

---

## 🔒 Security Considerations

- **Never commit real credentials** to version control
- Use **environment variables** for sensitive data
- **Clear test data** after test execution
- **Disable admin tests** in production environments

---

## 📞 Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Playwright documentation: https://playwright.dev
3. Check application logs in `backend/logs/`
4. Review browser console for frontend errors

---

## 📄 License

Part of BidOps AI project. See main project README for license information.

---

**Last Updated:** 2026-01-28

**Version:** 1.0.0

**Maintained by:** QA Automation Team
