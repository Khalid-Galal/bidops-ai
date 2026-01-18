# BidOps AI - E2E Test Suite

Comprehensive end-to-end testing for BidOps AI using Playwright.

## Overview

This test suite provides complete coverage of BidOps AI functionality including:

- ✅ Authentication & Authorization
- ✅ Dashboard & Analytics
- ✅ Project Management (CRUD operations)
- ✅ Document Processing & Upload
- ✅ AI-Powered BOQ Extraction (using Gemini 2.5)
- ✅ Package Management
- ✅ Supplier Management & RFQ Workflow
- ✅ Offer Evaluation & Comparison
- ✅ Pricing Analysis & Export
- ✅ Responsive Design & Accessibility
- ✅ Error Handling & Edge Cases

## Test Coverage

- **Total Test Cases**: 47
- **Critical Tests**: 15
- **High Priority**: 18
- **Medium Priority**: 12
- **Low Priority**: 2

### Test Categories

1. **Authentication** (4 tests) - TC001-TC004
2. **Dashboard** (1 test) - TC005
3. **Project Management** (4 tests) - TC006-TC009
4. **Document Processing** (4 tests) - TC010-TC013
5. **BOQ Extraction** (4 tests) - TC014-TC017
6. **Package Management** (4 tests) - TC018-TC021
7. **Supplier Management** (5 tests) - TC022-TC026
8. **Offer Evaluation** (5 tests) - TC027-TC031
9. **Pricing & Export** (3 tests) - TC032-TC034
10. **Search & Filter** (3 tests) - TC035-TC037
11. **Error Handling** (4 tests) - TC038-TC041
12. **Performance** (3 tests) - TC042-TC044
13. **Responsive & Accessibility** (3 tests) - TC045-TC047

## Prerequisites

### 1. Environment Setup

Ensure Docker services are running:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 2. Backend Services

The following services must be running:
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **Qdrant**: localhost:6333
- **FastAPI**: localhost:8000

### 3. Frontend Application

React frontend should be accessible at:
- **Frontend**: localhost:3000

### 4. Configuration

Ensure `.env` file is configured with:
```bash
GOOGLE_API_KEY=AIzaSyBgieScUSlySRym1BE4WORGUSFUwzypOAI
POSTGRES_USER=bidops
POSTGRES_PASSWORD=bidops_dev
POSTGRES_DB=bidops
SECRET_KEY=dev-secret-key-not-for-production
```

## Installation

```bash
cd e2e-tests
npm install
npx playwright install
```

## Running Tests

### Run All Tests
```bash
npm test
```

### Run with UI (Interactive Mode)
```bash
npm run test:ui
```

### Run in Headed Mode (See Browser)
```bash
npm run test:headed
```

### Run Specific Browser
```bash
npm run test:chrome    # Chrome only
npm run test:firefox   # Firefox only
npm run test:webkit    # Safari only
```

### Debug Tests
```bash
npm run test:debug
```

### View Test Report
```bash
npm run test:report
```

## Test Data

### Default Test User

```javascript
{
  email: 'admin@bidops.test',
  password: 'Admin@123'
}
```

### Test Projects

Create these projects manually or let tests create them:
- "Test Project E2E"
- "Dubai Metro Extension - Package A"
- "Abu Dhabi Hospital Construction"

### Test Suppliers

- "ABC Electrical Contractors LLC"
- "XYZ Mechanical Services"
- "DEF Civil Works"

## Test Execution Flow

### Recommended Order

1. **Authentication Tests** (TC001-TC004)
   - Establishes login capability

2. **Dashboard Tests** (TC005)
   - Verifies basic dashboard functionality

3. **Project Management** (TC006-TC009)
   - Creates test projects for subsequent tests

4. **Document Processing** (TC010-TC013)
   - Uploads documents for BOQ extraction

5. **BOQ Extraction** (TC014-TC017)
   - Tests AI-powered extraction with Gemini

6. **Package Management** (TC018-TC021)
   - Creates packages from BOQ items

7. **Supplier Management** (TC022-TC026)
   - Sets up suppliers for RFQs

