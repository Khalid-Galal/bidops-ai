# BidOps AI - End-to-End Test Cases

## Test Environment
- **Frontend URL**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Test Scenarios

### 1. Authentication Tests

#### TC001: User Login - Valid Credentials
**Priority**: Critical
**Preconditions**: User account exists in database
**Steps**:
1. Navigate to http://localhost:3000/login
2. Enter valid email
3. Enter valid password
4. Click "Login" button
5. Verify redirect to dashboard (/)

**Expected Results**:
- User successfully logs in
- Redirected to dashboard page
- User session is active
- Auth token is stored

#### TC002: User Login - Invalid Credentials
**Priority**: High
**Preconditions**: None
**Steps**:
1. Navigate to http://localhost:3000/login
2. Enter invalid email
3. Enter invalid password
4. Click "Login" button

**Expected Results**:
- Error message displayed
- User remains on login page
- No auth token stored

#### TC003: Protected Route Access Without Login
**Priority**: High
**Preconditions**: User is not logged in
**Steps**:
1. Navigate directly to http://localhost:3000/projects

**Expected Results**:
- User is redirected to /login page
- Cannot access protected routes

#### TC004: User Logout
**Priority**: High
**Preconditions**: User is logged in
**Steps**:
1. Click user menu/avatar
2. Click "Logout" button
3. Verify redirect to login page

**Expected Results**:
- User session is terminated
- Auth token is cleared
- Redirected to login page

---

### 2. Dashboard Tests

#### TC005: Dashboard Data Display
**Priority**: High
**Preconditions**: User is logged in
**Steps**:
1. Navigate to dashboard (/)
2. Verify statistics cards are displayed
3. Verify recent projects list is displayed

**Expected Results**:
- Dashboard loads successfully
- Statistics show correct data
- Recent projects are visible

---

### 3. Project Management Tests

#### TC006: Create New Project
**Priority**: Critical
**Preconditions**: User is logged in
**Steps**:
1. Navigate to /projects
2. Click "New Project" button
3. Fill in project details:
   - Project Name: "Test Project E2E"
   - Client: "Test Client"
   - Description: "Automated E2E Test Project"
4. Click "Create" button

**Expected Results**:
- Project is created successfully
- Success message displayed
- Project appears in projects list
- Redirected to project detail page

#### TC007: View Projects List
**Priority**: High
**Preconditions**: At least one project exists
**Steps**:
1. Navigate to /projects
2. Verify projects table displays
3. Check table columns (Name, Client, Status, Created Date)

**Expected Results**:
- Projects table loads
- All projects are listed
- Pagination works (if applicable)

#### TC008: View Project Details
**Priority**: High
**Preconditions**: Project exists
**Steps**:
1. Navigate to /projects
2. Click on a project row
3. Verify project detail page loads

**Expected Results**:
- Project details are displayed
- Tabs for Documents, BOQ, Packages, Pricing are visible
- Project metadata is correct

#### TC009: Delete Project
**Priority**: Medium
**Preconditions**: Project exists
**Steps**:
1. Navigate to /projects
2. Click delete button on a project
3. Confirm deletion in modal
4. Verify project is removed

**Expected Results**:
- Confirmation modal appears
- Project is deleted from database
- Project removed from list
- Success message displayed

---

### 4. Document Processing Tests

#### TC010: Upload PDF Document
**Priority**: Critical
**Preconditions**: User is logged in, project exists
**Steps**:
1. Navigate to /projects/{id}/documents
2. Click "Upload Document" button
3. Select a PDF file
4. Click "Upload"
5. Wait for processing to complete

**Expected Results**:
- File upload progress shown
- Document appears in documents list
- Document status shows "Processed" or "Ready"
- AI extraction begins automatically

#### TC011: Upload Multiple Document Types
**Priority**: High
**Preconditions**: User is logged in, project exists
**Steps**:
1. Navigate to /projects/{id}/documents
2. Upload the following file types:
   - PDF document
   - DOCX document
   - XLSX spreadsheet
   - DWG/DXF CAD file (if available)
3. Verify all files are processed

**Expected Results**:
- All document types are accepted
- Each document is processed correctly
- Appropriate metadata extracted
- No errors for supported formats

#### TC012: View Document Details
**Priority**: Medium
**Preconditions**: Document exists
**Steps**:
1. Navigate to /projects/{id}/documents
2. Click on a document
3. View document preview/details

**Expected Results**:
- Document details displayed
- Extracted text visible
- Metadata shows correct values

#### TC013: Delete Document
**Priority**: Medium
**Preconditions**: Document exists
**Steps**:
1. Navigate to /projects/{id}/documents
2. Click delete button on document
3. Confirm deletion

**Expected Results**:
- Document removed from list
- File deleted from storage
- Success message displayed

---

### 5. BOQ Extraction Tests (AI-Powered)

