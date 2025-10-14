# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Test fixtures and data for attendance rule engine tests
"""

from datetime import datetime, date
from typing import Dict, List, Any


# Standard attendance rule configuration
STANDARD_ATTENDANCE_RULE = {
    "doctype": "Attendance Rule",
    "name": "Test Company",
    "company": "Test Company",
    "factory_start_time": "08:00:00",
    "factory_end_time": "17:00:00",
    "required_factory_hours": 8.5,
    "friday_start_time": "07:30:00",
    "friday_end_time": "13:00:00",
    "checkin_grace_minutes": 15,
    "checkin_max_grace_minutes": 15,
    "checkout_grace_minutes": 15,
    "checkout_max_grace_minutes": 15,
    "break_duration_minutes": 30,
    "regular_break_start": "12:30:00",
    "regular_break_end": "13:30:00",
    "friday_break_start": "13:30:00",
    "friday_break_end": "14:30:00",
    "gazetted_overtime_multiplier": 2.0,
    "force_hours_on_friday": False,
    "allow_negative_hours": False,
    "enable_friday_logic": True,
    "consider_check_out_next_day": True,
    "allow_absent_on_holiday": False,
    "ignore_break_in_overtime": False
}

# Test dates
TEST_DATES = {
    "regular_monday": "2024-01-15",  # Monday
    "regular_tuesday": "2024-01-16",  # Tuesday
    "regular_wednesday": "2024-01-17",  # Wednesday
    "regular_thursday": "2024-01-18",  # Thursday
    "friday": "2024-01-19",  # Friday
    "saturday": "2024-01-20",  # Saturday
    "sunday": "2024-01-21",  # Sunday
    "holiday": "2024-01-26",  # Republic Day (Friday)
}

# Grace period test scenarios
GRACE_PERIOD_SCENARIOS = [
    {
        "name": "checkin_within_grace",
        "check_in": "07:35:00",  # 5 minutes late, within 10 min grace
        "check_out": "16:00:00",
        "expected_adjusted_checkin": "07:30:00",  # Should be adjusted to factory time
        "description": "Check-in within grace period should be adjusted to factory time"
    },
    {
        "name": "checkin_between_grace_and_max",
        "check_in": "07:50:00",  # 20 minutes late, between grace and max
        "check_out": "16:00:00",
        "expected_adjusted_checkin": "08:00:00",  # Should be adjusted to max grace time
        "description": "Check-in between grace and max grace should be adjusted to max grace time"
    },
    {
        "name": "checkin_beyond_max_grace",
        "check_in": "08:15:00",  # 45 minutes late, beyond max grace
        "check_out": "16:00:00",
        "expected_adjusted_checkin": "08:15:00",  # Should remain actual time
        "description": "Check-in beyond max grace should remain actual time"
    },
    {
        "name": "checkout_within_grace",
        "check_in": "07:30:00",
        "check_out": "15:58:00",  # 2 minutes early, within 5 min grace
        "expected_adjusted_checkout": "16:00:00",  # Should be adjusted to factory time
        "description": "Check-out within grace period should be adjusted to factory time"
    },
    {
        "name": "checkout_between_grace_and_max",
        "check_in": "07:30:00",
        "check_out": "15:50:00",  # 10 minutes early, between grace and max
        "expected_adjusted_checkout": "15:40:00",  # Should be adjusted to max grace time
        "description": "Check-out between grace and max grace should be adjusted to max grace time"
    },
    {
        "name": "checkout_beyond_max_grace",
        "check_in": "07:30:00",
        "check_out": "15:30:00",  # 30 minutes early, beyond max grace
        "expected_adjusted_checkout": "15:30:00",  # Should remain actual time
        "description": "Check-out beyond max grace should remain actual time"
    }
]

# Break calculation test scenarios
BREAK_CALCULATION_SCENARIOS = [
    {
        "name": "no_break_early_checkout",
        "check_in": "07:30:00",
        "check_out": "11:30:00",  # Before break start
        "expected_break_duration": 0,
        "description": "Check-out before break start should have no break deduction"
    },
    {
        "name": "no_break_late_checkin",
        "check_in": "12:15:00",  # After break start
        "check_out": "16:00:00",
        "expected_break_duration": 0,
        "description": "Check-in after break start should have no break deduction"
    },
    {
        "name": "full_break_deduction",
        "check_in": "07:30:00",
        "check_out": "16:00:00",  # After break end
        "expected_break_duration": 30,  # 30 minutes in seconds
        "description": "Check-out after break end should have full break deduction"
    },
    {
        "name": "friday_no_break_early_checkout",
        "check_in": "07:30:00",
        "check_out": "12:00:00",  # Before Friday break start
        "date": "friday",
        "expected_break_duration": 0,
        "description": "Friday check-out before break start should have no break deduction"
    },
    {
        "name": "friday_full_break_deduction",
        "check_in": "07:30:00",
        "check_out": "16:00:00",  # After Friday break end
        "date": "friday",
        "expected_break_duration": 90,  # 90 minutes in seconds
        "description": "Friday check-out after break end should have full break deduction"
    }
]

# Overtime calculation test scenarios
OVERTIME_SCENARIOS = [
    {
        "name": "no_overtime_regular_day",
        "check_in": "07:30:00",
        "check_out": "16:00:00",  # Exactly 8.5 hours
        "expected_overtime": 0,
        "description": "Regular day with exact required hours should have no overtime"
    },
    {
        "name": "regular_overtime",
        "check_in": "07:30:00",
        "check_out": "17:00:00",  # 9.5 hours total
        "expected_overtime": 1.0,  # 9.5 - 8.5 = 1 hour
        "description": "Regular day with extra hours should calculate overtime"
    },
    {
        "name": "friday_overtime_with_break",
        "check_in": "08:00:00",  # Friday start time
        "check_out": "16:00:00",  # 8 hours total (1 hour overtime from Friday 7 hours)
        "date": "friday",
        "expected_overtime": 1.0,  # 8 - 7 (Friday hours) = 1 hour overtime
        "description": "Friday overtime should use Friday-specific hours"
    },
    {
        "name": "friday_overtime_ignore_break",
        "check_in": "07:30:00",
        "check_out": "17:00:00",  # 9.5 hours total
        "date": "friday",
        "ignore_break_in_overtime": True,
        "expected_overtime": 1.0,  # 9.5 - 8.5 = 1 hour (break ignored)
        "description": "Friday overtime with break ignored should not deduct break"
    },
    {
        "name": "gazetted_holiday_overtime",
        "check_in": "07:30:00",
        "check_out": "16:00:00",  # 8.5 hours
        "date": "holiday",
        "expected_overtime": 17.0,  # 8.5 * 2.0 multiplier
        "description": "Gazetted holiday should apply multiplier to all hours"
    }
]

# Deficiency calculation test scenarios
DEFICIENCY_SCENARIOS = [
    {
        "name": "no_deficiency_regular_day",
        "check_in": "07:30:00",
        "check_out": "16:00:00",  # Exactly 8.5 hours
        "expected_deficiency": 0,
        "description": "Regular day with exact required hours should have no deficiency"
    },
    {
        "name": "regular_deficiency",
        "check_in": "07:30:00",
        "check_out": "15:30:00",  # 8 hours total
        "expected_deficiency": 0.5,  # 8.5 - 8 = 0.5 hours
        "description": "Regular day with less than required hours should calculate deficiency"
    },
    {
        "name": "friday_deficiency_force_hours",
        "check_in": "08:00:00",  # Friday start time
        "check_out": "14:00:00",  # 6 hours total (1 hour deficiency from Friday 7 hours)
        "date": "friday",
        "expected_deficiency": 1.0,  # 7 - 6 = 1 hour deficiency
        "description": "Friday with force hours should calculate deficiency using Friday hours"
    },
    {
        "name": "deficiency_with_negative_hours_disabled",
        "check_in": "07:30:00",
        "check_out": "15:30:00",  # 8 hours total
        "allow_negative_hours": False,
        "expected_deficiency": 0.5,  # Should still calculate deficiency
        "description": "Deficiency should be calculated even when negative hours disabled"
    },
    {
        "name": "gazetted_holiday_no_deficiency",
        "check_in": "07:30:00",
        "check_out": "15:30:00",  # 8 hours total
        "date": "holiday",
        "expected_deficiency": 0,
        "description": "Gazetted holiday should have no deficiency"
    }
]

# Friday special logic test scenarios
FRIDAY_LOGIC_SCENARIOS = [
    {
        "name": "friday_prayer_break_checkout_before",
        "check_in": "07:30:00",
        "check_out": "12:00:00",  # Before Friday prayer break
        "date": "friday",
        "expected_adjusted_checkout": "12:00:00",
        "description": "Friday checkout before prayer break should remain actual time"
    },
    {
        "name": "friday_prayer_break_checkout_during",
        "check_in": "07:30:00",
        "check_out": "13:00:00",  # During Friday prayer break
        "date": "friday",
        "expected_adjusted_checkout": "16:00:00",  # Should be adjusted to factory end time
        "description": "Friday checkout during prayer break should be adjusted to factory end time"
    },
    {
        "name": "friday_prayer_break_checkout_after",
        "check_in": "07:30:00",
        "check_out": "15:00:00",  # After Friday prayer break
        "date": "friday",
        "expected_adjusted_checkout": "15:00:00",
        "description": "Friday checkout after prayer break should remain actual time"
    }
]

# Overnight shift test scenarios
OVERNIGHT_SHIFT_SCENARIOS = [
    {
        "name": "normal_shift",
        "check_in": "07:30:00",
        "check_out": "16:00:00",
        "expected_adjusted_checkin": "07:30:00",
        "expected_adjusted_checkout": "16:00:00",
        "description": "Normal shift should not be adjusted"
    },
    {
        "name": "overnight_shift",
        "check_in": "22:00:00",
        "check_out": "06:00:00",  # Next day
        "expected_adjusted_checkin": "22:00:00",
        "expected_adjusted_checkout": "2024-01-16 06:00:00",  # Next day
        "description": "Overnight shift should adjust checkout to next day"
    }
]

# Complete attendance calculation test scenarios
COMPLETE_ATTENDANCE_SCENARIOS = [
    {
        "name": "perfect_attendance_regular_day",
        "check_in": "07:30:00",
        "check_out": "16:00:00",
        "date": "regular_monday",
        "expected": {
            "total_hours": 8.5,
            "regular_hours": 8.0,  # 8.5 - 0.5 (break)
            "overtime_hours": 0,
            "deficiency_hours": 0,
            "is_friday": False,
            "is_gazetted_holiday": False
        },
        "description": "Perfect attendance on regular day"
    },
    {
        "name": "perfect_attendance_friday",
        "check_in": "08:00:00",  # Friday start time
        "check_out": "15:00:00",  # Friday end time
        "date": "friday",
        "expected": {
            "total_hours": 7.0,  # 15:00 - 08:00 = 7 hours
            "regular_hours": 7.0,  # Friday hours (7 hours)
            "overtime_hours": 0,
            "deficiency_hours": 0,
            "is_friday": True,
            "is_gazetted_holiday": False
        },
        "description": "Perfect attendance on Friday with Friday-specific times"
    },
    {
        "name": "overtime_attendance_regular_day",
        "check_in": "07:30:00",
        "check_out": "17:30:00",  # 10 hours total
        "date": "regular_monday",
        "expected": {
            "total_hours": 10.0,
            "regular_hours": 8.0,  # 8.5 - 0.5 (break)
            "overtime_hours": 1.5,  # 10 - 8.5 = 1.5
            "deficiency_hours": 0,
            "is_friday": False,
            "is_gazetted_holiday": False
        },
        "description": "Overtime attendance on regular day"
    },
    {
        "name": "deficiency_attendance_regular_day",
        "check_in": "07:30:00",
        "check_out": "15:00:00",  # 7.5 hours total
        "date": "regular_monday",
        "expected": {
            "total_hours": 7.5,
            "regular_hours": 7.0,  # 7.5 - 0.5 (break)
            "overtime_hours": 0,
            "deficiency_hours": 1.0,  # 8.5 - 7.5 = 1.0
            "is_friday": False,
            "is_gazetted_holiday": False
        },
        "description": "Deficiency attendance on regular day"
    },
    {
        "name": "gazetted_holiday_attendance",
        "check_in": "07:30:00",
        "check_out": "16:00:00",  # 8.5 hours total
        "date": "holiday",
        "expected": {
            "total_hours": 8.5,
            "regular_hours": 8.5,
            "overtime_hours": 17.0,  # 8.5 * 2.0 multiplier
            "deficiency_hours": 0,
            "is_friday": True,  # Holiday is Friday
            "is_gazetted_holiday": True
        },
        "description": "Attendance on gazetted holiday"
    }
]

# Edge case test scenarios
EDGE_CASE_SCENARIOS = [
    {
        "name": "zero_hours_attendance",
        "check_in": "07:30:00",
        "check_out": "07:30:00",  # Same time
        "expected": {
            "total_hours": 0,
            "regular_hours": 0,
            "overtime_hours": 0,
            "deficiency_hours": 8.5,  # Full deficiency
        },
        "description": "Zero hours attendance should show full deficiency"
    },
    {
        "name": "very_long_shift",
        "check_in": "07:30:00",
        "check_out": "23:30:00",  # 16 hours
        "expected": {
            "total_hours": 16.0,
            "regular_hours": 8.0,  # Capped at required hours minus break
            "overtime_hours": 7.5,  # 16 - 8.5 = 7.5
            "deficiency_hours": 0,
        },
        "description": "Very long shift should calculate appropriate overtime"
    },
    {
        "name": "late_checkin_early_checkout",
        "check_in": "10:00:00",  # 2.5 hours late
        "check_out": "14:00:00",  # 2 hours early
        "expected": {
            "total_hours": 4.0,
            "regular_hours": 4.0,  # No break deduction (late checkin)
            "overtime_hours": 0,
            "deficiency_hours": 4.5,  # 8.5 - 4 = 4.5
        },
        "description": "Late checkin and early checkout scenario"
    }
]

# Test employee data
TEST_EMPLOYEES = [
    {
        "employee_number": "TEST-EMP-001",
        "employee_name": "Test Employee 1",
        "first_name": "Test",
        "last_name": "Employee 1",
        "company": "Test Company",
        "custom_attendance_rule": "Test Company",
        "gender": "Male",
        "date_of_birth": "1990-01-01",
        "date_of_joining": "2020-01-01",
        "status": "Active",
        "naming_series": "EMP-TEST-.#####"
    },
    {
        "employee_number": "TEST-EMP-002",
        "employee_name": "Test Employee 2",
        "first_name": "Test",
        "last_name": "Employee 2",
        "company": "Test Company",
        "custom_attendance_rule": "Test Company",
        "gender": "Female",
        "date_of_birth": "1991-01-01",
        "date_of_joining": "2020-01-01",
        "status": "Active",
        "naming_series": "EMP-TEST-.#####"
    }
]

# Holiday list for testing
TEST_HOLIDAY_LIST = {
    "doctype": "Holiday List",
    "holiday_list_name": "Test Holiday List",
    "from_date": "2024-01-01",
    "to_date": "2024-12-31",
    "holidays": [
        {
            "holiday_date": "2024-01-26",
            "description": "Republic Day"
        }
    ]
}
