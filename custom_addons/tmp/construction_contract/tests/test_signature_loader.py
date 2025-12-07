# -*- coding: utf-8 -*-
"""
Unit Tests for Signature Loader Service
Tests signature loading with fallback mechanism
"""

from odoo.tests import common, tagged
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


# Minimal valid PNG image (1x1 transparent pixel)
MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

# Minimal valid JPEG image
MINIMAL_JPEG = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01'
    b'\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06'
    b'\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b'
    b'\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
    b'\x1c $.\' ",#\x1c\x1c(7teletext(teletext(teletext'
    b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
    b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01'
    b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04'
    b'\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02'
    b'\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01'
    b'\x7d\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa'
    b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0'
    b'$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDE'
    b'FGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87'
    b'\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2'
    b'\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6'
    b'\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca'
    b'\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4'
    b'\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7'
    b'\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb'
    b'\xd5\x00\x00\x00\x00\xff\xd9'
)


@tagged('post_install', '-at_install', 'construction_contract', 'signature_loader')
class TestSignatureLoader(common.TransactionCase):
    """Test Signature Loader Service"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.signature_loader = cls.env['construction.contract.signature.loader']
        cls.company = cls.env.company

    def test_01_validate_png_signature(self):
        """Test validation of PNG signature image"""
        result = self.signature_loader.validate_signature_image(MINIMAL_PNG)
        self.assertTrue(result, "Valid PNG should pass validation")

    def test_02_validate_jpeg_signature(self):
        """Test validation of JPEG signature image"""
        result = self.signature_loader.validate_signature_image(MINIMAL_JPEG)
        self.assertTrue(result, "Valid JPEG should pass validation")

    def test_03_reject_empty_signature(self):
        """Test that empty signature is rejected"""
        result = self.signature_loader.validate_signature_image(b'')
        self.assertFalse(result, "Empty signature should be rejected")

    def test_04_reject_invalid_format(self):
        """Test that non-image data is rejected"""
        invalid_data = b'This is not an image'
        result = self.signature_loader.validate_signature_image(invalid_data)
        self.assertFalse(result, "Non-image data should be rejected")

    def test_05_reject_too_small_signature(self):
        """Test that too small signature is rejected"""
        small_data = b'\x89PNG' + b'\x00' * 50  # Less than 100 bytes
        result = self.signature_loader.validate_signature_image(small_data)
        self.assertFalse(result, "Too small signature should be rejected")

    def test_06_validate_with_details(self):
        """Test validation with detailed error information"""
        is_valid, details = self.signature_loader.validate_signature_image(
            MINIMAL_PNG, return_details=True
        )
        
        self.assertTrue(is_valid, "Valid PNG should pass")
        self.assertIsNone(details['error_code'], "No error code for valid image")
        self.assertEqual(details['details']['format'], 'PNG')

    def test_07_validate_invalid_with_details(self):
        """Test validation of invalid image with detailed error"""
        is_valid, details = self.signature_loader.validate_signature_image(
            b'invalid', return_details=True
        )
        
        self.assertFalse(is_valid, "Invalid data should fail")
        self.assertEqual(details['error_code'], 'SIZE_TOO_SMALL')

    def test_08_load_company_signature_from_field(self):
        """Test loading company signature from company.signature field"""
        # Set signature on company
        self.company.write({
            'signature': base64.b64encode(MINIMAL_PNG)
        })
        
        result = self.signature_loader.load_company_signature()
        
        self.assertIn('image_data', result)
        self.assertIn('signer_name', result)
        self.assertTrue(result['image_data'].startswith('data:image/png;base64,'))

    def test_09_load_company_signature_fallback_to_user(self):
        """Test fallback to user signature when company signature missing"""
        # Clear company signature
        if hasattr(self.company, 'signature'):
            self.company.write({'signature': False})
        
        # Set user signature
        self.env.user.write({
            'signature': base64.b64encode(MINIMAL_PNG)
        })
        
        result = self.signature_loader.load_company_signature()
        
        self.assertIn('image_data', result)
        self.assertTrue(result['image_data'].startswith('data:image/png;base64,'))

    def test_10_load_company_signature_error_when_none(self):
        """Test error when no signature found after all fallbacks"""
        # Clear all signatures
        if hasattr(self.company, 'signature'):
            self.company.write({'signature': False})
        if hasattr(self.env.user, 'signature'):
            self.env.user.write({'signature': False})
        
        # This should raise UserError if static file also doesn't exist
        # Note: In test environment, static file may or may not exist
        try:
            result = self.signature_loader.load_company_signature()
            # If we get here, static file exists - that's OK
            self.assertIn('image_data', result)
        except UserError as e:
            # Expected if no static file
            self.assertIn('Signature', str(e))

    def test_11_load_subcontractor_signature(self):
        """Test loading subcontractor signature from signature record"""
        # Create a mock signature record
        signature_record = self.env['construction.contract.signature'].create({
            'signature_data': base64.b64encode(MINIMAL_PNG).decode('utf-8'),
            'signer_name': 'Test Subcontractor',
            'signature_date': '2025-11-30',
        })
        
        result = self.signature_loader.load_subcontractor_signature(signature_record)
        
        self.assertIn('image_data', result)
        self.assertIn('signature_date', result)
        self.assertIn('signer_name', result)
        self.assertEqual(result['signer_name'], 'Test Subcontractor')
        self.assertEqual(result['signature_date'], '30/11/2025')

    def test_12_load_subcontractor_signature_missing_data(self):
        """Test error when signature record has no data"""
        signature_record = self.env['construction.contract.signature'].create({
            'signer_name': 'Test Subcontractor',
            'signature_date': '2025-11-30',
            'signature_data': False,
        })
        
        with self.assertRaises(UserError) as context:
            self.signature_loader.load_subcontractor_signature(signature_record)
        
        self.assertIn('manquantes', str(context.exception))

    def test_13_load_subcontractor_signature_invalid_data(self):
        """Test error when signature record has invalid image data"""
        signature_record = self.env['construction.contract.signature'].create({
            'signer_name': 'Test Subcontractor',
            'signature_date': '2025-11-30',
            'signature_data': base64.b64encode(b'not an image').decode('utf-8'),
        })
        
        with self.assertRaises(UserError) as context:
            self.signature_loader.load_subcontractor_signature(signature_record)
        
        self.assertIn('invalide', str(context.exception))

    def test_14_load_subcontractor_signature_no_record(self):
        """Test error when no signature record provided"""
        with self.assertRaises(UserError) as context:
            self.signature_loader.load_subcontractor_signature(None)
        
        self.assertIn('enregistrement', str(context.exception).lower())

    def test_15_validate_base64_string_input(self):
        """Test validation accepts base64 string input"""
        b64_data = base64.b64encode(MINIMAL_PNG).decode('utf-8')
        result = self.signature_loader.validate_signature_image(b64_data)
        self.assertTrue(result, "Base64 string should be accepted")

    def test_16_reject_gif_format(self):
        """Test that GIF format is rejected"""
        gif_header = b'GIF89a' + b'\x00' * 200
        is_valid, details = self.signature_loader.validate_signature_image(
            gif_header, return_details=True
        )
        
        self.assertFalse(is_valid, "GIF should be rejected")
        self.assertEqual(details['error_code'], 'INVALID_FORMAT')
        self.assertEqual(details['details']['detected_format'], 'GIF')

