#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple test runner for construction_sale module
Runs all unit tests without Odoo dependencies
"""

import unittest
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """Run all unit tests"""
    print("=" * 60)
    print("CONSTRUCTION SALE - UNIT TESTS")
    print("=" * 60)
    
    # Test modules to run
    test_modules = [
        'test_sale_order',
        'test_quote_wizard', 
        'test_product_creator',
        'test_product_dialog',
        'test_quote_line',
        'test_line_editor',
        'test_cancel_confirm',
        'test_product_template',
        'test_product_product'
    ]
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    
    for module_name in test_modules:
        print(f"\n{'='*20} {module_name.upper()} {'='*20}")
        
        try:
            # Import and run the test module
            module = __import__(module_name)
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(module)
            runner = unittest.TextTestRunner(verbosity=2, stream=open(os.devnull, 'w'))
            result = runner.run(suite)
            
            # Count results
            tests_run = result.testsRun
            failures = len(result.failures)
            errors = len(result.errors)
            
            total_tests += tests_run
            total_failures += failures
            total_errors += errors
            
            print(f"Tests run: {tests_run}")
            print(f"Failures: {failures}")
            print(f"Errors: {errors}")
            
            if failures > 0:
                print("FAILURES:")
                for test, traceback in result.failures:
                    error_msg = traceback.split('AssertionError: ')[-1].split('\n')[0]
                    print(f"  - {test}: {error_msg}")
            
            if errors > 0:
                print("ERRORS:")
                for test, traceback in result.errors:
                    error_msg = traceback.split('\n')[-2]
                    print(f"  - {test}: {error_msg}")
                    
        except Exception as e:
            print(f"ERROR loading {module_name}: {e}")
            total_errors += 1
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {total_tests}")
    print(f"Total failures: {total_failures}")
    print(f"Total errors: {total_errors}")
    
    if total_failures == 0 and total_errors == 0:
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        return 1

if __name__ == '__main__':
    sys.exit(run_tests())