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
    # TOKEN-BASED ENTRY POINT (from SMS/Email link)
    # ============================================================

    @http.route('/contract/sign/<string:token>', type='http', auth='public', website=True)
    def contract_sign_entry(self, token, **kwargs):
        """
        Entry point for contract signing via signing_token (from SMS/Email).
        
        Validates signing_token and redirects to main signature portal with access_token.
        Following construction_subcontractor pattern.
        
        Args:
            token (str): Signing token from contract.signing_token
            
        Returns:
            Redirect to signature portal or error page
        """
        contract = request.env['construction.contract'].sudo().search([
            ('signing_token', '=', token),
        ], limit=1)
        
        if not contract:
            return request.render('construction_contract.token_expired', {
                'error_title': _("Lien invalide"),
                'error_message': _("Ce lien de signature n'est pas valide ou a été révoqué."),
            })
        
        # Redirect to existing portal with access_token
        if contract.access_token:
            return request.redirect(f'/my/contract/{contract.id}/sign?access_token={contract.access_token}')
        else:
            # Generate access_token if missing
            contract._portal_ensure_token()
            return request.redirect(f'/my/contract/{contract.id}/sign?access_token={contract.access_token}')

    @http.route('/sign/verify/<string:token>', type='http', auth='public', website=True)
    def signature_verify(self, token, **kwargs):
        """
        Verify the authenticity of a signed document via its signature token (F-05).
        """
        signature = request.env['construction.contract.signature'].sudo().search([
            ('access_token', '=', token)
        ], limit=1)

        if not signature:
            return request.render('construction_contract.token_expired', {
                'error_title': _("Signature introuvable"),
                'error_message': _("Ce jeton de vérification de signature n'existe pas ou est invalide."),
            })

        return request.render('construction_contract.signature_verification_page', {
            'signature': signature,
            'contract': signature.contract_id,
        })

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

        # Fetch related attachments (CCTP, Plans)
        Attachment = request.env['ir.attachment'].sudo()
        domain = ['|', '|',
            '&', ('res_model', '=', 'construction.contract'), ('res_id', '=', contract.id),
            '&', ('res_model', '=', 'construction.chantier'), ('res_id', '=', contract.chantier_id.id),
            '&', ('res_model', '=', 'construction.lot'), ('res_id', 'in', contract.lot_ids.ids)
        ]
        attachments = Attachment.search(domain)

        values = {
            'contract': contract,
            'access_token': access_token,
            'validation_status': validation_status,
            'can_sign': can_sign,
            'pdf_url': f'/my/contract/{contract_id}/pdf?access_token={access_token}',
            'json': json,
            'attachments': attachments,
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
            # For type='json' routes, Odoo extracts params from JSON-RPC and passes them as arguments
            # If params are missing from arguments, get them from request.jsonrequest (Odoo 18 way)
            # or from the params directly in older versions
            
            # Try to get from request.jsonrequest if available (Odoo 18+)
            if hasattr(request, 'jsonrequest') and request.jsonrequest:
                if not contract_id:
                    contract_id = request.jsonrequest.get('contract_id')
                if not access_token:
                    access_token = request.jsonrequest.get('access_token')
                if not page_number:
                    page_number = request.jsonrequest.get('page_number')
                if not time_spent:
                    time_spent = request.jsonrequest.get('time_spent', 0)

            if not contract_id or not access_token:
                return {
                    'status': 'error',
                    'message': _("Missing required parameters: contract_id and access_token"),
                }

            contract = self._validate_access(contract_id, access_token)

            if not page_number:
                page_number = kwargs.get('current_page', 1)
            page_number = int(page_number)

            _logger.info(f"Validating page {page_number} for contract {contract_id}")
            
            result = contract.portal_validate_page(
                page_number=page_number,
                access_token=access_token,
                time_spent=time_spent
            )

            _logger.info(f"Page {page_number} validated successfully for contract {contract_id}")

            return {
                'status': 'success',
                'data': result,
            }

        except (ValidationError, AccessError) as e:
            _logger.warning(f"Validation/Access error validating page {page_number} for contract {contract_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
            }
        except Exception as e:
            _logger.error(f"Error validating page {page_number} for contract {contract_id}: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': _("An error occurred while validating the page: %s") % str(e),
            }

    # ============================================================
    # SIGNATURE SAVING
    # ============================================================

    @http.route('/my/contract/<int:contract_id>/save_signature', type='json', auth='public')
    def save_signature(self, contract_id, access_token=None, signature_data=None, **kwargs):
        """
        Save electronic signature

        Args:
            contract_id (int): Contract ID (from URL)
            access_token (str): Access token
            signature_data (str): Base64 signature image

        Returns:
            dict: Save result with redirect URL
        """
        try:
            # For type='json' routes, Odoo extracts params from JSON-RPC and passes them as arguments
            # If params are missing from arguments, get them from request.jsonrequest (Odoo 18 way)
            
            # Try to get from request.jsonrequest if available (Odoo 18+)
            if hasattr(request, 'jsonrequest') and request.jsonrequest:
                if not access_token:
                    access_token = request.jsonrequest.get('access_token')
                if not signature_data:
                    signature_data = request.jsonrequest.get('signature_data')
                if not contract_id:
                    contract_id = request.jsonrequest.get('contract_id')
            
            if not contract_id:
                return {
                    'status': 'error',
                    'message': _("Missing contract ID"),
                }
            
            if not access_token:
                return {
                    'status': 'error',
                    'message': _("Missing access token"),
                }

            contract = self._validate_access(contract_id, access_token)

            if not signature_data:
                return {
                    'status': 'error',
                    'message': _("Signature data is required."),
                }

            # Clean signature data (remove data:image/png;base64, prefix if present)
            _logger.info(f"Raw signature_data type: {type(signature_data)}, value preview: {str(signature_data)[:100] if signature_data else 'None'}")
            
            if signature_data:
                if isinstance(signature_data, (list, tuple)):
                    # If it's a list, take the first element
                    signature_data = signature_data[0] if signature_data else ''
                    _logger.warning(f"signature_data was a list/tuple with {len(signature_data) if hasattr(signature_data, '__len__') else 'unknown'} elements, using first element")
                
                # Ensure it's a string now
                if not isinstance(signature_data, str):
                    original_type = type(signature_data)
                    signature_data = str(signature_data)
                    _logger.warning(f"signature_data was {original_type}, converted to string")
                
                # Now it should be a string, process it
                if isinstance(signature_data, str):
                    if signature_data.startswith('data:'):
                        # Extract base64 part after comma
                        if ',' in signature_data:
                            parts = signature_data.split(',', 1)
                            if len(parts) > 1:
                                signature_data = parts[1]
                            else:
                                _logger.warning(f"signature_data has 'data:' prefix but no comma found")
                
            _logger.info(f"Cleaned signature_data type: {type(signature_data)}, length: {len(signature_data) if signature_data else 0}")
            
            # Get request information for traceability
            ip_address = '0.0.0.0'
            user_agent = ''
            
            try:
                if request and hasattr(request, 'httprequest'):
                    # Get IP address - handle different formats
                    remote_addr = request.httprequest.environ.get('REMOTE_ADDR', '')
                    
                    # Ensure remote_addr is a string
                    if isinstance(remote_addr, (list, tuple)):
                        remote_addr = remote_addr[0] if remote_addr else ''
                    elif not isinstance(remote_addr, str):
                        remote_addr = str(remote_addr) if remote_addr else ''
                    
                    # Try proxy headers
                    forwarded_for = request.httprequest.environ.get('HTTP_X_FORWARDED_FOR', '')
                    real_ip = request.httprequest.environ.get('HTTP_X_REAL_IP', '')
                    
                    # Ensure forwarded_for is a string, not a list
                    if isinstance(forwarded_for, (list, tuple)):
                        forwarded_for = forwarded_for[0] if forwarded_for else ''
                    elif not isinstance(forwarded_for, str):
                        forwarded_for = str(forwarded_for) if forwarded_for else ''
                    
                    # Ensure real_ip is a string
                    if isinstance(real_ip, (list, tuple)):
                        real_ip = real_ip[0] if real_ip else ''
                    elif not isinstance(real_ip, str):
                        real_ip = str(real_ip) if real_ip else ''
                    
                    # Get first IP from forwarded_for (can contain multiple IPs separated by comma)
                    if forwarded_for and isinstance(forwarded_for, str):
                        parts = forwarded_for.split(',')
                        ip_address = parts[0].strip() if parts else forwarded_for.strip()
                    elif real_ip and isinstance(real_ip, str):
                        ip_address = real_ip.strip()
                    elif remote_addr and isinstance(remote_addr, str):
                        ip_address = remote_addr.strip()
                    
                    # Get user agent
                    user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')
                    if isinstance(user_agent, (list, tuple)):
                        user_agent = user_agent[0] if user_agent else ''
                    elif not isinstance(user_agent, str):
                        user_agent = str(user_agent) if user_agent else ''
                        
            except Exception as e:
                _logger.warning(f"Could not get request info for signature: {e}", exc_info=True)
            
            _logger.info(f"Saving signature for contract {contract_id}, IP: {ip_address}, data length: {len(signature_data) if signature_data else 0}")
            
            result = contract.portal_save_signature(
                signature_data=signature_data,
                access_token=access_token,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            redirect_url = f"{base_url}/my/contract/{contract_id}/sign?access_token={access_token}"

            _logger.info(f"Signature saved successfully for contract {contract_id}, redirecting to {redirect_url}")

            return {
                'status': 'success',
                'data': result,
                'redirect_url': redirect_url,
            }

        except (ValidationError, AccessError) as e:
            _logger.warning(f"Validation/Access error saving signature for contract {contract_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
            }
        except Exception as e:
            _logger.error(f"Error saving signature for contract {contract_id}: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': _("An error occurred while saving the signature: %s") % str(e),
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
                _logger.error(f"PDF document not found for contract {contract_id}")
                raise NotFound(_("PDF document not found."))

            # Decode base64 PDF content
            import base64
            try:
                pdf_content = base64.b64decode(contract.pdf_document)
            except Exception as e:
                _logger.error(f"Failed to decode PDF for contract {contract_id}: {e}")
                raise NotFound(_("PDF document is corrupted."))
            
            filename = contract.pdf_filename or 'contract.pdf'
            
            _logger.info(f"Serving PDF for contract {contract_id}: {len(pdf_content)} bytes")

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

            # Decode base64 PDF content
            import base64
            pdf_content = base64.b64decode(contract.pdf_document)
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

    @http.route('/my/contract/<int:contract_id>/attachment/<int:attachment_id>', type='http', auth='public')
    def download_attachment(self, contract_id, attachment_id, access_token=None, **kwargs):
        """
        Download secondary attachment (CCTP, Plans, etc.)
        Secured by contract access token.
        """
        try:
            contract = self._validate_access(contract_id, access_token)
            
            # Verify attachment belongs to contract or related objects (Chantier, Lots)
            # For simplicity in this hotfix, we verify the attachment is linked to one of these models
            # and that the specific record is related to our contract.
            
            Attachment = request.env['ir.attachment'].sudo()
            attachment = Attachment.browse(attachment_id)
            
            if not attachment.exists():
                raise NotFound(_("Attachment not found."))
            
            # Security Check: Is this attachment related to our contract context?
            allowed_models = ['construction.contract', 'construction.chantier', 'construction.lot']
            if attachment.res_model not in allowed_models:
                 raise AccessError(_("Access denied to this document type."))
            
            # Check linkage
            is_allowed = False
            if attachment.res_model == 'construction.contract' and attachment.res_id == contract.id:
                is_allowed = True
            elif attachment.res_model == 'construction.chantier' and attachment.res_id == contract.chantier_id.id:
                is_allowed = True
            elif attachment.res_model == 'construction.lot' and attachment.res_id in contract.lot_ids.ids:
                is_allowed = True
                
            if not is_allowed:
                raise AccessError(_("This document does not belong to your contract context."))

            # Serve file
            filecontent =  attachment.datas
            if not filecontent:
                 raise NotFound(_("File content missing."))
                 
            import base64
            content = base64.b64decode(filecontent)
            
            return request.make_response(
                content,
                headers=[
                    ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                    ('Content-Disposition', f'attachment; filename="{attachment.name}"'),
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

            # Decode base64 PDF content
            import base64
            cert_content = base64.b64decode(contract.certificate_of_completion)
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
    # SIGNATURE SUCCESS PAGE (SAP-GRADE)
    # ============================================================

    @http.route('/my/contract/<int:contract_id>/success', type='http', auth='public', website=True)
    def signature_success(self, contract_id, access_token=None, **kwargs):
        """
        Signature success page with download option and audit summary.
        
        SAP-grade: Shows all audit trail information for legal proof.
        
        Args:
            contract_id (int): Contract ID
            access_token (str): Access token
            
        Returns:
            Rendered success page with download button
        """
        try:
            contract = self._validate_access(contract_id, access_token)
            
            if contract.state != 'signed':
                # Redirect to main portal if not signed yet
                return request.redirect(f'/my/contract/{contract_id}/sign?access_token={access_token}')
            
            # Get signature record
            signature = contract.signature_id
            
            # Build audit summary
            page_validations = contract.page_validation_ids.sorted('validated_at')
            
            values = {
                'contract': contract,
                'access_token': access_token,
                'signature': signature,
                'page_validations': page_validations,
                'total_pages': contract.pdf_page_count,
                'download_url': f'/my/contract/{contract_id}/download_signed?access_token={access_token}',
                'certificate_url': f'/my/contract/{contract_id}/download_certificate?access_token={access_token}',
                'audit_summary': {
                    'signed_at': signature.signed_at if signature else None,
                    'ip_address': signature.ip_address if signature else None,
                    'pdf_hash': contract.pdf_hash_after_signature[:16] + '...' if contract.pdf_hash_after_signature else None,
                    'pages_validated': len(page_validations),
                    'total_time_spent': sum(v.time_spent for v in page_validations) if page_validations else 0,
                },
            }
            
            _logger.info(
                f"[AUDIT] Showing success page for contract {contract.name}, "
                f"signature IP: {signature.ip_address if signature else 'N/A'}"
            )
            
            return request.render('construction_contract.signature_success_template', values)
            
        except (NotFound, Forbidden, AccessError) as e:
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

