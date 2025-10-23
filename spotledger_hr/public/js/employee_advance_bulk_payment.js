// Copyright (c) SpotLedger, All rights reserved
// License: GNU General Public License v3.0

// List View Settings for Employee Advance bulk operations
frappe.listview_settings["Employee Advance"] = {
	add_fields: ["status", "company", "advance_amount", "paid_amount", "docstatus", "employee_name"],
	
	onload(listview) {
		// Add "Create Bulk Payment" action to list view
		listview.page.add_actions_menu_item(
			__("Create Bulk Payment"),
			function() {
				const checked_items = listview.get_checked_items();
				
				// Validation: At least one record selected
				if (!checked_items.length) {
					frappe.msgprint({
						title: __("No Selection"),
						message: __("Please select at least one Employee Advance"),
						indicator: "orange"
					});
					return;
				}
				
				// Show preview dialog with selected records
				show_bulk_payment_preview_dialog(checked_items);
			},
			"icon-bolt"
		);
	}
};

/**
 * Display preview dialog showing selected Employee Advances
 * Allows user to review before processing
 */
function show_bulk_payment_preview_dialog(selected_items) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create Bulk Payment Entries"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "preview_section",
				label: ""
			}
		],
		primary_action_label: __("Create Payment"),
		primary_action(d) {
			execute_bulk_payment_creation(selected_items);
			dialog.hide();
		},
		secondary_action_label: __("Cancel")
	});

	const preview_html = create_preview_html(selected_items);
	dialog.set_df_property("preview_section", "options", preview_html);
	dialog.show();
}

/**
 * Generate HTML for preview dialog
 * Shows table with selected records and summary
 */
function create_preview_html(items) {
	let html = `
		<div class="bulk-payment-preview" style="padding: 15px;">
			<h6 style="margin-bottom: 15px;"><i class="fa fa-info-circle"></i> ${__("Selected Employee Advances:")}</h6>
			<div style="overflow-x: auto;">
				<table class="table table-bordered table-sm">
					<thead class="table-light">
						<tr>
							<th>${__("Employee Advance")}</th>
							<th>${__("Employee")}</th>
							<th class="text-right">${__("Advance Amount")}</th>
							<th class="text-right">${__("Paid Amount")}</th>
							<th class="text-right">${__("Outstanding")}</th>
							<th>${__("Status")}</th>
							<th>${__("Company")}</th>
						</tr>
					</thead>
					<tbody>
	`;
	
	let total_outstanding = 0;
	items.forEach(item => {
		const status_badge = get_status_badge(item.status);
		const outstanding = flt(item.advance_amount || 0) - flt(item.paid_amount || 0);
		total_outstanding += outstanding;
		
		html += `
			<tr>
				<td><strong>${item.name}</strong></td>
				<td>${item.employee_name || item.employee || "-"}</td>
				<td class="text-right">${frappe.format(item.advance_amount || 0, { fieldtype: "Currency" })}</td>
				<td class="text-right">${frappe.format(item.paid_amount || 0, { fieldtype: "Currency" })}</td>
				<td class="text-right"><strong>${frappe.format(outstanding, { fieldtype: "Currency" })}</strong></td>
				<td>${status_badge}</td>
				<td>${item.company || "-"}</td>
			</tr>
		`;
	});
	
	html += `
					</tbody>
				</table>
			</div>
			<div class="alert alert-info" role="alert" style="margin-top: 15px;">
				<i class="fa fa-info-circle"></i>
				<small>${__("Only submitted Employee Advances with Unpaid status will be processed. Others will be skipped and shown in results.")}</small>
			</div>
			<div class="row" style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
				<div class="col-md-6">
					<small class="text-muted">${__("Total Records:")}</small><br>
					<strong style="font-size: 18px;">${items.length}</strong>
				</div>
				<div class="col-md-6 text-right">
					<small class="text-muted">${__("Total Outstanding Amount:")}</small><br>
					<strong style="font-size: 18px; color: #28a745;">${frappe.format(total_outstanding, { fieldtype: "Currency" })}</strong>
				</div>
			</div>
		</div>
	`;
	
	return html;
}

/**
 * Get colored status badge
 */
function get_status_badge(status) {
	const status_color_map = {
		"Unpaid": "danger",
		"Paid": "success",
		"Claimed": "info",
		"Returned": "secondary",
		"Partly Claimed and Returned": "warning",
		"Draft": "warning",
		"Cancelled": "dark"
	};
	
	const color = status_color_map[status] || "secondary";
	return `<span class="badge badge-${color}">${status}</span>`;
}

/**
 * Execute bulk payment creation
 * Calls backend with progress bar feedback
 */
function execute_bulk_payment_creation(selected_items) {
	const item_names = selected_items.map(item => item.name);
	const total = item_names.length;
	
	// Show progress bar
	frappe.show_progress(__("Creating Payment Entries"), 0, total);
	
	let progress = 0;
	const progress_interval = setInterval(() => {
		if (progress < total * 0.9) { // Increment until 90%
			progress += Math.max(1, Math.floor(total / 10));
			frappe.show_progress(__("Creating Payment Entries"), progress, total);
		}
	}, 200); // Update every 200ms
	
	// Call backend endpoint
	frappe.call({
		method: "spotledger_hr.utilities.bulk_advances_payment.create_bulk_payment_entries",
		args: {
			employee_advance_names: item_names
		},
		callback: function(r) {
			clearInterval(progress_interval);
			frappe.show_progress(__("Creating Payment Entries"), total, total); // Complete the progress bar
			frappe.hide_progress();
			
			if (r.message) {
				show_bulk_payment_results_dialog(r.message);
				// Refresh list view to show updated statuses
				if (cur_list) {
					cur_list.refresh();
				}
			}
		},
		error: function(r) {
			clearInterval(progress_interval);
			frappe.hide_progress();
			
			// Parse error message
			let error_msg = __("Error creating bulk payment entries. Please try again.");
			if (r.responseJSON && r.responseJSON.message) {
				error_msg = r.responseJSON.message;
			}
			
			frappe.msgprint({
				title: __("Error"),
				message: error_msg,
				indicator: "red"
			});
		}
	});
}

