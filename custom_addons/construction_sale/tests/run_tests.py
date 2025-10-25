#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test runner for construction_sale module
Allows running tests individually or all together with detailed logs
"""

import unittest
import sys
import os
import argparse

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_single_test(module_name):
    """Run a single test module with detailed output"""
    print(f"\n{'='*60}")
    print(f"RUNNING: {module_name.upper()}")
    print(f"{'='*60}")
    
    try:
        # Import and run the test module
        module = __import__(module_name)
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(module)
        
        # Run with detailed output
        runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
        result = runner.run(suite)
        
        # Print detailed results
        print(f"\n{'='*40} RESULTS {'='*40}")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        
        if result.failures:
            print(f"\n{'='*20} FAILURES {'='*20}")
            for test, traceback in result.failures:
                print(f"\nFAILED: {test}")
                print(f"Traceback:\n{traceback}")
        
        if result.errors:
            print(f"\n{'='*20} ERRORS {'='*20}")
            for test, traceback in result.errors:
                print(f"\nERROR: {test}")
                print(f"Traceback:\n{traceback}")
        
        if not result.failures and not result.errors:
            print(f"\n✅ {module_name.upper()} - ALL TESTS PASSED!")
            return True
        else:
            print(f"\n❌ {module_name.upper()} - SOME TESTS FAILED!")
            return False
            
    except Exception as e:
        print(f"❌ ERROR loading {module_name}: {e}")
        return False

def run_all_tests():
    """Run all test modules"""
    print("=" * 60)
    print("CONSTRUCTION SALE - ALL UNIT TESTS")
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
    passed_modules = 0
    
    for module_name in test_modules:
        try:
            # Import and run the test module
            module = __import__(module_name)
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(module)
            
            # Run with minimal output for summary
            runner = unittest.TextTestRunner(verbosity=1, stream=open(os.devnull, 'w'))
            result = runner.run(suite)
            
            # Count results
            tests_run = result.testsRun
            failures = len(result.failures)
            errors = len(result.errors)
            
            total_tests += tests_run
            total_failures += failures
            total_errors += errors
            
            if not failures and not errors:
                passed_modules += 1
                print(f"✅ {module_name}: {tests_run} tests passed")
            else:
                print(f"❌ {module_name}: {tests_run} tests, {failures} failures, {errors} errors")
                
        except Exception as e:
            print(f"❌ ERROR loading {module_name}: {e}")
            total_errors += 1
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Modules passed: {passed_modules}/{len(test_modules)}")
    print(f"Total tests: {total_tests}")
    print(f"Total failures: {total_failures}")
    print(f"Total errors: {total_errors}")
    
    if total_failures == 0 and total_errors == 0:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("💥 SOME TESTS FAILED!")
        return 1

def list_tests():
    """List all available test modules"""
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
    
    print("Available test modules:")
    for i, module in enumerate(test_modules, 1):
        print(f"  {i}. {module}")
    
    print(f"\nUsage examples:")
    print(f"  python3 run_tests.py --all                    # Run all tests")
    print(f"  python3 run_tests.py --module test_sale_order # Run specific module")
    print(f"  python3 run_tests.py --list                   # List available modules")

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(description='Run construction_sale unit tests')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--module', type=str, help='Run specific test module')
    parser.add_argument('--list', action='store_true', help='List available test modules')
    
    args = parser.parse_args()
    
    if args.list:
        list_tests()
        return 0
    
    if args.all:
        return run_all_tests()
    
    if args.module:
        if not args.module.startswith('test_'):
            args.module = f'test_{args.module}'
        return 0 if run_single_test(args.module) else 1
    
    # Default: show help
    parser.print_help()
    return 0

if __name__ == '__main__':
    sys.exit(main())
