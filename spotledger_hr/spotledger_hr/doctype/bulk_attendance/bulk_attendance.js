// Copyright (c) 2025, SpotLedger and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bulk Attendance', {
	refresh: function(frm) {
		// Add custom styling for missing data rows
		frm.trigger('add_missing_data_styling');

		// Set up button actions - always show buttons
		frm.page.set_primary_action(__('Load Data'), function() {
			frm.trigger('load_data');
		});

		if (frm.doc.attendance_data && frm.doc.attendance_data.length > 0) {
			frm.page.set_secondary_action(__('Bulk Update'), function() {
				frm.trigger('bulk_update');
			});
		}

		// Add filter functionality
		frm.trigger('setup_filters');
		
		// Disable popup dialog for child table - allow inline editing only
		if (frm.fields_dict.attendance_data && frm.fields_dict.attendance_data.grid) {
			// Prevent grid row form from opening on click
			frm.fields_dict.attendance_data.grid.grid_form = null;
			
			// Make all fields editable inline
			frm.fields_dict.attendance_data.grid.editable_fields = [
				{fieldname: 'status'},
				{fieldname: 'check_in_date'},
				{fieldname: 'check_in_time'},
				{fieldname: 'check_out_date'},
				{fieldname: 'check_out_time'}
			];
		}
		frm.add_custom_button(__("Upload Attendance"), function() {
            let d = new frappe.ui.Dialog({
                title: 'Upload Attendance File',
                fields: [
                    {
                        label: 'Upload File',
                        fieldname: 'upload_file',
                        fieldtype: 'Attach',
                        reqd: 1
                    }
                ],
                primary_action_label: 'Upload',
                primary_action(values) {
                    if (values.upload_file) {
                        frappe.show_alert({
                            message: __('File uploaded successfully'),
                            indicator: 'green'
                        });
                        
                        // Placeholder for processing uploaded file
                        process_uploaded_file(values.upload_file);
                        
                        d.hide();
                    }
                }
            });
            d.show();
        });

		// Add Sync from Database button
		frm.add_custom_button(__("Sync Attendance"), function() {
			let sync_dialog = new frappe.ui.Dialog({
				title: __('Sync Attendance from Database File'),
				fields: [
					{
						label: __('Upload Database File'),
						fieldname: 'db_file',
						fieldtype: 'Attach',
						description: __('Upload the SQLite attendance database file (.db or .sqlite)'),
						reqd: 1
					},
					{
						fieldtype: 'Section Break',
						label: __('Advanced Options')
					},
					{
						label: __('Batch Size'),
						fieldname: 'batch_size',
						fieldtype: 'Int',
						default: 50,
						description: __('Number of records to save at once (default: 50)')
					},
					{
						fieldtype: 'Column Break'
					},
					{
						label: __('Re-sync from Date (Optional)'),
						fieldname: 'force_from_date',
						fieldtype: 'Datetime',
						description: __('Leave empty to sync only new records')
					}
				],
				primary_action_label: __('Start Sync'),
				primary_action(values) {
					if (!values.db_file) {
						frappe.msgprint(__('Please upload a database file'));
						return;
					}
					sync_dialog.hide();
					
					// Call the sync function directly with values
					frm.events.start_attendance_sync(frm, values);
				}
			});
			sync_dialog.show();
		});
	},

	start_attendance_sync: function(frm, values) {
		console.log('Starting sync with values:', values);  // Debug log
		
		// Extract file path from uploaded file URL
		// Frappe attach field returns full URL like: /files/attendance.db
		let file_url = values.db_file;
		
		if (!file_url) {
			frappe.msgprint(__('No file selected. Please upload a database file.'));
			return;
		}
		
		console.log('File URL:', file_url);
		
		// Declare poll_interval in outer scope
		let poll_interval;
		
		// Show progress dialog
		let progress_dialog = new frappe.ui.Dialog({
			title: __('Syncing Attendance'),
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'progress_area'
				}
			],
			primary_action_label: __('Close'),
			primary_action() {
				if (poll_interval) clearInterval(poll_interval);  // Stop polling when closed
				progress_dialog.hide();
			},
			onhide: function() {
				if (poll_interval) clearInterval(poll_interval);  // Stop polling when hidden
			}
		});
		
		// Create progress HTML
		let progress_html = `
			<div class="progress-sync-container" style="margin: 20px 0;">
				<div class="progress" style="height: 25px; margin-bottom: 15px;">
					<div class="progress-bar progress-bar-striped progress-bar-animated" 
						 role="progressbar" 
						 style="width: 0%;" 
						 id="sync-progress-bar">0%</div>
				</div>
				<div class="sync-status" id="sync-status" style="margin-top: 10px;">
					<p><strong>File:</strong> <span class="text-muted">${file_url.split('/').pop()}</span></p>
					<p><strong>Status:</strong> <span id="sync-status-text">Starting sync...</span></p>
					<p><strong>Progress:</strong> <span id="sync-progress-text">0 of 0</span></p>
					<p><strong>Success:</strong> <span id="sync-success-count" class="text-success">0</span></p>
					<p><strong>Failed:</strong> <span id="sync-failed-count" class="text-danger">0</span></p>
				</div>
			</div>
		`;
		
		progress_dialog.fields_dict.progress_area.$wrapper.html(progress_html);
		progress_dialog.show();
		
		// Disable primary action initially
		progress_dialog.get_primary_btn().prop('disabled', true);
		
		// Listen for progress events - specific to this sync
		let progress_event_id = `attendance_sync_${frappe.session.user}_${Date.now()}`;
		
		frappe.realtime.on("progress", function(data) {
			console.log('Progress event received:', data);
			if (data.progress) {
				let percent = Math.round(data.progress[0]);
				$('#sync-progress-bar').css('width', percent + '%').text(percent + '%');
				$('#sync-status-text').text(data.progress[1] || 'Processing...');
				$('#sync-progress-text').text(data.progress[2] || '');
				
				// Extract counts from description if available
				let desc = data.progress[2] || '';
				let successMatch = desc.match(/Success:\s*(\d+)/);
				let failedMatch = desc.match(/Failed:\s*(\d+)/);
				
				if (successMatch) {
					$('#sync-success-count').text(successMatch[1]);
				}
				if (failedMatch) {
					$('#sync-failed-count').text(failedMatch[1]);
				}
			}
		});
		
		// Also poll for status updates every 2 seconds
		poll_interval = setInterval(function() {
			// Check if dialog is still open
			if (!progress_dialog.$wrapper.is(':visible')) {
				clearInterval(poll_interval);
				return;
			}
			
			// Call a status endpoint to get current progress
			frappe.call({
				method: 'spotledger_hr.controllers.attendance_controller.get_sync_progress',
				args: {
					session_id: frappe.session.sid
				},
				callback: function(r) {
					console.log('Poll response:', r);
					if (r.message && r.message.in_progress) {
						let data = r.message;
						let percent = Math.round((data.processed / data.total) * 100) || 0;
						
						$('#sync-progress-bar').css('width', percent + '%').text(percent + '%');
						$('#sync-status-text').text(data.status || 'Processing...');
						$('#sync-progress-text').text(`${data.processed} of ${data.total}`);
						$('#sync-success-count').text(data.successful || 0);
						$('#sync-failed-count').text(data.failed || 0);
						
						console.log(`Sync progress: ${data.processed}/${data.total} (${percent}%) - Success: ${data.successful}, Failed: ${data.failed}`);
					} else if (r.message && !r.message.in_progress) {
						// Sync completed or not started - stop polling
						console.log('Sync not in progress, stopping poll');
						clearInterval(poll_interval);
					}
				},
				error: function(r) {
					console.error('Poll error:', r);
				}
			});
		}, 2000);  // Poll every 2 seconds
		
		// Update status before making call
		$('#sync-status-text').text('Connecting to server...');
		
		// Set a timeout to detect if call is stuck
		let timeout_id = setTimeout(function() {
			console.warn('API call timeout - no response in 5 seconds');
			$('#sync-status-text').text('Connection timeout - checking...');
		}, 5000);
		
		// Make the API call without freeze
		console.log('About to make API call with:', {
			method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
			file_url: file_url,
			batch_size: values.batch_size || 50,
			force_from_date: values.force_from_date || null
		});
		
		frappe.call({
			method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
			args: {
				attendance_db_path: file_url,
				batch_size: parseInt(values.batch_size) || 50,
				force_from_date: values.force_from_date || null
			},
			freeze: false,
			async: true,
			callback: function(r) {
				clearTimeout(timeout_id);  // Clear timeout on success
				console.log('API callback executed, response:', r);
				// Enable close button when done
				progress_dialog.get_primary_btn().prop('disabled', false);
				
				if (r.message) {
					let result = r.message;
					$('#sync-status-text').text('Completed');
					$('#sync-progress-bar').removeClass('progress-bar-animated');
					
					if (result.success) {
						$('#sync-progress-bar').removeClass('bg-primary').addClass('bg-success');
					} else {
						$('#sync-progress-bar').removeClass('bg-primary').addClass('bg-warning');
					}
					
					// Show final counts
					$('#sync-success-count').text(result.successful || 0);
					$('#sync-failed-count').text(result.failed || 0);
					$('#sync-progress-text').text(`${result.total_records} total records processed`);
					
					// Show employee codes not found (primary error display)
					if (result.employee_not_found_codes && result.employee_not_found_codes.length > 0) {
						let codes_html = '<div class="alert alert-warning" style="margin-top: 15px;">';
						codes_html += '<strong>Employee Codes Not Found:</strong><br>';
						codes_html += '<div style="max-height: 150px; overflow-y: auto; margin-top: 10px;">';
						codes_html += '<code style="display: block; white-space: pre-wrap; word-break: break-all;">';
						codes_html += result.employee_not_found_codes.join(', ');
						codes_html += '</code></div>';
						codes_html += `<small class="text-muted">Total: ${result.employee_not_found_codes.length} employee codes not found</small>`;
						codes_html += '</div>';
						$('#sync-status').append(codes_html);
					}
					
					// Show other errors if any
					if (result.errors && result.errors.length > 0) {
						let error_html = '<div class="alert alert-danger" style="margin-top: 15px;"><strong>Other Errors:</strong><ul>';
						result.errors.slice(0, 5).forEach(err => {
							error_html += `<li>${err.employee_code} (${err.date}): ${err.error}</li>`;
						});
						if (result.errors.length > 5) {
							error_html += `<li><em>...and ${result.errors.length - 5} more. Check Error Log for details.</em></li>`;
						}
						error_html += '</ul></div>';
						$('#sync-status').append(error_html);
					}
					
					// Reload the form to show new data
					frm.reload_doc();
				}
			},
			error: function(r) {
				clearTimeout(timeout_id);  // Clear timeout on error
				console.error('API error - full response:', r);
				console.error('API error - message:', r.message);
				console.error('API error - exc:', r.exc);
				console.error('API error - _server_messages:', r._server_messages);
				
				progress_dialog.get_primary_btn().prop('disabled', false);
				$('#sync-status-text').text('Failed');
				$('#sync-progress-bar').removeClass('progress-bar-animated bg-primary').addClass('bg-danger');
				
				let error_msg = 'Unknown error occurred';
				
				// Try to extract error message from various sources
				if (r._server_messages) {
					try {
						let messages = JSON.parse(r._server_messages);
						if (Array.isArray(messages) && messages.length > 0) {
							// Parse the first message which might be JSON itself
							try {
								let parsed = JSON.parse(messages[0]);
								error_msg = parsed.message || messages[0];
							} catch (e) {
								error_msg = messages[0];
							}
						}
					} catch (e) {
						error_msg = r._server_messages;
					}
				} else if (r.message) {
					error_msg = r.message;
				} else if (r.exc) {
					error_msg = r.exc;
				}
				
				console.log('Extracted error message:', error_msg);
				
				$('#sync-status').append(`
					<div class="alert alert-danger" style="margin-top: 15px;">
						<strong>Error:</strong> ${error_msg}
					</div>
				`);
				
				frappe.msgprint({
					title: __('Sync Failed'),
					message: error_msg,
					indicator: 'red'
				});
			}
		});
	},

	load_data: function(frm) {
		// Validate required fields
		if (!frm.doc.from_date || !frm.doc.to_date) {
			frappe.msgprint(__('Please select From Date and To Date'));
			return;
		}

		// Save the document first if it's new (with ignore_mandatory since child table is empty)
		if (frm.is_new()) {
			frappe.show_alert({message: __('Saving document...'), indicator: 'blue'});
			frm.save('Save', null, null, () => {
				frm.trigger('do_load_data');
			});
		} else {
			frm.trigger('do_load_data');
		}
	},

	do_load_data: function(frm) {
		frappe.show_alert({message: __('Loading attendance data...'), indicator: 'blue'});
		
		frm.call({
			method: 'load_data',
			doc: frm.doc,
			args: {
				docname: frm.doc.name
			},
			freeze: true,
			freeze_message: __('Loading attendance data...'),
			callback: function(r) {
				if (r.message) {
					if (r.message.count > 0) {
						frappe.show_alert({
							message: __('{0} attendance records loaded', [r.message.count]), 
							indicator: 'green'
						});
					} else {
						frappe.msgprint(__('No attendance records found for the selected criteria'));
					}
				}
				// Always reload to show the loaded data
				frm.reload_doc();
			},
			error: function(r) {
				frappe.show_alert({
					message: __('Error loading data. Please check console for details.'), 
					indicator: 'red'
				});
			}
		});
	},

	bulk_update: function(frm) {
		frappe.confirm(
			__('Are you sure you want to update all changed attendance records?'),
			function() {
				frm.call({
					method: 'bulk_update',
					doc: frm.doc,
					args: {
						docname: frm.doc.name
					},
					freeze: true,
					freeze_message: __('Updating attendance records...'),
					callback: function(r) {
						if (r.message) {
							frappe.show_alert({
								message: r.message.message || __('Bulk update completed'), 
								indicator: 'green'
							});
						}
						// Reload to show the updated data
						frm.reload_doc();
					},
					error: function(r) {
						frappe.show_alert({
							message: __('Error updating records. Please check console for details.'), 
							indicator: 'red'
						});
					}
				});
			}
		);
	},

	add_missing_data_styling: function(frm) {
		// Add CSS for highlighting missing data rows in pink
		if (!$('#bulk-attendance-missing-data-styles').length) {
			$('<style id="bulk-attendance-missing-data-styles">')
				.html(`
					.bulk-attendance-missing-data {
						background-color: #ffe6e6 !important;
					}
					.bulk-attendance-status-present {
						background-color: #e6ffe6 !important;
					}
					.bulk-attendance-status-error {
						background-color: #fff4e6 !important;
					}
				`)
				.appendTo('head');
		}

		// Apply styling after a short delay to ensure grid is loaded
		setTimeout(function() {
			frm.trigger('apply_row_styling');
		}, 500);
	},

	apply_row_styling: function(frm) {
		// Apply styling to rows based on status
		if (frm.fields_dict.attendance_data && frm.fields_dict.attendance_data.grid) {
			const grid_rows = frm.fields_dict.attendance_data.grid.grid_rows;

			grid_rows.forEach(function(row) {
				if (row.doc) {
					const status = row.doc.status;
					const row_element = $(row.wrapper);

					// Remove existing styling classes
					row_element.removeClass('bulk-attendance-missing-data bulk-attendance-status-present bulk-attendance-status-error');

					// Apply new styling based on status
					if (status === 'Present') {
						row_element.addClass('bulk-attendance-status-present');
					} else if (status === 'Error') {
						row_element.addClass('bulk-attendance-status-error');
					} else if (status === 'Absent') {
						row_element.addClass('bulk-attendance-missing-data');
					}
				}
			});
		}
	},

	setup_filters: function(frm) {
		// Add filter buttons for common use cases
		if (frm.doc.attendance_data && frm.doc.attendance_data.length > 0) {
			frm.page.add_menu_item(__('Show Only Missing Data'), function() {
				frm.trigger('filter_missing_data');
			});

			frm.page.add_menu_item(__('Show Only Present'), function() {
				frm.trigger('filter_present');
			});

			frm.page.add_menu_item(__('Show Only Errors'), function() {
				frm.trigger('filter_errors');
			});

			frm.page.add_menu_item(__('Clear Filters'), function() {
				frm.trigger('clear_filters');
			});
		}
	},

	filter_missing_data: function(frm) {
		frm.trigger('apply_filter', {field: 'status', value: 'Absent'});
	},

	filter_present: function(frm) {
		frm.trigger('apply_filter', {field: 'status', value: 'Present'});
	},

	filter_errors: function(frm) {
		frm.trigger('apply_filter', {field: 'status', value: 'Error'});
	},

	clear_filters: function(frm) {
		// Clear the filters by showing all rows
		if (frm.fields_dict.attendance_data && frm.fields_dict.attendance_data.grid) {
			frm.fields_dict.attendance_data.grid.grid_rows.forEach(function(row) {
				if (row.wrapper) {
					$(row.wrapper).show();
				}
			});
			frm.trigger('apply_row_styling');
			frappe.show_alert({message: __('Filters cleared'), indicator: 'blue'});
		}
	},

	apply_filter: function(frm, args) {
		// Simple client-side filtering by hiding/showing rows
		if (frm.fields_dict.attendance_data && frm.fields_dict.attendance_data.grid) {
			const field = args.field;
			const value = args.value;
			let visible_count = 0;

			frm.fields_dict.attendance_data.grid.grid_rows.forEach(function(row) {
				if (row.doc && row.wrapper) {
					if (row.doc[field] === value) {
						$(row.wrapper).show();
						visible_count++;
					} else {
						$(row.wrapper).hide();
					}
				}
			});

			frm.trigger('apply_row_styling');
			frappe.show_alert({
				message: __('Showing {0} records with {1}: {2}', [visible_count, field, value]), 
				indicator: 'blue'
			});
		}
	}
});

