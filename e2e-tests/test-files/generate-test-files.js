/**
 * Generate Sample Test Files for E2E Testing
 *
 * This script creates sample files that can be used for testing
 * document upload, processing, and extraction features.
 */

const fs = require('fs');
const path = require('path');

// Create a simple text-based PDF (actually a text file, but can be used for testing)
function generateSamplePDF() {
  const content = `
TENDER DOCUMENT
Project: Sample Construction Project
Client: Test Client Company

BILL OF QUANTITIES

Item Code | Description | Quantity | Unit
----------|-------------|----------|-----
001       | Concrete Grade 40 | 500 | M3
002       | Steel Reinforcement | 50 | TON
003       | Formwork | 1000 | M2
004       | Blockwork | 2000 | M2
005       | Plaster | 3000 | M2

Project Timeline: 12 months
Budget: AED 5,000,000
Deadline: 2026-12-31
`;

  fs.writeFileSync(path.join(__dirname, 'sample-tender.txt'), content);
  console.log('✓ Created sample-tender.txt (use as PDF simulation)');
}

// Create a simple CSV file (can be opened as Excel)
function generateSampleBOQ() {
  const content = `Item Code,Description,Quantity,Unit,Unit Price,Total Price
001,Concrete Grade 40 Supply and Installation,500,M3,450,225000
002,Steel Reinforcement Supply and Installation,50,TON,3500,175000
003,Formwork Supply and Installation,1000,M2,85,85000
004,Blockwork 200mm Supply and Installation,2000,M2,120,240000
005,Plaster 25mm Supply and Installation,3000,M2,35,105000`;

  fs.writeFileSync(path.join(__dirname, 'sample-boq.csv'), content);
  console.log('✓ Created sample-boq.csv (use as Excel simulation)');
}

// Create a supplier offer file
function generateSampleOffer() {
  const content = `SUPPLIER QUOTATION
Supplier: ABC Contracting LLC
Email: abc@supplier.com
Phone: +971501234567

PRICE BREAKDOWN

Item Code,Description,Quantity,Unit,Unit Price,Total Price
001,Concrete Grade 40,500,M3,420,210000
002,Steel Reinforcement,50,TON,3400,170000
003,Formwork,1000,M2,80,80000
004,Blockwork 200mm,2000,M2,115,230000
005,Plaster 25mm,3000,M2,32,96000

Total Offer: AED 786,000
Validity: 60 days
Delivery: 30 days
`;

  fs.writeFileSync(path.join(__dirname, 'sample-offer.txt'), content);
  console.log('✓ Created sample-offer.txt (use as PDF simulation)');
}

// Create a specification document
function generateSampleSpec() {
  const content = `PROJECT SPECIFICATION DOCUMENT

Project Name: Sample Construction Project
Project Code: PRJ-2026-001
Location: Dubai, UAE

1. GENERAL REQUIREMENTS
   - All works shall comply with Dubai Municipality standards
   - Materials shall be approved before installation
   - Weekly progress reports required

2. CONCRETE WORKS
   - Grade: 40 N/mm²
   - Slump: 100-150mm
   - Testing: As per BS standards

3. STEEL REINFORCEMENT
   - Grade: 460 N/mm²
   - Welding: As per approved shop drawings
   - Cover: As per structural drawings

4. FORMWORK
   - Material: Steel or approved plywood
   - Stripping time: As per engineer approval
   - Quality: Surface finish as per specifications

5. BLOCKWORK
   - Type: Hollow concrete blocks
   - Size: 200mm thickness
   - Mortar: Grade M4

6. PLASTER
   - Thickness: 25mm
   - Mix: Cement-sand 1:5
   - Finish: Smooth trowel finish
`;

  fs.writeFileSync(path.join(__dirname, 'sample-specification.txt'), content);
  console.log('✓ Created sample-specification.txt (use as Word simulation)');
}

// Main execution
console.log('Generating test files...\n');

try {
  generateSamplePDF();
  generateSampleBOQ();
  generateSampleOffer();
  generateSampleSpec();

  console.log('\n✅ All test files generated successfully!');
  console.log('\nFiles created:');
  console.log('  - sample-tender.txt (simulates PDF)');
  console.log('  - sample-boq.csv (simulates Excel)');
  console.log('  - sample-offer.txt (simulates PDF offer)');
  console.log('  - sample-specification.txt (simulates Word)');
  console.log('\nThese files can be used for E2E testing.');
} catch (error) {
  console.error('Error generating test files:', error);
  process.exit(1);
}