#### TC014: AI BOQ Extraction from Documents
**Priority**: Critical
**Preconditions**: Documents uploaded, Gemini API key configured
**Steps**:
1. Navigate to /projects/{id}/boq
2. Click "Extract BOQ" button
3. Select documents for extraction
4. Wait for AI processing
5. Verify BOQ items are generated

**Expected Results**:
- AI extraction starts
- Progress indicator shown
- BOQ items extracted with:
  - Item descriptions
  - Quantities
  - Units
  - Categories
- Items appear in BOQ table

#### TC015: Edit BOQ Item
**Priority**: High
**Preconditions**: BOQ items exist
**Steps**:
1. Navigate to /projects/{id}/boq
2. Click edit on a BOQ item
3. Modify quantity and description
4. Save changes

**Expected Results**:
- Item is editable
- Changes are saved
- Updated values displayed
- Success message shown

#### TC016: Add Manual BOQ Item
**Priority**: Medium
**Preconditions**: User is logged in, project exists
**Steps**:
1. Navigate to /projects/{id}/boq
2. Click "Add Item" button
3. Fill in item details manually
4. Save item

**Expected Results**:
- Manual item added to BOQ
- Item appears in list
- All fields saved correctly

#### TC017: Delete BOQ Item
**Priority**: Medium
**Preconditions**: BOQ item exists
**Steps**:
1. Navigate to /projects/{id}/boq
2. Select a BOQ item
3. Click delete
4. Confirm deletion

**Expected Results**:
- Item removed from BOQ
- Success message displayed

---

### 6. Package Management Tests

#### TC018: Create Package from BOQ Items
**Priority**: Critical
**Preconditions**: BOQ items exist
**Steps**:
1. Navigate to /projects/{id}/packages
2. Click "Create Package" button
3. Select BOQ items to include
4. Enter package name: "Electrical Package E2E"
5. Click "Create"

**Expected Results**:
- Package created successfully
- Selected BOQ items grouped into package
- Package appears in packages list

#### TC019: View Package Details
**Priority**: High
**Preconditions**: Package exists
**Steps**:
1. Navigate to /projects/{id}/packages
2. Click on a package
3. View package details page

**Expected Results**:
- Package details displayed
- All items in package shown
- Specifications and drawings linked (if available)

#### TC020: Edit Package
**Priority**: Medium
**Preconditions**: Package exists
**Steps**:
1. Navigate to /projects/{id}/packages/{packageId}
2. Click edit button
3. Add/remove items
4. Update package name
5. Save changes

**Expected Results**:
- Package updated successfully
- Changes reflected in package list
- Success message displayed

#### TC021: Delete Package
**Priority**: Medium
**Preconditions**: Package exists
**Steps**:
1. Navigate to /projects/{id}/packages
2. Click delete on a package
3. Confirm deletion

**Expected Results**:
- Package deleted
- BOQ items remain (not deleted)
- Success message shown

---

### 7. Supplier Management Tests

#### TC022: Add New Supplier
**Priority**: High
**Preconditions**: User is logged in
**Steps**:
1. Navigate to /suppliers
2. Click "Add Supplier" button
3. Fill in supplier details:
   - Name: "Test Supplier E2E"
   - Email: "supplier@test.com"
   - Phone: "+971501234567"
   - Category: "Electrical"
4. Click "Save"

**Expected Results**:
- Supplier added to database
- Supplier appears in suppliers list
- Success message displayed

#### TC023: View Supplier Details
**Priority**: Medium
**Preconditions**: Supplier exists
**Steps**:
1. Navigate to /suppliers
2. Click on a supplier
3. View supplier detail page

**Expected Results**:
- Supplier information displayed
- History of RFQs shown
- Contact details visible

#### TC024: Send RFQ to Supplier
**Priority**: Critical
**Preconditions**: Supplier exists, package exists
**Steps**:
1. Navigate to /projects/{id}/packages/{packageId}
2. Click "Send RFQ" button
3. Select suppliers
4. Customize RFQ template
5. Click "Send"

**Expected Results**:
- RFQ email sent to selected suppliers
- Email contains:
  - Package details
  - BOQ items
  - Deadline for submission
- RFQ tracked in system
- Success notification shown

#### TC025: Edit Supplier Information
**Priority**: Medium
**Preconditions**: Supplier exists
**Steps**:
1. Navigate to /suppliers/{id}
2. Click "Edit" button
3. Update supplier details
4. Save changes

**Expected Results**:
- Supplier information updated
- Changes reflected in supplier list
- Success message displayed

#### TC026: Delete Supplier
**Priority**: Low
**Preconditions**: Supplier exists, no active RFQs
**Steps**:
1. Navigate to /suppliers
2. Click delete on supplier
3. Confirm deletion

