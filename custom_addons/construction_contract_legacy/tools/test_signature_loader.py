#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test script to verify signature loader service
Run this from Odoo shell: odoo-bin shell -d your_database -c your_config.conf
Then: exec(open('tools/test_signature_loader.py').read())
"""

import logging
import base64

_logger = logging.getLogger(__name__)

def test_signature_loader():
    """Test the signature loader service"""
    print("\n" + "="*60)
    print("Testing Signature Loader Service")
    print("="*60 + "\n")
    
    # Get the service
    try:
        signature_loader = env['construction.contract.signature.loader']
        print("✓ Signature loader service found")
    except Exception as e:
        print(f"✗ Failed to get signature loader service: {e}")
        return False
    
    # Test 1: Load company signature
    print("\n--- Test 1: Load Company Signature ---")
    try:
        company_sig = signature_loader.load_company_signature()
        print(f"✓ Company signature loaded successfully")
        print(f"  - Signer name: {company_sig.get('signer_name')}")
        print(f"  - Image data length: {len(company_sig.get('image_data', ''))} chars")
        print(f"  - Image data preview: {company_sig.get('image_data', '')[:50]}...")
    except Exception as e:
        print(f"✗ Failed to load company signature: {e}")
        return False
    
    # Test 2: Validate signature image
    print("\n--- Test 2: Validate Signature Image ---")
    try:
        # Create a small test PNG image (1x1 pixel)
        test_png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        )
        is_valid = signature_loader.validate_signature_image(test_png)
        print(f"✓ Signature validation works: {is_valid}")
    except Exception as e:
        print(f"✗ Failed to validate signature: {e}")
        return False
    
    # Test 3: Test with invalid data
    print("\n--- Test 3: Validate Invalid Signature ---")
    try:
        is_valid = signature_loader.validate_signature_image(b'invalid data')
        print(f"✓ Invalid signature correctly rejected: {not is_valid}")
    except Exception as e:
        print(f"✗ Validation error handling failed: {e}")
        return False
    
    print("\n" + "="*60)
    print("All tests passed! ✓")
    print("="*60 + "\n")
    return True

# Run the test
if __name__ == '__main__':
    test_signature_loader()
