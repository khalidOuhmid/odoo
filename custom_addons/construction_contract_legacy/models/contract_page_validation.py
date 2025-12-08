# -*- coding: utf-8 -*-
"""
Contract Page Validation Model
Tracks page-by-page validation in signature portal
Ensures complete document reading before signature (legal requirement)
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ConstructionContractPageValidation(models.Model):
    """
    Page Validation Record

    Tracks when each page of the contract PDF was validated by the signer
    Required for legal proof that document was fully read before signing
    """

    _name = 'construction.contract.page.validation'
    _description = 'Contract Page Validation'
    _order = 'page_number, validated_date'

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

    page_number = fields.Integer(
        string='Page Number',
        required=True,
        help="Page number that was validated (1-indexed)"
    )

    validated_date = fields.Datetime(
        string='Validation Date',
        required=True,
        default=fields.Datetime.now,
        help="Timestamp when page was validated"
    )

    # ============================================================
    # TRACEABILITY
    # ============================================================

    access_token = fields.Char(
        string='Access Token',
        required=True,
        index=True,
        help="Portal access token used for validation"
    )

    ip_address = fields.Char(
        string='IP Address',
        help="IP address from which validation occurred"
    )

    user_agent = fields.Text(
        string='User Agent',
        help="Browser/device information"
    )

    # ============================================================
    # READING METRICS
    # ============================================================

    time_spent = fields.Integer(
        string='Time Spent (seconds)',
        default=0,
        help="Number of seconds spent on this page before validation"
    )

    scroll_percentage = fields.Float(
        string='Scroll Percentage',
        default=0.0,
        help="Percentage of page scrolled (0-100)"
    )

    # ============================================================
    # VALIDATION METHOD
    # ============================================================

    validation_method = fields.Selection([
        ('button', 'Validation Button'),
        ('scroll', 'Auto-validate on Scroll'),
        ('timer', 'Auto-validate After Timer'),
    ], string='Validation Method', default='button', help="How the page was validated")

    # ============================================================
    # CONSTRAINTS
    # ============================================================

    @api.constrains('contract_id', 'page_number', 'access_token')
    def _check_unique_page_validation(self):
        """Prevent duplicate validation of same page with same token"""
        for validation in self:
            duplicates = self.search([
                ('contract_id', '=', validation.contract_id.id),
                ('page_number', '=', validation.page_number),
                ('access_token', '=', validation.access_token),
                ('id', '!=', validation.id),
            ])

            if duplicates:
                # This is OK - just log it
                _logger.info(
                    f"Page {validation.page_number} validated multiple times for contract {validation.contract_id.name}")

    @api.constrains('page_number')
    def _check_page_number_valid(self):
        """Ensure page number is within contract page count"""
        for validation in self:
            if validation.page_number < 1:
                raise ValidationError(_("Page number must be at least 1."))

            if validation.contract_id.pdf_page_count > 0:
                if validation.page_number > validation.contract_id.pdf_page_count:
                    raise ValidationError(_(
                        "Page number %d exceeds total pages (%d) in contract."
                    ) % (validation.page_number, validation.contract_id.pdf_page_count))

    @api.constrains('time_spent')
    def _check_time_spent_reasonable(self):
        """Log warning if time spent is suspiciously short"""
        MIN_READ_TIME = 5  # seconds

        for validation in self:
            if validation.time_spent < MIN_READ_TIME:
                _logger.warning(
                    f"Page {validation.page_number} of contract {validation.contract_id.name} "
                    f"validated after only {validation.time_spent} seconds"
                )

    # ============================================================
    # BUSINESS METHODS
    # ============================================================

    @api.model
    def get_validation_summary(self, contract_id, access_token):
        """
        Get summary of page validations for a contract

        Args:
            contract_id (int): Contract ID
            access_token (str): Portal access token

        Returns:
            dict: Validation summary with statistics
        """
        validations = self.search([
            ('contract_id', '=', contract_id),
            ('access_token', '=', access_token),
        ]).sorted('page_number')

        contract = self.env['construction.contract'].browse(contract_id)
        total_pages = contract.pdf_page_count

        validated_pages = validations.mapped('page_number')
        missing_pages = [p for p in range(1, total_pages + 1) if p not in validated_pages]

        total_time_spent = sum(validations.mapped('time_spent'))
        avg_time_per_page = total_time_spent / len(validations) if validations else 0

        return {
            'total_pages': total_pages,
            'validated_pages': len(validated_pages),
            'missing_pages': missing_pages,
            'completion_percentage': (len(validated_pages) / total_pages * 100) if total_pages else 0,
            'total_time_spent': total_time_spent,
            'avg_time_per_page': avg_time_per_page,
            'can_sign': len(missing_pages) == 0,
            'validations': validations.read(['page_number', 'validated_date', 'time_spent']),
        }
