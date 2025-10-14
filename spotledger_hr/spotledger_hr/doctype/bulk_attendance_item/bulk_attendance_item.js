// Copyright (c) 2025, SpotLedger and contributors
// For license information, please see license.txt

frappe.listview_settings['Bulk Attendance Item'] = {
	add_fields: ["status", "employee", "employee_name", "day"],

	get_indicator: function(doc) {
		const status_colors = {
			"Present": "green",
			"Error": "orange",
			"Absent": "red"
		};

		return [__(doc.status), status_colors[doc.status] || "grey", "status,=," + doc.status];
	},

	formatters: {
		status: function(value) {
			const colors = {
				"Present": "green",
				"Error": "orange",
				"Absent": "red"
			};

			return `<span class="indicator-pill ${colors[value] || 'grey'} small">${__(value)}</span>`;
		}
	},

	onload: function(listview) {
		// Add custom filters for bulk operations
		listview.page.add_menu_item(__("Bulk Update Status"), function() {
			listview.bulk_update_status();
		});
	},

	bulk_update_status: function() {
		let selected = listview.get_checked_items();
		if (!selected.length) {
			frappe.msgprint(__("Please select items to update"));
			return;
		}

		frappe.prompt({
			label: __("New Status"),
			fieldname: "status",
			fieldtype: "Select",
			options: "Present\nError\nAbsent",
			reqd: 1
		}, function(values) {
			frappe.call({
				method: "frappe.desk.form.bulk_update.submit_cancel_or_update_docs",
				args: {
					doctype: "Bulk Attendance Item",
					docs: selected,
					field: "status",
					value: values.status,
					action: "update"
				},
				callback: function(r) {
					if (r.message) {
						frappe.msgprint(__("Status updated for {0} items", [selected.length]));
						listview.refresh();
					}
				}
			});
		}, __("Bulk Update Status"), __("Update"));
	}
};

