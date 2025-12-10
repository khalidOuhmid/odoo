# -*- coding: utf-8 -*-
"""
Portal Controller for Subcontractor Document Upload

Handles the public portal page where subcontractors upload their compliance documents.
"""

import logging
from datetime import datetime

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class SubcontractorPortalController(http.Controller):
    """Portal controller for subcontractor document upload."""
    
    @http.route('/subcontractor/upload/<string:token>', type='http', auth='public', 
                website=True, csrf=False)
    def subcontractor_upload_page(self, token, **kwargs):
        """Display the document upload page for a subcontractor."""
        
        # Find partner by token
        partner = request.env['res.partner'].sudo().search([
            ('upload_token', '=', token),
        ], limit=1)
        
        if not partner:
            return request.render('construction_subcontractor.upload_error', {
                'error_title': _("Lien invalide"),
                'error_message': _("Ce lien d'upload n'est pas valide ou a été révoqué.")
            })
        
        # Check token expiration
        if partner.token_expiration and partner.token_expiration < datetime.now():
            return request.render('construction_subcontractor.upload_error', {
                'error_title': _("Lien expiré"),
                'error_message': _("Ce lien d'upload a expiré. Veuillez en demander un nouveau.")
            })
        
        # Get document types and their current status
        doc_types = [
            {
                'key': 'kbis',
                'name': 'KBIS',
                'status': partner.doc_kbis_status,
                'has_file': bool(partner.doc_kbis),
                'expiry': partner.doc_kbis_expiry,
                'has_expiry': True,
            },
            {
                'key': 'urssaf',
                'name': 'Attestation URSSAF',
                'status': partner.doc_urssaf_status,
                'has_file': bool(partner.doc_urssaf),
                'expiry': partner.doc_urssaf_expiry,
                'has_expiry': True,
            },
            {
                'key': 'insurance_dec',
                'name': 'Assurance Décennale',
                'status': partner.doc_insurance_dec_status,
                'has_file': bool(partner.doc_insurance_dec),
                'expiry': partner.doc_insurance_dec_expiry,
                'has_expiry': True,
            },
            {
                'key': 'insurance_pro',
                'name': 'Assurance RC Pro',
                'status': partner.doc_insurance_pro_status,
                'has_file': bool(partner.doc_insurance_pro),
                'expiry': partner.doc_insurance_pro_expiry,
                'has_expiry': True,
            },
            {
                'key': 'rib',
                'name': 'RIB',
                'status': partner.doc_rib_status,
                'has_file': bool(partner.doc_rib),
                'has_expiry': False,
            },
        ]
        
        return request.render('construction_subcontractor.upload_page', {
            'partner': partner,
            'doc_types': doc_types,
            'token': token,
        })
    
    @http.route('/subcontractor/upload/<string:token>/submit', type='http', 
                auth='public', methods=['POST'], csrf=False)
    def subcontractor_upload_submit(self, token, **post):
        """Handle document upload submission."""
        
        # Validate token
        partner = request.env['res.partner'].sudo().search([
            ('upload_token', '=', token),
        ], limit=1)
        
        if not partner:
            return request.redirect('/subcontractor/upload/error')
        
        if partner.token_expiration and partner.token_expiration < datetime.now():
            return request.redirect('/subcontractor/upload/error')
        
        # Process uploaded files
        updates = {}
        doc_keys = ['kbis', 'urssaf', 'insurance_dec', 'insurance_pro', 'rib']
        
        for key in doc_keys:
            file_key = f'doc_{key}'
            expiry_key = f'doc_{key}_expiry'
            
            if file_key in request.httprequest.files:
                file = request.httprequest.files[file_key]
                if file.filename:
                    import base64
                    file_content = base64.b64encode(file.read())
                    updates[f'doc_{key}'] = file_content
                    updates[f'doc_{key}_filename'] = file.filename
            
            # Handle expiry date
            if expiry_key in post and post[expiry_key]:
                try:
                    expiry_date = datetime.strptime(post[expiry_key], '%Y-%m-%d').date()
                    updates[f'doc_{key}_expiry'] = expiry_date
                except ValueError:
                    pass
        
        if updates:
            partner.write(updates)
            partner.message_post(
                body=_("📁 Documents mis à jour via le portail par %s") % partner.name,
                message_type='notification'
            )
        
        return request.render('construction_subcontractor.upload_success', {
            'partner': partner,
        })
    
    @http.route('/subcontractor/upload/error', type='http', auth='public', website=True)
    def upload_error_page(self, **kwargs):
        """Display generic error page."""
        return request.render('construction_subcontractor.upload_error', {
            'error_title': _("Erreur"),
            'error_message': _("Une erreur s'est produite. Veuillez réessayer.")
        })
