# QR Code Integration for Spotledger HR

This document describes the QR code functionality that has been integrated into the Spotledger HR app, migrated from the legacy Breeze Payroll system.

## Overview

The QR code functionality allows generation of QR codes for Employee documents, which can be used for employee identification, attendance tracking, and other HR processes.

## Features

- **Employee QR Code Generation**: Generate QR codes for any Employee document
- **Legacy Code Support**: Use custom_old_code field if available for QR code data
- **Print Format Integration**: QR codes are included in Employee print formats
- **API Endpoints**: RESTful API for QR code generation
- **Web Interface**: JavaScript integration for Employee forms

## Files Added/Modified

### Core Files
- `spotledger_hr/utilities/qr_code_generator.py` - Main QR code generation logic
- `spotledger_hr/api/employee_qr_code.py` - API endpoints for QR code functionality
- `spotledger_hr/public/js/employee_qr_code.js` - JavaScript for Employee form integration

### Configuration Files
- `spotledger_hr/fixtures/custom_field.json` - Added custom_qr_code field to Employee doctype
- `spotledger_hr/fixtures/print_format_employee_qr.json` - Print format with QR code
- `spotledger_hr/hooks.py` - Updated to include JavaScript and fixtures

### Assets
- `spotledger_hr/public/qrfont.ttf` - Custom font for QR code text overlay

## Usage

### 1. Employee Form Integration

When viewing an Employee document:
- QR code is automatically generated and displayed in the `custom_qr_code` field
- A "Generate QR Code" button is available in the Actions menu
- QR code updates automatically when the `custom_old_code` field changes

### 2. API Usage

```python
# Generate QR code for an employee
from spotledger_hr.api.employee_qr_code import get_employee_qr_code_api

result = get_employee_qr_code_api("EMP-001", use_legacy_code=True)
if result["status"] == "success":
    qr_code_data_url = result["qr_code"]
```

### 3. Print Format

The "Employee QR Code" print format includes:
- Employee information in a structured table
- QR code displayed prominently
- Government ID information (if available)
- Generation timestamp

### 4. Direct Function Usage

```python
from spotledger_hr.utilities.qr_code_generator import get_employee_qr_code

# Generate QR code using employee name
qr_code = get_employee_qr_code("EMP-001")

# Generate QR code using legacy code if available
qr_code = get_employee_qr_code_with_legacy_code("EMP-001")
```

## QR Code Data Format

The QR code contains different data based on the generation method:

1. **Standard QR Code**: `{employee_name} - {employee_id}`
2. **Legacy Code QR Code**: `{custom_old_code}` (if available)
3. **Fallback**: `{employee_id}` only

## Dependencies

- `qrcode` - Python QR code generation library
- `PIL` (Pillow) - Image processing for text overlay
- `frappe` - Framework integration

## Installation

1. The QR code functionality is automatically installed with the Spotledger HR app
2. Custom fields and print formats are created via fixtures
3. JavaScript files are loaded via hooks configuration

## Testing

Run the test script to verify functionality:

```bash
cd /home/frappe/frappe-bench/apps/spotledger_hr
python test_qr_code.py
```

## Migration from Legacy System

The QR code functionality has been migrated from:
- **Source**: `legacy_code/breeze_payroll/breeze_payroll/qr_code_generator.py`
- **Improvements Made**:
  - Better error handling and logging
  - Integration with Frappe framework
  - Support for legacy employee codes
  - Web interface integration
  - Print format support
  - API endpoints for external access

## Troubleshooting

### Common Issues

1. **QR Code not generating**: Check if employee document exists and has required fields
2. **Font not found**: Ensure `qrfont.ttf` is in the public directory
3. **API errors**: Check Frappe logs for detailed error messages

### Error Handling

All functions include proper error handling and logging:
- Errors are logged to Frappe logger
- User-friendly error messages are displayed
- Graceful fallbacks for missing data

## Future Enhancements

Potential improvements for the QR code functionality:
- QR code customization options (size, colors, etc.)
- Batch QR code generation
- QR code scanning integration
- Mobile app integration
- Advanced employee identification features