// Child table events
frappe.ui.form.on('Bulk Attendance Item', {
	attendance_data_on_form_rendered: function(frm, cdt, cdn) {
		// Apply styling when grid is rendered
		setTimeout(function() {
			frm.trigger('apply_row_styling');
		}, 100);
	},

	status: function(frm, cdt, cdn) {
		// Reapply styling when status changes
		setTimeout(function() {
			frm.trigger('apply_row_styling');
		}, 100);
	},

	check_in_date: function(frm, cdt, cdn) {
		frm.trigger('update_datetime_fields', cdt, cdn);
	},

	check_in_time: function(frm, cdt, cdn) {
		frm.trigger('update_datetime_fields', cdt, cdn);
	},

	check_out_date: function(frm, cdt, cdn) {
		frm.trigger('update_datetime_fields', cdt, cdn);
	},

	check_out_time: function(frm, cdt, cdn) {
		frm.trigger('update_datetime_fields', cdt, cdn);
	},

	update_datetime_fields: function(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		// Update status based on current values
		const has_checkin = row.check_in_date && row.check_in_time;
		const has_checkout = row.check_out_date && row.check_out_time;

		let new_status = 'Absent';
		if (has_checkin && has_checkout) {
			new_status = 'Present';
		} else if (has_checkin || has_checkout) {
			new_status = 'Error';
		}

		// Only update status if it changed
		if (row.status !== new_status) {
			frappe.model.set_value(cdt, cdn, 'status', new_status);
		}

		// Reapply styling after a short delay
		setTimeout(function() {
			frm.trigger('apply_row_styling');
		}, 100);
	}
});

function process_uploaded_file(file_url) {
    
    
    frappe.call({
        method: 'spotledger_hr.controllers.attendance_controller.sync_attendance',
        args: {
            'attendance_db_path': file_url
        },
        freeze: true,
		freeze_message: __('Processing attendance records...'),

        callback: (r) => {
            if (r.message) {
                frappe.show_alert({
                    message: __('Attendance synced successfully'),
                    indicator: 'green'
                });
            }
        }
    });
}