**Expected Results**:
- Supplier deleted from database
- Removed from suppliers list
- Success message shown

---

### 8. Offer Evaluation Tests (AI-Powered)

#### TC027: View Received Offers
**Priority**: High
**Preconditions**: Offers received from suppliers
**Steps**:
1. Navigate to /offers
2. Verify offers list displays
3. Check offer details

**Expected Results**:
- All offers displayed in table
- Offer details include:
  - Supplier name
  - Package
  - Total price
  - Status
  - Submission date

#### TC028: Compare Multiple Offers
**Priority**: Critical
**Preconditions**: Multiple offers exist for same package
**Steps**:
1. Navigate to /offers
2. Select multiple offers for same package
3. Click "Compare Offers" button
4. View comparison matrix

**Expected Results**:
- Comparison view shows:
  - Side-by-side pricing
  - Technical compliance
  - Delivery times
  - Payment terms
- Differences highlighted
- Recommendations from AI

#### TC029: AI Compliance Check on Offer
**Priority**: Critical
**Preconditions**: Offer exists, Gemini API configured
**Steps**:
1. Navigate to /offers/{id}
2. Click "Check Compliance" button
3. Wait for AI analysis
4. View compliance report

**Expected Results**:
- AI analyzes offer against requirements
- Compliance report generated showing:
  - Technical compliance issues
  - Missing items
  - Deviations from specs
  - Recommendations
- Confidence scores displayed

#### TC030: Accept Offer
**Priority**: High
**Preconditions**: Offer exists, compliant
**Steps**:
1. Navigate to /offers/{id}
2. Review offer details
3. Click "Accept Offer" button
4. Confirm acceptance

**Expected Results**:
- Offer status updated to "Accepted"
- Other offers for same package marked as "Rejected"
- Notification sent to supplier
- Success message displayed

#### TC031: Generate Clarification Request (AI)
**Priority**: Medium
**Preconditions**: Offer with issues exists
**Steps**:
1. Navigate to /offers/{id}
2. Click "Request Clarification" button
3. AI generates clarification questions
4. Review and edit questions
5. Send to supplier

**Expected Results**:
- AI identifies unclear/non-compliant items
- Clarification questions generated
- Email sent to supplier
- Request tracked in system

---

### 9. Pricing & Export Tests

#### TC032: View Pricing Summary
**Priority**: High
**Preconditions**: Offers accepted
**Steps**:
1. Navigate to /projects/{id}/pricing
2. View pricing summary dashboard

**Expected Results**:
- Pricing breakdown displayed
- Shows:
  - Total project cost
  - Cost by package
  - Cost by supplier
  - Budget vs actual
- Charts and visualizations visible

#### TC033: Export BOQ with Selected Prices
**Priority**: Critical
**Preconditions**: Offers accepted
**Steps**:
1. Navigate to /projects/{id}/pricing
2. Select accepted offers/prices
3. Click "Export BOQ" button
4. Choose format (Excel)
5. Download file

**Expected Results**:
- Excel file generated
- BOQ populated with:
  - Item descriptions
  - Quantities
  - Unit prices from selected offers
  - Total prices
  - Supplier information
- File downloads successfully
- Format matches client template

#### TC034: Price Adjustment
**Priority**: Medium
**Preconditions**: Pricing exists
**Steps**:
1. Navigate to /projects/{id}/pricing
2. Click edit on a price
3. Apply markup/discount
4. Save changes
5. Verify total updates

**Expected Results**:
- Price adjustment applied
- Totals recalculated
- Changes reflected in export
- Audit trail maintained

---

### 10. Search & Filter Tests

#### TC035: Search Projects
**Priority**: Medium
**Preconditions**: Multiple projects exist
**Steps**:
1. Navigate to /projects
2. Enter search term in search box
3. Verify results filtered

**Expected Results**:
- Projects filtered by search term
- Search works on:
  - Project name
  - Client name
  - Description

#### TC036: Filter BOQ Items
**Priority**: Medium
**Preconditions**: BOQ items exist with categories
**Steps**:
1. Navigate to /projects/{id}/boq
2. Apply category filter
3. Verify filtered results

**Expected Results**:
- BOQ items filtered by category
- Filter options available for:
  - Category
  - Unit
  - Status

#### TC037: Filter Offers by Status
**Priority**: Medium
**Preconditions**: Offers with different statuses exist
**Steps**:
1. Navigate to /offers
2. Filter by status (Pending, Accepted, Rejected)
3. Verify filtered results

**Expected Results**:
- Offers filtered correctly
- Status badge visible on each offer
- Filter persists during session

---

### 11. Error Handling & Edge Cases

#### TC038: Handle Large File Upload
**Priority**: Medium
**Preconditions**: User is logged in
**Steps**:
1. Attempt to upload file > 500MB
2. Verify error handling

