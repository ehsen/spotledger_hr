#!/usr/bin/env python3
# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Test runner for Attendance Rule Engine and Controller tests
"""

import sys
import os
import unittest
import frappe
from frappe.tests.utils import FrappeTestCase

# Add the app path to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_attendance_tests():
    """Run all attendance-related tests"""
    
    # Test modules to run
    test_modules = [
        'spotledger_hr.tests.test_attendance_rule_engine',
        'spotledger_hr.tests.test_attendance_controller'
    ]
    
    # Test classes to run
    test_classes = [
        'TestAttendanceRuleEngine',
        'TestGracePeriodLogic', 
        'TestBreakCalculations',
        'TestOvertimeCalculations',
        'TestDeficiencyCalculations',
        'TestFridayLogic',
        'TestOvernightShifts',
        'TestCompleteAttendanceCalculations',
        'TestEdgeCases',
        'TestAttendanceController',
        'TestAttendanceControllerAPI',
        'TestAttendanceControllerIntegration'
    ]
    
    # Create test suite
    suite = unittest.TestSuite()
    
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            for class_name in test_classes:
                if hasattr(module, class_name):
                    test_class = getattr(module, class_name)
                    suite.addTest(unittest.makeSuite(test_class))
        except ImportError as e:
            print(f"Warning: Could not import {module_name}: {e}")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_specific_test_class(test_class_name):
    """Run a specific test class"""
    test_modules = [
        'spotledger_hr.tests.test_attendance_rule_engine',
        'spotledger_hr.tests.test_attendance_controller'
    ]
    
    suite = unittest.TestSuite()
    
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            if hasattr(module, test_class_name):
                test_class = getattr(module, test_class_name)
                suite.addTest(unittest.makeSuite(test_class))
        except ImportError as e:
            print(f"Warning: Could not import {module_name}: {e}")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_specific_test_method(test_class_name, test_method_name):
    """Run a specific test method"""
    test_modules = [
        'spotledger_hr.tests.test_attendance_rule_engine',
        'spotledger_hr.tests.test_attendance_controller'
    ]
    
    suite = unittest.TestSuite()
    
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            if hasattr(module, test_class_name):
                test_class = getattr(module, test_class_name)
                suite.addTest(test_class(test_method_name))
        except ImportError as e:
            print(f"Warning: Could not import {module_name}: {e}")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Run all tests
        success = run_attendance_tests()
        sys.exit(0 if success else 1)
    
    elif len(sys.argv) == 2:
        # Run specific test class
        test_class = sys.argv[1]
        success = run_specific_test_class(test_class)
        sys.exit(0 if success else 1)
    
    elif len(sys.argv) == 3:
        # Run specific test method
        test_class = sys.argv[1]
        test_method = sys.argv[2]
        success = run_specific_test_method(test_class, test_method)
        sys.exit(0 if success else 1)
    
    else:
        print("Usage:")
        print("  python run_tests.py                    # Run all tests")
        print("  python run_tests.py TestClass          # Run specific test class")
        print("  python run_tests.py TestClass method   # Run specific test method")
        sys.exit(1)
