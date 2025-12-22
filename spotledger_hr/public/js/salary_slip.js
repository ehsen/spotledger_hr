// Custom JavaScript for Salary Slip to fix UI refresh issues with tax components

frappe.ui.form.on('Salary Slip', {
    refresh: function(frm) {
        // Ensure deductions table is refreshed after save
        if (frm.doc.deductions) {
            frm.refresh_field('deductions');
        }
    },

    after_save: function(frm) {
        // Force refresh of deductions table after save to show tax components
        setTimeout(function() {
            if (frm.doc.deductions) {
                frm.refresh_field('deductions');
            }
        }, 500);
    }
});