8. **Offer Evaluation** (TC027-TC031)
   - Tests offer comparison and evaluation

9. **Pricing & Export** (TC032-TC034)
   - Final pricing and export tests

## Configuration

### Playwright Config

Key settings in `playwright.config.ts`:

```typescript
{
  baseURL: 'http://localhost:3000',
  timeout: 60000,              // 60 seconds per test
  actionTimeout: 15000,        // 15 seconds per action
  navigationTimeout: 30000,    // 30 seconds for navigation
  retries: 2,                  // Retry failed tests 2 times
  workers: 1,                  // Run tests sequentially
}
```

### Browser Support

Tests run on:
- ✅ Chromium (Chrome/Edge)
- ✅ Firefox
- ✅ WebKit (Safari)
- ✅ Mobile Chrome (Pixel 5)
- ✅ Mobile Safari (iPhone 12)

## Test Results

### Output Artifacts

After running tests, you'll find:

```
e2e-tests/
├── playwright-report/     # HTML test report
├── test-results/          # Screenshots, videos, traces
└── test-results.json      # JSON test results
```

### Viewing Reports

```bash
npm run test:report
```

Opens interactive HTML report showing:
- ✅ Passed tests
- ❌ Failed tests
- ⏭️ Skipped tests
- 📸 Screenshots on failure
- 🎥 Videos of failed tests
- 🔍 Trace viewer for debugging

## Debugging Failed Tests

### 1. View Screenshot
```bash
# Screenshots saved to: test-results/{test-name}/screenshots/
```

### 2. Watch Video
```bash
# Videos saved to: test-results/{test-name}/videos/
```

### 3. Use Trace Viewer
```bash
npx playwright show-trace test-results/{test-name}/trace.zip
```

### 4. Run in Debug Mode
```bash
npm run test:debug -- --grep "TC001"
```

## Common Issues & Solutions

### Issue: Tests Timeout

**Solution**: Increase timeouts in `playwright.config.ts`:
```typescript
timeout: 120000  // 2 minutes
```

### Issue: Authentication Fails

**Solution**: Check backend is running and credentials are correct:
```bash
curl http://localhost:8000/api/v1/health
```

### Issue: AI Extraction Fails

**Solution**: Verify Gemini API key is set:
```bash
echo $GOOGLE_API_KEY
# or check .env file
```

### Issue: Docker Services Not Running

**Solution**: Start Docker services:
```bash
cd ../
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml ps
```

### Issue: Frontend Not Accessible

**Solution**: Start frontend dev server:
```bash
cd ../frontend
npm install
npm run dev
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 20

      - name: Install dependencies
        run: |
          cd e2e-tests
          npm install
          npx playwright install --with-deps

      - name: Start services
        run: docker-compose -f docker-compose.dev.yml up -d

      - name: Run tests
        run: |
          cd e2e-tests
          npm test
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}

      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: e2e-tests/playwright-report/
```

## Performance Benchmarks

Expected test execution times:

| Test Suite | Duration |
|------------|----------|
| Authentication | 30s |
| Dashboard | 10s |
| Projects | 45s |
| Documents | 60s |
| BOQ Extraction | 90s (AI processing) |
| Packages | 40s |
| Suppliers | 35s |
| Offers | 50s |
| Pricing | 30s |
| **Total** | **~7 minutes** |

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Clean State**: Reset database between test runs
3. **Explicit Waits**: Use `waitForSelector` instead of `waitForTimeout`
4. **Page Objects**: Consider using Page Object Model for complex tests
5. **Test Data**: Use factories or fixtures for test data
6. **Assertions**: Always assert expected outcomes
7. **Screenshots**: Enable on failures for debugging

## Contributing

When adding new tests:

1. Follow naming convention: `TC###: Description`
2. Add to appropriate test suite
3. Update test count in README
4. Document any new test data requirements
5. Ensure tests are idempotent

## Support

For issues or questions:
- Check test logs in `test-results/`
- Review Playwright documentation: https://playwright.dev
- Consult BidOps AI API docs: http://localhost:8000/docs

## License

Proprietary - All rights reserved
