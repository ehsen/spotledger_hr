import qrcode
import frappe
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from qrcode.main import QRCode
from io import BytesIO
from base64 import b64encode


def gen_qrcode(employee_code, name):
    """Generate QR Code Image with employee code and name.
    
    Args:
        employee_code (str): Employee code/ID
        name (str): Employee name
        
    Returns:
        PIL.Image: QR Code image with text overlay
    """
    try:
        qr = qrcode.QRCode(box_size=20)
        qr.add_data(employee_code)
        img = qr.make_image()
        draw = ImageDraw.Draw(img)
        
        # Try to use custom font, fallback to default if not available
        try:
            font = ImageFont.truetype("qrfont.ttf", 30)
        except (OSError, IOError):
            font = ImageFont.load_default()
            
        draw.text((300, 520), employee_code, font=font)
        draw.text((300, 550), name, font=font)
        return img
        
    except Exception as e:
        frappe.logger().error(f"QR Code generation error: {str(e)}")
        frappe.throw("There seems to be a problem with QRCode Generation. Please Contact Support")


def gen_qrcode_bytes(employee_code, format="PNG"):
    """Generate QR Code as bytes.
    
    Args:
        employee_code (str): Employee code/ID
        format (str): Image format (default: PNG)
        
    Returns:
        bytes: QR Code image as bytes
    """
    try:
        qr = qrcode.QRCode(box_size=20)
        qr.add_data(employee_code)
        img = qr.make_image()
        
        buffered = BytesIO()
        img.save(buffered, format=format)
        return buffered.getvalue()

    except Exception as e:
        frappe.logger().error(f"QR Code bytes generation error: {str(e)}")
        raise


def bytes_to_b64(data: bytes) -> str:
    """Convert bytes to base64 string.
    
    Args:
        data (bytes): Binary data
        
    Returns:
        str: Base64 encoded string
    """
    return b64encode(data).decode("utf-8")


def add_file_info(data: str) -> str:
    """Add info about the file type and encoding for browser display.
    
    Args:
        data (str): Base64 encoded data
        
    Returns:
        str: Data URL for browser display
    """
    return f"data:image/png;base64, {data}"


def get_qr_code(employee_code):
    """Get QR Code as base64 data URL for web display.
    
    Args:
        employee_code (str): Employee code/ID
        
    Returns:
        str: Base64 data URL for QR code image
    """
    qrcode_bytes = gen_qrcode_bytes(employee_code=employee_code)
    base64_data = bytes_to_b64(qrcode_bytes)
    return add_file_info(base64_data)


def get_employee_qr_code(employee_id):
    """Get QR Code for an Employee document.
    
    Args:
        employee_id (str): Employee document name/ID
        
    Returns:
        str: Base64 data URL for QR code image
    """
    try:
        employee = frappe.get_doc("Employee", employee_id)
        
        # Use employee name as the QR code data, or employee ID if name is not available
        qr_data = employee.name
        if employee.employee_name:
            qr_data = f"{employee.name} - {employee.employee_name}"
            
        return get_qr_code(qr_data)
        
    except Exception as e:
        frappe.logger().error(f"Employee QR Code generation error: {str(e)}")
        frappe.throw(f"Error generating QR code for employee {employee_id}: {str(e)}")


def get_employee_qr_code_with_legacy_code(employee_id):
    """Get QR Code for an Employee using legacy code if available.
    
    Args:
        employee_id (str): Employee document name/ID
        
    Returns:
        str: Base64 data URL for QR code image
    """
    try:
        employee = frappe.get_doc("Employee", employee_id)
        
        # Use custom_old_code if available, otherwise use employee name
        qr_data = employee.name
        if hasattr(employee, 'custom_old_code') and employee.custom_old_code:
            qr_data = employee.custom_old_code
        elif employee.employee_name:
            qr_data = f"{employee.name}"
            
        return get_qr_code(qr_data)
        
    except Exception as e:
        frappe.logger().error(f"Employee QR Code generation error: {str(e)}")
        frappe.throw(f"Error generating QR code for employee {employee_id}: {str(e)}")
