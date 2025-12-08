# -*- coding: utf-8 -*-
"""
Contract Signature Model
Stores electronic signatures with full traceability for legal compliance
Records IP address, geolocation, user agent, and authentication method
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

# Import constants
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.contract_constants import AUTHENTICATION_METHODS, MAX_SIGNATURE_SIZE_MB


class ConstructionContractSignature(models.Model):
    """
    Electronic Signature Record

    Stores signature data with complete audit trail for legal compliance
    Includes IP address, geolocation, timestamp, and device information
    """

    _name = 'construction.contract.signature'
    _description = 'Contract Electronic Signature'
    _order = 'signature_date desc'

    # ============================================================
    # BASIC INFORMATION
    # ============================================================

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        index=True,
        help="Related contract"
    )

    signature_date = fields.Datetime(
        string='Signature Date',
        required=True,
        default=fields.Datetime.now,
        help="Exact timestamp of signature"
    )

    # ============================================================
    # SIGNATURE DATA
    # ============================================================

    signature_data = fields.Binary(
        string='Signature Image',
        required=True,
        attachment=True,
        help="Base64 encoded PNG/JPEG of handwritten signature"
    )

    signature_filename = fields.Char(
        compute='_compute_signature_filename',
        help="Generated filename for signature image"
    )

    # ============================================================
    # SIGNER INFORMATION
    # ============================================================

    signer_name = fields.Char(
        string='Signer Name',
        required=True,
        help="Full name of the person signing"
    )

    signer_email = fields.Char(
        string='Signer Email',
        required=True,
        help="Email address of signer"
    )

    signer_phone = fields.Char(
        string='Signer Phone',
        help="Phone number of signer"
    )

    signer_function = fields.Char(
        string='Signer Function',
        help="Job title/function of signer"
    )

    # ============================================================
    # TRACEABILITY (Legal Compliance)
    # ============================================================

    ip_address = fields.Char(
        string='IP Address',
        required=True,
        help="IPv4/IPv6 address of signing device"
    )

    geolocation = fields.Char(
        string='Geolocation',
        help="City and country determined from IP address"
    )

    user_agent = fields.Text(
        string='User Agent',
        help="Browser and OS information"
    )

    device_type = fields.Selection([
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
        ('unknown', 'Unknown'),
    ], string='Device Type', compute='_compute_device_type', store=True)

    # ============================================================
    # AUTHENTICATION
    # ============================================================

    authentication_method = fields.Selection(
        selection=AUTHENTICATION_METHODS,
        string='Authentication Method',
        default='email',
        required=True,
        help="Method used to authenticate the signer"
    )

    sms_code_verified = fields.Boolean(
        string='SMS Code Verified',
        default=False,
        help="True if SMS 2FA code was successfully verified"
    )

    access_token = fields.Char(
        string='Access Token Used',
        help="Portal access token used for signing"
    )

    # ============================================================
    # TIMESTAMPS (eIDAS Compliance)
    # ============================================================

    timestamp_token = fields.Char(
        string='Timestamp Token',
        help="Qualified timestamp token (eIDAS compliant)"
    )

    timestamp_provider = fields.Char(
        string='Timestamp Provider',
        help="Name of timestamp authority (e.g., Universign, Certinomis)"
    )

    # ============================================================
    # VALIDATION STATUS
    # ============================================================

    is_valid = fields.Boolean(
        string='Signature Valid',
        default=True,
        help="False if signature has been invalidated"
    )

    invalidation_reason = fields.Text(
        string='Invalidation Reason',
        help="Reason for signature invalidation (if applicable)"
    )

    invalidation_date = fields.Datetime(
        string='Invalidation Date',
        help="Date when signature was invalidated"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('contract_id', 'signature_date')
    def _compute_signature_filename(self):
        """Generate filename for signature image"""
        for signature in self:
            if signature.contract_id and signature.signature_date:
                date_str = signature.signature_date.strftime('%Y%m%d_%H%M%S')
                contract_ref = signature.contract_id.name.replace('/', '_')
                signature.signature_filename = f"signature_{contract_ref}_{date_str}.png"
            else:
                signature.signature_filename = 'signature.png'

    @api.depends('user_agent')
    def _compute_device_type(self):
        """Detect device type from user agent"""
        for signature in self:
            if not signature.user_agent:
                signature.device_type = 'unknown'
                continue

            ua = signature.user_agent.lower()

            if any(x in ua for x in ['mobile', 'android', 'iphone']):
                signature.device_type = 'mobile'
            elif any(x in ua for x in ['tablet', 'ipad']):
                signature.device_type = 'tablet'
            elif any(x in ua for x in ['windows', 'mac', 'linux']):
                signature.device_type = 'desktop'
            else:
                signature.device_type = 'unknown'

    # ============================================================
    # CONSTRAINTS
    # ============================================================

    @api.constrains('signature_data')
    def _check_signature_size(self):
        """Validate signature file size"""
        for signature in self:
            if signature.signature_data:
                import base64
                # Decode to check actual size
                try:
                    decoded = base64.b64decode(signature.signature_data)
                    size_mb = len(decoded) / (1024 * 1024)

                    if size_mb > MAX_SIGNATURE_SIZE_MB:
                        raise ValidationError(_(
                            "Signature image is too large (%.2f MB). "
                            "Maximum allowed: %d MB"
                        ) % (size_mb, MAX_SIGNATURE_SIZE_MB))
                except Exception as e:
                    _logger.warning(f"Could not validate signature size: {e}")

    # ============================================================
    # BUSINESS METHODS
    # ============================================================

    def action_invalidate(self):
        """
        Invalidate this signature
        Requires admin privileges
        """
        self.ensure_one()

        if not self.env.user.has_group('base.group_system'):
            raise ValidationError(_("Only administrators can invalidate signatures."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invalidate Signature'),
            'res_model': 'signature.invalidation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_signature_id': self.id},
        }

    def action_download_signature(self):
        """Download signature image"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/construction.contract.signature/{self.id}/signature_data/{self.signature_filename}?download=true',
            'target': 'new',
        }

    def _get_signature_details_for_certificate(self):
        """
        Get signature details formatted for certificate of completion

        Returns:
            dict: Formatted signature information
        """
        self.ensure_one()

        return {
            'signer': {
                'name': self.signer_name,
                'email': self.signer_email,
                'phone': self.signer_phone,
                'function': self.signer_function,
            },
            'technical': {
                'date': self.signature_date.strftime('%d/%m/%Y %H:%M:%S') if self.signature_date else '',
                'ip': self.ip_address,
                'geolocation': self.geolocation or 'N/A',
                'device': dict(self._fields['device_type'].selection).get(self.device_type, 'Unknown'),
                'user_agent': self.user_agent or 'N/A',
            },
            'authentication': {
                'method': dict(AUTHENTICATION_METHODS).get(self.authentication_method),
                'sms_verified': self.sms_code_verified,
            },
            'timestamp': {
                'provider': self.timestamp_provider or 'N/A',
                'token': self.timestamp_token or 'N/A',
            },
            'validity': {
                'is_valid': self.is_valid,
                'invalidation_reason': self.invalidation_reason,
                'invalidation_date': self.invalidation_date.strftime(
                    '%d/%m/%Y %H:%M:%S') if self.invalidation_date else None,
            }
        }
