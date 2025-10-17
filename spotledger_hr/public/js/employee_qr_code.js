// Employee QR Code functionality
frappe.ui.form.on('Employee', {
    refresh: function(frm) {
        // Add QR Code generation button
        if (frm.doc.name) {
            frm.add_custom_button(__('Generate QR Code'), function() {
                generate_qr_code(frm);
            }, __('Actions'));
            
            // Auto-generate QR code on form load
            if (!frm.doc.custom_qr_code) {
                generate_qr_code(frm);
            }
        }
    },
    
    custom_old_code: function(frm) {
        // Regenerate QR code when old code changes
        if (frm.doc.name && frm.doc.custom_old_code) {
            generate_qr_code(frm, true);
        }
    }
});

function generate_qr_code(frm, use_legacy_code = false) {
    frappe.call({
        method: 'spotledger_hr.api.employee_qr_code.get_employee_qr_code_api',
        args: {
            employee_id: frm.doc.name,
            use_legacy_code: use_legacy_code
        },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                // Update the QR code field with the generated image
                frm.set_value('custom_qr_code', 
                    `<img src="${r.message.qr_code}" alt="QR Code" style="max-width: 200px; height: auto;" />`
                );
                frm.save();
                frappe.show_alert({
                    message: __('QR Code generated successfully'),
                    indicator: 'green'
                });
            } else {
                frappe.msgprint(__('Error generating QR Code: ') + (r.message.message || 'Unknown error'));
            }
        },
        error: function(r) {
            frappe.msgprint(__('Error generating QR Code'));
        }
    });
}


