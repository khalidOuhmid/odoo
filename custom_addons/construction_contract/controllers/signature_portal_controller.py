# -*- coding: utf-8 -*-
"""
Signature Portal Controller
Handles all portal routes for contract signature workflow
"""

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError, AccessError
from werkzeug.exceptions import NotFound, Forbidden
import json
import logging

_logger = logging.getLogger(__name__)


class SignaturePortalController(http.Controller):
    """
    Portal Controller for Electronic Signature

    Provides routes for:
    - Contract viewing and signature portal
    - Page validation tracking
    - Signature capture and storage
    - PDF download endpoints
    """

    # ============================================================
    # MAIN SIGNATURE PORTAL
    # ============================================================

    @http.route('/my/contract/<int:contract_id>/sign', type='http', auth='public', website=True)
    def contract_signature_portal(self, contract_id, access_token=None, **kwargs):
        """
        Main signature portal page

        Args:
            contract_id (int): Contract ID
            access_token (str): Access token for authentication

        Returns:
            Rendered portal page or error page
        """
        try:
            contract = self._validate_access(contract_id, access_token)
        except (NotFound, Forbidden, AccessError) as e:
            return self._render_error_page('contract_not_found', str(e))

        if contract._is_token_expired(access_token):
            return request.render('construction_contract.token_expired', {
                'contract': contract,
            })

        if contract.state == 'signed':
            signature = contract.signature_id
            return request.render('construction_contract.signature_confirmation_template', {
                'contract': contract,
                'signature': signature,
                'access_token': access_token,
            })

        if contract.state not in ['sent', 'in_progress']:
            return request.render('construction_contract.contract_unavailable', {
                'contract': contract,
            })

        validation_status = contract._get_page_validation_status(access_token)
        can_sign = validation_status.get('can_sign', False)

        values = {
            'contract': contract,
            'access_token': access_token,
            'validation_status': validation_status,
            'can_sign': can_sign,
            'pdf_url': f'/my/contract/{contract_id}/pdf?access_token={access_token}',
            'json': json,
        }

        return request.render('construction_contract.signature_portal_template', values)

    # ============================================================
    # PAGE VALIDATION
    # ============================================================

    @http.route('/contract/page/validate', type='json', auth='public')
    def validate_page(self, contract_id=None, access_token=None, page_number=None, time_spent=0, **kwargs):
        """
        Validate that a page has been read

        Args:
            contract_id (int): Contract ID
            access_token (str): Access token
            page_number (int): Page number being validated
            time_spent (int): Time spent reading the page (seconds)

        Returns:
            dict: Validation result
        """
        try:
            contract = self._validate_access(contract_id, access_token)

            if not page_number:
                current_page = kwargs.get('current_page', 1)
                page_number = int(current_page)

            result = contract.portal_validate_page(
                page_number=page_number,
                access_token=access_token,
                time_spent=time_spent
            )

            return {
                'status': 'success',
                'data': result,
            }

        except (ValidationError, AccessError) as e:
            return {
                'status': 'error',
                'message': str(e),
            }
        except Exception as e:
            _logger.error(f"Error validating page: {e}")
            return {
                'status': 'error',
                'message': _("An error occurred while validating the page."),
            }

    # ============================================================
    # SIGNATURE SAVING
    # ============================================================

    @http.route('/my/contract/<int:contract_id>/save_signature', type='json', auth='public')
    def save_signature(self, contract_id, access_token=None, signature_data=None, **kwargs):
        """
        Save electronic signature

        Args:
            contract_id (int): Contract ID
            access_token (str): Access token
            signature_data (str): Base64 signature image

        Returns:
            dict: Save result with redirect URL
        """
        try:
            contract = self._validate_access(contract_id, access_token)

            if not signature_data:
                raise ValidationError(_("Signature data is required."))

            result = contract.portal_save_signature(
                signature_data=signature_data,
                access_token=access_token
            )

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            redirect_url = f"{base_url}/my/contract/{contract_id}/sign?access_token={access_token}"

            return {
                'status': 'success',
                'data': result,
                'redirect_url': redirect_url,
            }

        except (ValidationError, AccessError) as e:
            return {
                'status': 'error',
                'message': str(e),
            }
        except Exception as e:
            _logger.error(f"Error saving signature for contract {contract_id}: {e}")
            return {
                'status': 'error',
                'message': _("An error occurred while saving the signature."),
            }

    # ============================================================
    # PDF DOWNLOAD ROUTES
    # ============================================================

    @http.route('/my/contract/<int:contract_id>/pdf', type='http', auth='public')
    def download_contract_pdf(self, contract_id, access_token=None, **kwargs):
        """
        Download or view contract PDF

        Args:
            contract_id (int): Contract ID
            access_token (str): Access token

        Returns:
            PDF file response
        """
        try:
            contract = self._validate_access(contract_id, access_token)

            if not contract.pdf_document:
                raise NotFound(_("PDF document not found."))

            pdf_content = contract.pdf_document
            filename = contract.pdf_filename or 'contract.pdf'

            return request.make_response(
                pdf_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'inline; filename="{filename}"'),
                ],
            )

        except (NotFound, AccessError) as e:
            return self._render_error_page('contract_not_found', str(e))

    @http.route('/my/contract/<int:contract_id>/download_signed', type='http', auth='public')
    def download_signed_contract(self, contract_id, access_token=None, **kwargs):
        """
        Download signed contract PDF

        Args:
            contract_id (int): Contract ID
            access_token (str): Access token

        Returns:
            PDF file response
        """
        try:
            contract = self._validate_access(contract_id, access_token)

            if contract.state != 'signed':
                raise AccessError(_("Contract has not been signed yet."))

            if not contract.pdf_document:
                raise NotFound(_("PDF document not found."))

            pdf_content = contract.pdf_document
            filename = contract.pdf_filename or 'contract_signed.pdf'

            return request.make_response(
                pdf_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                ],
            )

        except (NotFound, AccessError) as e:
            return self._render_error_page('contract_not_found', str(e))

    @http.route('/my/contract/<int:contract_id>/download_certificate', type='http', auth='public')
    def download_certificate(self, contract_id, access_token=None, **kwargs):
        """
        Download certificate of completion

        Args:
            contract_id (int): Contract ID
            access_token (str): Access token

        Returns:
            PDF certificate response
        """
        try:
            contract = self._validate_access(contract_id, access_token)

            if contract.state != 'signed':
                raise AccessError(_("Certificate is only available for signed contracts."))

            if not contract.certificate_of_completion:
                raise NotFound(_("Certificate not found."))

            cert_content = contract.certificate_of_completion
            filename = contract.certificate_filename or 'certificate.pdf'

            return request.make_response(
                cert_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                ],
            )

        except (NotFound, AccessError) as e:
            return self._render_error_page('contract_not_found', str(e))

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _validate_access(self, contract_id, access_token):
        """
        Validate contract access with token

        Args:
            contract_id (int): Contract ID
            access_token (str): Access token

        Returns:
            construction.contract: Contract record

        Raises:
            NotFound: If contract doesn't exist
            Forbidden: If token is invalid
        """
        if not contract_id:
            raise NotFound(_("Contract ID is required."))

        contract = request.env['construction.contract'].sudo().browse(int(contract_id))

        if not contract.exists():
            raise NotFound(_("Contract not found."))

        if not access_token:
            raise Forbidden(_("Access token is required."))

        if contract.access_token != access_token:
            raise Forbidden(_("Invalid access token."))

        return contract

    def _render_error_page(self, template_name, message):
        """
        Render error page

        Args:
            template_name (str): Template name
            message (str): Error message

        Returns:
            Rendered error page
        """
        values = {
            'error_message': message,
        }

        return request.render(f'construction_contract.{template_name}', values)

