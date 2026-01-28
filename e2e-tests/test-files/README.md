# Test Files Directory

This directory contains sample files used for E2E testing.

## File Types Supported

The BidOps AI application supports the following file types for testing:

### Documents
- **PDF** - Tender documents, BOQ files
- **Word (.docx)** - Project specifications, proposals
- **Excel (.xlsx)** - BOQ spreadsheets, pricing tables
- **PowerPoint (.pptx)** - Presentations

### CAD/BIM Files
- **DWG/DXF** - AutoCAD drawings
- **IFC** - Building Information Models

### Email Files
- **MSG** - Outlook messages
- **EML** - Standard email format

### Images
- **PNG/JPG** - Scanned documents, drawings
- **TIFF** - High-quality scans

## Creating Test Files

To create test files for automated testing:

1. **For Document Upload Tests:**
   - Create simple PDF files with sample tender information
   - Include BOQ tables in Excel format
   - Add project specifications in Word format

2. **For BOQ Extraction Tests:**
   - Create PDF files with clear table structures
   - Include item codes, descriptions, quantities, and units
   - Use standard BOQ formatting

3. **For Offer Evaluation Tests:**
   - Create Excel files with supplier pricing information
   - Include all BOQ items with unit prices
   - Add supplier details

## Sample File Generation Script

You can generate sample test files using the provided script:

```bash
node generate-test-files.js
```

This will create:
- `sample-tender.pdf` - Sample tender document
- `sample-boq.xlsx` - Sample BOQ spreadsheet
- `sample-offer.xlsx` - Sample supplier offer
- `sample-spec.docx` - Sample specification document

## File Naming Convention

Test files should follow this naming pattern:
- `test-[type]-[description].[ext]`
- Example: `test-boq-concrete-works.xlsx`

## Important Notes

- Keep test files small (< 5MB) for faster test execution
- Use realistic but anonymized data
- Ensure files don't contain sensitive information
- Test files are automatically gitignored