**Expected Results**:
- File size validation occurs
- Error message displayed
- Upload prevented
- Clear message about size limit

#### TC039: Handle Network Error During Upload
**Priority**: Medium
**Preconditions**: User is uploading document
**Steps**:
1. Start document upload
2. Simulate network disconnection
3. Verify error handling

**Expected Results**:
- Upload fails gracefully
- Error message displayed
- Option to retry
- No partial/corrupt files stored

#### TC040: Handle AI Service Unavailable
**Priority**: High
**Preconditions**: Gemini API key invalid or service down
**Steps**:
1. Attempt BOQ extraction
2. Verify error handling when AI service fails

**Expected Results**:
- Graceful error handling
- Clear error message to user
- Option to retry
- System remains functional for other tasks

#### TC041: Handle Concurrent User Edits
**Priority**: Medium
**Preconditions**: Two users accessing same project
**Steps**:
1. User A edits BOQ item
2. User B edits same BOQ item simultaneously
3. Both save changes

**Expected Results**:
- Conflict detection mechanism
- Warning about concurrent edits
- Last write wins or conflict resolution UI
- Data integrity maintained

---

### 12. Performance Tests

#### TC042: Dashboard Load Time
**Priority**: Medium
**Preconditions**: User is logged in
**Steps**:
1. Navigate to dashboard
2. Measure page load time

**Expected Results**:
- Dashboard loads within 2 seconds
- All API calls complete within 3 seconds
- No performance degradation with 10+ projects

#### TC043: BOQ Extraction Performance
**Priority**: High
**Preconditions**: Large document uploaded
**Steps**:
1. Upload 50-page PDF
2. Start BOQ extraction
3. Monitor processing time

**Expected Results**:
- Extraction completes within reasonable time
- Progress indicators shown
- User can navigate away during processing
- Notification when complete

#### TC044: Large BOQ Rendering
**Priority**: Medium
**Preconditions**: BOQ with 1000+ items
**Steps**:
1. Navigate to BOQ page
2. Verify table rendering performance

**Expected Results**:
- Table renders without lag
- Pagination or virtual scrolling implemented
- Filters work smoothly
- No browser freezing

---

### 13. Responsive Design & Accessibility

#### TC045: Mobile View - Dashboard
**Priority**: Low
**Preconditions**: User is logged in
**Steps**:
1. Resize browser to mobile dimensions (375x667)
2. Navigate to dashboard
3. Verify responsive layout

**Expected Results**:
- Layout adapts to mobile screen
- All content accessible
- No horizontal scrolling
- Touch-friendly buttons

#### TC046: Accessibility - Keyboard Navigation
**Priority**: Medium
**Preconditions**: User on login page
**Steps**:
1. Navigate using only keyboard (Tab, Enter, Esc)
2. Complete login flow
3. Navigate to projects

**Expected Results**:
- All interactive elements accessible via keyboard
- Focus indicators visible
- Logical tab order
- Can complete all tasks without mouse

#### TC047: Screen Reader Compatibility
**Priority**: Low
**Preconditions**: Screen reader enabled
**Steps**:
1. Navigate through application
2. Verify ARIA labels present
3. Check form labels

**Expected Results**:
- All images have alt text
- Form inputs have labels
- Buttons have descriptive text
- Proper heading hierarchy

---

## Test Data Requirements

### Users
- Admin User: admin@bidops.test / Admin@123
- Regular User: user@bidops.test / User@123

### Projects
- Test Project 1: "Dubai Metro Extension - Package A"
- Test Project 2: "Abu Dhabi Hospital Construction"
- Test Project 3: "Sharjah Residential Complex"

### Documents
- PDF: Tender specifications (10+ pages)
- DOCX: Technical requirements
- XLSX: BOQ template
- DWG: CAD drawings (if available)

### Suppliers
- Supplier 1: "ABC Electrical Contractors LLC"
- Supplier 2: "XYZ Mechanical Services"
- Supplier 3: "DEF Civil Works"

---

## Environment Setup

1. **Backend Services**:
   - PostgreSQL: Running on port 5432
   - Redis: Running on port 6379
   - Qdrant: Running on port 6333
   - FastAPI: Running on port 8000

2. **Frontend**:
   - React App: Running on port 3000

3. **Configuration**:
   - Gemini API Key: Set in .env file
   - SMTP: Configured for email testing
   - Storage: Accessible for file uploads

---

## Execution Notes

1. Run tests in order for dependent scenarios
2. Clean database between test runs for consistency
3. Monitor AI API usage/costs during tests
4. Capture screenshots on failures
5. Log all API responses for debugging
6. Test with both Chrome and Firefox browsers

---

## Expected Coverage

- **Functional Coverage**: 90%+
- **API Coverage**: 85%+
- **UI Coverage**: 80%+
- **Critical Path Coverage**: 100%
