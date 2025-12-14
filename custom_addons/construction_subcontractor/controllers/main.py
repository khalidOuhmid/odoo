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
        
        # Get document types dynamically from model config if possible, or hardcoded for safety based on user request
        doc_types = [
            {
                'key': 'kbis',
                'name': 'KBIS (Extrait Kbis)',
                'status': partner.doc_kbis_status,
                'has_file': bool(partner.doc_kbis),
                'expiry': partner.doc_kbis_expiry,
                'has_expiry': True,
                'required': True,
            },
            {
                'key': 'urssaf',
                'name': 'Attestation URSSAF',
                'status': partner.doc_urssaf_status,
                'has_file': bool(partner.doc_urssaf),
                'expiry': partner.doc_urssaf_expiry,
                'has_expiry': True,
                'required': True,
            },
            {
                'key': 'insurance_dec',
                'name': 'Assurance Décennale',
                'status': partner.doc_insurance_dec_status,
                'has_file': bool(partner.doc_insurance_dec),
                'expiry': partner.doc_insurance_dec_expiry,
                'has_expiry': True,
                'required': True,
            },
            {
                'key': 'cni',
                'name': 'Carte d\'Identité (Gérant)',
                'status': partner.doc_cni_status,
                'has_file': bool(partner.doc_cni),
                'expiry': partner.doc_cni_expiry,
                'has_expiry': True,
                'required': True,
            },
            {
                'key': 'rib',
                'name': 'Relevé d\'Identité Bancaire (RIB)',
                'status': partner.doc_rib_status,
                'has_file': bool(partner.doc_rib),
                'has_expiry': False,
                'required': False,
            },
        ]
        
        return request.render('construction_subcontractor.upload_page', {
            'partner': partner,
            'doc_types': doc_types,
            'token': token,
        })
    
    @http.route('/subcontractor/upload/<string:token>/process', type='http', auth='public', methods=['POST'], csrf=False)
    def subcontractor_upload_process(self, token, **post):
        """
        Handle individual document upload/update via AJAX.
        Returns JSON response to allow partial updates without page reload.
        """
        partner = request.env['res.partner'].sudo().search([('upload_token', '=', token)], limit=1)
        
        if not partner:
            return request.make_json_response({'error': _("Lien invalide ou partenaire introuvable.")}, status=400)
            
        if partner.token_expiration and partner.token_expiration < datetime.now():
            return request.make_json_response({'error': _("Lien expiré.")}, status=403)

        # Identify which document is being updated
        doc_key = post.get('doc_key')
        if not doc_key:
            return request.make_json_response({'error': _("Type de document manquant.")}, status=400)

        updates = {}
        file_key = f'doc_{doc_key}' # e.g., doc_kbis
        expiry_key = 'expiry_date' # Genric key sent by JS
        
        if 'file' in request.httprequest.files:
            file = request.httprequest.files['file']
            if file.filename:
                import base64
                import os
                
                # --- Auto-Renaming Logic ---
                # Map keys to readable prefixes
                DOC_PREFIXES = {
                    'kbis': 'KBIS',
                    'urssaf': 'URSSAF',
                    'insurance_dec': 'DECENNALE',
                    'insurance_pro': 'RC_PRO',
                    'cni': 'CNI',
                    'rib': 'RIB',
                }
                
                # Clean partner name (simple sanitization)
                clean_name = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in partner.name]).strip()
                prefix = DOC_PREFIXES.get(doc_key, doc_key.upper())
                date_str = datetime.today().strftime('%Y-%m-%d')
                ext = os.path.splitext(file.filename)[1]
                if not ext:
                    ext = '.pdf' # Default fallback
                    
                new_filename = f"{prefix} {clean_name} - {date_str}{ext}"
                
                file_content = base64.b64encode(file.read())
                updates[file_key] = file_content
                updates[f'{file_key}_filename'] = new_filename
        
        # 2. Handle Expiry Date
        if expiry_key in post and post[expiry_key]:
            try:
                expiry_date = datetime.strptime(post[expiry_key], '%Y-%m-%d').date()
                updates[f'{file_key}_expiry'] = expiry_date
            except ValueError:
                return request.make_json_response({'error': _("Format de date invalide.")}, status=400)

        if updates:
            try:
                partner.write(updates)
                partner._compute_compliance_state() # Force recompute immediate
                
                # Log only significant changes (to avoid spamming chatter on every date pick)
                if any(k.endswith('_filename') for k in updates.keys()):
                    partner.message_post(
                        body=_("📄 Document '%s' mis à jour via le portail.") % doc_key,
                        message_type='notification'
                    )
                    
                return request.make_json_response({
                    'success': True,
                    'doc_key': doc_key,
                    'status': getattr(partner, f'{file_key}_status'),
                    'is_compliant': partner.compliance_state == 'compliant'
                })
            except Exception as e:
                _logger.error(f"Upload error for {partner.name}: {str(e)}")
                return request.make_json_response({'error': str(e)}, status=500)
        
        return request.make_json_response({'success': True, 'message': 'No changes detected'})

    # Removed old 'subcontractor_upload_submit' and 'upload_error_page' as we are single-page app now
