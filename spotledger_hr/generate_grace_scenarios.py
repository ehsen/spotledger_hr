#!/usr/bin/env python3
"""
Generate HTML demo for grace period scenarios
"""
import frappe
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine

def generate_scenarios():
    frappe.init(site='bfi')
    frappe.connect()
    
    test_employee = "128"
    
    # Regular day scenarios (Monday)
    regular_date = "2024-01-15"  # Monday
    
    regular_scenarios = [
        (regular_date, "08:00:00", "17:00:00", "Perfect Attendance", 
         "Employee arrives exactly on time and leaves exactly on time"),
        
        (regular_date, "08:10:00", "17:10:00", "10 Min Late & Overtime (Within Grace)", 
         "Late by 10 min and stayed 10 min extra - both within 15 min grace period, adjusted to factory times (no penalty)"),
        
        (regular_date, "08:15:00", "17:15:00", "15 Min Late & Overtime (At Grace Limit)", 
         "Late by 15 min and stayed 15 min extra - exactly at grace limit, adjusted to factory times (no penalty)"),
        
        (regular_date, "08:20:00", "17:20:00", "⭐ 20 Min Late & Overtime (CAPPED)", 
         "Late by 20 min and stayed 20 min extra - beyond 15 min grace but within 30 min max, CAPPED at 08:30-17:30 (limited penalty)"),
        
        (regular_date, "08:25:00", "17:25:00", "⭐ 25 Min Late & Overtime (CAPPED)", 
         "Late by 25 min and stayed 25 min extra - beyond grace, within max, CAPPED at 08:30-17:30"),
        
        (regular_date, "08:30:00", "17:30:00", "30 Min Late & Overtime (At Max Grace)", 
         "Late by 30 min and stayed 30 min extra - at max grace limit of 30 min"),
        
        (regular_date, "08:45:00", "17:45:00", "45 Min Late & Overtime (Beyond Max)", 
         "Late by 45 min and stayed 45 min extra - beyond max grace, actual times used (full penalty)"),
        
        (regular_date, "09:00:00", "18:00:00", "1 Hour Late & Overtime (Way Beyond)", 
         "Late by 1 hour and stayed 1 hour extra - way beyond max grace, full penalty applies"),
        
        (regular_date, "08:00:00", "16:30:00", "Left 30 Minutes Early", 
         "Perfect check-in but left 30 minutes early - deficiency calculated"),
        
        (regular_date, "08:00:00", "17:20:00", "⭐ 20 Min Overtime Only (CAPPED)", 
         "Perfect check-in, stayed 20 min extra - capped at 17:30 for overtime calculation"),
        
        (regular_date, "08:20:00", "17:00:00", "⭐ 20 Min Late Only (CAPPED)", 
         "Late by 20 min, perfect checkout - capped at 08:30 for deficiency calculation"),
    ]
    
    # Friday scenarios
    friday_date = "2024-01-19"  # Friday
    
    friday_scenarios = [
        (friday_date, "07:30:00", "13:30:00", "Friday Perfect Attendance", 
         "Friday: 7:30-13:30 (6 hrs). Break starts at 13:30, so NO break deduction - employee leaves before break"),
        
        (friday_date, "07:40:00", "13:40:00", "Friday 10 Min Late & Extra (Within Grace)", 
         "Friday: 10 min late and stayed 10 min into break time - both adjusted to 7:30-13:30 (no penalty)"),
        
        (friday_date, "07:50:00", "13:50:00", "⭐ Friday 20 Min Late & Extra (CAPPED)", 
         "Friday: 20 min late, stayed 20 min into break - capped at 8:00-14:00"),
        
        (friday_date, "08:00:00", "14:00:00", "Friday 30 Min Late & Extra (At Max)", 
         "Friday: 30 min late, stayed 30 min into break - at max grace (8:00-14:00)"),
    ]
    
    scenarios = regular_scenarios + friday_scenarios
    
    html_scenarios = []
    for date, check_in, check_out, title, description in scenarios:
        engine = AttendanceRuleEngine(test_employee, date)
        summary = engine.calculate_attendance_summary(check_in, check_out)
        
        # Add day label
        day_label = "Friday" if date == friday_date else "Monday"
        
        html_scenarios.append({
            'day': day_label,
            'title': title,
            'description': description,
            'check_in': check_in,
            'check_out': check_out,
            'adjusted_check_in': str(summary['adjusted_check_in']),
            'adjusted_check_out': str(summary['adjusted_check_out']),
            'regular_hours': summary['regular_hours'],
            'overtime': summary['overtime_hours'],
            'deficiency': summary['deficiency_hours'],
            'total_hours': summary['total_hours'],
            'break_minutes': summary['break_duration_minutes'],
            'is_friday': summary.get('is_friday', False)
        })
    
    # Generate HTML
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attendance Grace Period Scenarios - BFI</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 20px;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-bottom: 40px;
            text-align: center;
        }
        
        .header h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 20px;
        }
        
        .rules-info {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin-top: 30px;
            text-align: left;
        }
        
        .rules-info h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        
        .rules-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .rule-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        
        .rule-card h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        
        .rule-card ul {
            list-style: none;
            padding-left: 0;
        }
        
        .rule-card li {
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }
        
        .rule-card li:last-child {
            border-bottom: none;
        }
        
        .rule-card .value {
            color: #667eea;
            font-weight: 600;
        }
        
        .scenarios-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
        }
        
        .scenario-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .scenario-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }
        
        .scenario-title {
            color: #667eea;
            font-size: 1.5em;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 3px solid #667eea;
        }
        
        .scenario-description {
            color: #666;
            margin-bottom: 25px;
            line-height: 1.6;
            font-size: 0.95em;
        }
        
        .time-section {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .time-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .time-row:last-child {
            margin-bottom: 0;
        }
        
        .time-label {
            color: #666;
            font-size: 0.9em;
        }
        
        .time-value {
            font-weight: 600;
            color: #333;
            font-size: 1.1em;
        }
        
        .time-actual {
            color: #e74c3c;
        }
        
        .time-adjusted {
            color: #27ae60;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }
        
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
        }
        
        .metric-label {
            font-size: 0.85em;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: bold;
        }
        
        .metric-unit {
            font-size: 0.7em;
            opacity: 0.8;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            margin-top: 15px;
        }
        
        .status-perfect {
            background: #d4edda;
            color: #155724;
        }
        
        .status-warning {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-deficient {
            background: #f8d7da;
            color: #721c24;
        }
        
        .footer {
            background: white;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-top: 40px;
            text-align: center;
            color: #666;
        }
        
        @media (max-width: 768px) {
            .scenarios-grid {
                grid-template-columns: 1fr;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .rules-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🕐 Attendance Grace Period Scenarios</h1>
            <p style="color: #666; font-size: 1.1em; margin-top: 15px;">
                Understanding how check-in and check-out grace periods affect attendance calculations<br>
                <strong>Including Regular Days (Monday) and Friday (Half-Day) Scenarios</strong>
            </p>
            
            <div class="rules-info">
                <h2>📋 Attendance Rule Configuration (Regular Profile)</h2>
                <div class="rules-grid">
                    <div class="rule-card">
                        <h3>⏰ Factory Timings</h3>
                        <ul>
                            <li><strong>Regular Day:</strong></li>
                            <li>Start: <span class="value">08:00</span> | End: <span class="value">17:00</span></li>
                            <li>Required: <span class="value">8.5 hrs (net)</span></li>
                            <li>Break: <span class="value">12:30-13:00 (30 min)</span></li>
                            <li style="margin-top: 10px;"><strong>Friday:</strong></li>
                            <li>Start: <span class="value">07:30</span> | End: <span class="value">13:30</span></li>
                            <li>Required: <span class="value">6.0 hrs (no break)</span></li>
                            <li>Note: <span class="value">Break at 13:30, after work ends</span></li>
                        </ul>
                    </div>
                    
                    <div class="rule-card">
                        <h3>🚪 Check-In Grace Rules</h3>
                        <ul>
                            <li>Grace Period: <span class="value">15 min</span></li>
                            <li>Max Grace Cap: <span class="value">30 min</span></li>
                            <li>≤15 min late: <span class="value">Forgiven (08:00)</span></li>
                            <li>16-30 min late: <span class="value">Capped (08:30)</span></li>
                            <li>>30 min late: <span class="value">Full penalty</span></li>
                        </ul>
                    </div>
                    
                    <div class="rule-card">
                        <h3>🏃 Check-Out Grace Rules</h3>
                        <ul>
                            <li>Grace Period: <span class="value">15 min</span></li>
                            <li>Max Grace Cap: <span class="value">30 min</span></li>
                            <li>≤15 min extra: <span class="value">Adjusted to 17:00</span></li>
                            <li>16-30 min extra: <span class="value">Capped (17:30)</span></li>
                            <li>>30 min extra: <span class="value">Full time used</span></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="scenarios-grid">
"""
    
    for scenario in html_scenarios:
        # Determine status
        if scenario['deficiency'] > 0:
            status_class = 'status-deficient'
            status_text = f"⚠️ Deficient ({scenario['deficiency']:.2f} hrs)"
        elif scenario['overtime'] > 0:
            status_class = 'status-warning'
            status_text = f"⏱️ Overtime ({scenario['overtime']:.2f} hrs)"
        else:
            status_class = 'status-perfect'
            status_text = "✅ Perfect Attendance"
        
        day_badge = f'<span style="background: {"#3498db" if scenario["is_friday"] else "#2ecc71"}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8em; font-weight: 600;">{scenario["day"]}</span>'
        
        html += f"""
            <div class="scenario-card">
                <div style="margin-bottom: 10px;">{day_badge}</div>
                <h2 class="scenario-title">{scenario['title']}</h2>
                <p class="scenario-description">{scenario['description']}</p>
                
                <div class="time-section">
                    <div class="time-row">
                        <span class="time-label">Actual Check-In:</span>
                        <span class="time-value time-actual">{scenario['check_in']}</span>
                    </div>
                    <div class="time-row">
                        <span class="time-label">Adjusted Check-In:</span>
                        <span class="time-value time-adjusted">{scenario['adjusted_check_in'].split()[1]}</span>
                    </div>
                    <div class="time-row">
                        <span class="time-label">Actual Check-Out:</span>
                        <span class="time-value time-actual">{scenario['check_out']}</span>
                    </div>
                    <div class="time-row">
                        <span class="time-label">Adjusted Check-Out:</span>
                        <span class="time-value time-adjusted">{scenario['adjusted_check_out'].split()[1]}</span>
                    </div>
                </div>
                
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-label">Regular Hours</div>
                        <div class="metric-value">{scenario['regular_hours']:.1f} <span class="metric-unit">hrs</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Overtime</div>
                        <div class="metric-value">{scenario['overtime']:.1f} <span class="metric-unit">hrs</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Deficiency</div>
                        <div class="metric-value">{scenario['deficiency']:.1f} <span class="metric-unit">hrs</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Break Time</div>
                        <div class="metric-value">{scenario['break_minutes']} <span class="metric-unit">min</span></div>
                    </div>
                </div>
                
                <div style="text-align: center;">
                    <span class="{status_class} status-badge">{status_text}</span>
                </div>
            </div>
"""
    
    html += """
        </div>
        
        <div class="footer">
            <p><strong>📊 Summary of Grace Logic:</strong></p>
            <p style="margin-top: 15px; line-height: 1.8;">
                The grace period system has two tiers for both check-in and check-out:<br>
                <strong>Tier 1 (Forgiveness):</strong> 0-15 minutes → Adjusted to factory time (no penalty/overtime)<br>
                <strong>⭐ Tier 2 (CAPPED):</strong> 16-30 minutes → Capped at max grace (limited penalty/overtime)<br>
                <strong>Beyond Max:</strong> >30 minutes → Actual time used (full calculation applies)
            </p>
            <p style="margin-top: 20px; line-height: 1.8;">
                <strong>📅 Friday Special Logic:</strong><br>
                Friday has different timings (7:30-13:30, 6 hours). The Friday prayer break (13:30-14:30) starts AFTER factory end time,
                so NO break deduction applies on Friday. Required hours = 6.0 hours (gross = net).
                Grace periods still apply normally.
            </p>
            <p style="margin-top: 20px; color: #999; font-size: 0.9em;">
                Generated for BFI - Attendance Management System | Grace Period Demo
            </p>
        </div>
    </div>
</body>
</html>
"""
    
    with open('/home/frappe/frappe-bench/apps/spotledger_hr/attendance_grace_scenarios_demo.html', 'w') as f:
        f.write(html)
    
    print("✅ HTML demo generated successfully!")
    print("📁 Location: /home/frappe/frappe-bench/apps/spotledger_hr/attendance_grace_scenarios_demo.html")
    
    frappe.db.commit()
    frappe.destroy()

if __name__ == "__main__":
    generate_scenarios()

