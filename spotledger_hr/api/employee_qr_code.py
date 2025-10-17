import frappe
from frappe import _
from spotledger_hr.utilities.qr_code_generator import get_employee_qr_code, get_employee_qr_code_with_legacy_code


@frappe.whitelist()
def get_employee_qr_code_api(employee_id, use_legacy_code=False):
    """API endpoint to get QR code for an employee.
    
    Args:
        employee_id (str): Employee document name/ID
        use_legacy_code (bool): Whether to use custom_old_code if available
        
    Returns:
        dict: Response with QR code data URL
    """
    try:
        # Validate employee exists
        if not frappe.db.exists("Employee", employee_id):
            frappe.throw(_("Employee {0} not found").format(employee_id))
        
        # Generate QR code
        if use_legacy_code:
            qr_code_data = get_employee_qr_code_with_legacy_code(employee_id)
        else:
            qr_code_data = get_employee_qr_code(employee_id)
        
        return {
            "status": "success",
            "qr_code": qr_code_data,
            "employee_id": employee_id
        }
        
    except Exception as e:
        frappe.logger().error(f"Employee QR Code API error: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def generate_qr_code_for_print(employee_id, use_legacy_code=False):
    """Generate QR code for print format.
    
    Args:
        employee_id (str): Employee document name/ID
        use_legacy_code (bool): Whether to use custom_old_code if available
        
    Returns:
        str: QR code data URL for print format
    """
    try:
        if use_legacy_code:
            return get_employee_qr_code_with_legacy_code(employee_id)
        else:
            return get_employee_qr_code(employee_id)
            
    except Exception as e:
        frappe.logger().error(f"Print QR Code generation error: {str(e)}")
        return None