/**
 * Display comprehensive results dialog
 * Shows success, failed, and summary information
 */
function show_bulk_payment_results_dialog(result) {
	const dialog = new frappe.ui.Dialog({
		title: __("Bulk Payment Creation - Results"),
		width: 900,
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "results_section",
				label: ""
			}
		],
		primary_action_label: __("Close"),
		primary_action() {
			dialog.hide();
		}
	});
	
	const results_html = create_results_html(result);
	dialog.set_df_property("results_section", "options", results_html);
	dialog.show();
}

/**
 * Generate comprehensive HTML for results dialog
 */
function create_results_html(result) {
	const summary = result.summary;
	const success_count = result.success.length;
	const failed_count = result.failed.length;
	
	// Determine summary indicator color
	let summary_indicator = "info";
	if (failed_count === 0 && success_count > 0) {
		summary_indicator = "success";
	} else if (success_count === 0) {
		summary_indicator = "danger";
	}
	
	let html = `
		<div class="bulk-payment-results" style="padding: 0;">
			<!-- Summary Section -->
			<div class="alert alert-${summary_indicator}" style="margin-bottom: 20px; border-radius: 4px;">
				<h6 style="margin-bottom: 15px;"><i class="fa fa-bar-chart"></i> <strong>${__("Summary")}</strong></h6>
				<div class="row">
					<div class="col-md-3 text-center" style="border-right: 1px solid rgba(255,255,255,0.3); padding: 10px 0;">
						<div style="font-size: 12px; opacity: 0.8;">${__("Total Selected")}</div>
						<div style="font-size: 24px; font-weight: bold; margin-top: 5px;">${summary.total_selected}</div>
					</div>
					<div class="col-md-3 text-center" style="border-right: 1px solid rgba(255,255,255,0.3); padding: 10px 0;">
						<div style="font-size: 12px; opacity: 0.8;">${__("Successfully Created")}</div>
						<div style="font-size: 24px; font-weight: bold; margin-top: 5px; color: #28a745;">${summary.total_created}</div>
					</div>
					<div class="col-md-3 text-center" style="border-right: 1px solid rgba(255,255,255,0.3); padding: 10px 0;">
						<div style="font-size: 12px; opacity: 0.8;">${__("Failed/Skipped")}</div>
						<div style="font-size: 24px; font-weight: bold; margin-top: 5px; color: #dc3545;">${summary.total_failed}</div>
					</div>
					<div class="col-md-3 text-center; padding: 10px 0;">
						<div style="font-size: 12px; opacity: 0.8;">${__("Total Amount Processed")}</div>
						<div style="font-size: 18px; font-weight: bold; margin-top: 5px;">${frappe.format(summary.total_amount, { fieldtype: "Currency" })}</div>
					</div>
				</div>
			</div>
	`;
	
	// Success section
	if (success_count > 0) {
		html += `
			<div style="margin-bottom: 25px;">
				<h6 style="margin-bottom: 12px; color: #28a745;">
					<i class="fa fa-check-circle"></i> ${__("Successfully Created")} <span class="badge badge-success">${success_count}</span>
				</h6>
				<div style="overflow-x: auto;">
					<table class="table table-bordered table-sm" style="margin-bottom: 0;">
						<thead class="table-light">
							<tr>
								<th>${__("Employee Advance")}</th>
								<th>${__("Payment Entry")}</th>
								<th>${__("Employee")}</th>
								<th class="text-right">${__("Amount")}</th>
							</tr>
						</thead>
						<tbody>
		`;
		
		result.success.forEach(item => {
			html += `
				<tr>
					<td><strong>${item.employee_advance}</strong></td>
					<td>
						<a href="/app/payment-entry/${item.payment_entry}" target="_blank" style="font-weight: 500;">
							${item.payment_entry}
							<i class="fa fa-external-link" style="margin-left: 5px; font-size: 11px;"></i>
						</a>
					</td>
					<td>${item.employee}</td>
					<td class="text-right"><strong>${frappe.format(item.amount, { fieldtype: "Currency" })}</strong></td>
				</tr>
			`;
		});
		
		html += `
						</tbody>
					</table>
				</div>
			</div>
		`;
	}
	
	// Failed section
	if (failed_count > 0) {
		html += `
			<div style="margin-bottom: 15px;">
				<h6 style="margin-bottom: 12px; color: #dc3545;">
					<i class="fa fa-times-circle"></i> ${__("Failed/Skipped")} <span class="badge badge-danger">${failed_count}</span>
				</h6>
				<div style="overflow-x: auto;">
					<table class="table table-bordered table-sm" style="margin-bottom: 0;">
						<thead class="table-light">
							<tr>
								<th>${__("Employee Advance")}</th>
								<th>${__("Reason")}</th>
							</tr>
						</thead>
						<tbody>
		`;
		
		result.failed.forEach(item => {
			html += `
				<tr>
					<td><strong>${item.employee_advance}</strong></td>
					<td><small style="color: #dc3545;">${item.reason}</small></td>
				</tr>
			`;
		});
		
		html += `
						</tbody>
					</table>
				</div>
			</div>
		`;
	}
	
	html += `</div>`;
	
	return html;
}
