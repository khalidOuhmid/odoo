# -*- coding: utf-8 -*-
"""
Portal Controller for Subcontractor Document Upload

Handles the public portal page where subcontractors upload their compliance documents.
"""

import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

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
        all_doc_types = [
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

        # FILTER: Show only documents requiring action (Missing, Rejected, Expired, Expiring)
        # Always show RIB (optional but editable)
        # Hide 'valid' and 'to_check' (pending validation)
        doc_types = []
        for doc in all_doc_types:
            if doc['key'] == 'rib':
                doc_types.append(doc)
            elif doc['status'] not in ['valid', 'to_check']:
                doc_types.append(doc)
        
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

    @http.route('/subcontractor/upload/<string:token>/submit-single', type='json', auth='public', csrf=False)
    def subcontractor_submit_single(self, token, **post):
        """Submit a single staged document from localStorage.
        
        This endpoint receives base64-encoded file data that was cached
        in the browser's localStorage during the staging workflow.
        
        Args:
            token: Partner upload token for authentication
            doc_key: Document type key (kbis, urssaf, etc.)
            file_base64: Base64-encoded file content
            filename: Original filename
            expiry_date: Optional expiry date (YYYY-MM-DD)
            
        Returns:
            JSON response with success status and updated document state
        """
        # Validate token and get partner
        partner = request.env['res.partner'].sudo().search([
            ('upload_token', '=', token)
        ], limit=1)
        
        if not partner:
            return {'error': _("Lien invalide ou partenaire introuvable."), 'success': False}
        
        if partner.token_expiration and partner.token_expiration < datetime.now():
            return {'error': _("Lien expiré."), 'success': False}
        
        # Extract parameters from JSON body
        doc_key = post.get('doc_key')
        file_base64 = post.get('file_base64')
        filename = post.get('filename')
        expiry_date_str = post.get('expiry_date')
        
        if not doc_key:
            return {'error': _("Type de document manquant."), 'success': False}
        
        if not file_base64:
            return {'error': _("Contenu du fichier manquant."), 'success': False}
        
        # Prepare update values
        updates = {}
        file_field = f'doc_{doc_key}'  # e.g., doc_kbis
        
        # --- Auto-Renaming Logic (SAP-style consistent naming) ---
        DOC_PREFIXES = {
            'kbis': 'KBIS',
            'urssaf': 'URSSAF',
            'insurance_dec': 'DECENNALE',
            'insurance_pro': 'RC_PRO',
            'cni': 'CNI',
            'rib': 'RIB',
        }
        
        import os
        clean_name = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in partner.name]).strip()
        prefix = DOC_PREFIXES.get(doc_key, doc_key.upper())
        date_str = datetime.today().strftime('%Y-%m-%d')
        ext = os.path.splitext(filename)[1] if filename else '.pdf'
        
        new_filename = f"{prefix} {clean_name} - {date_str}{ext}"
        
        # Store file content (already base64 encoded)
        updates[file_field] = file_base64
        updates[f'{file_field}_filename'] = new_filename
        
        # Handle expiry date
        if expiry_date_str:
            try:
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                updates[f'{file_field}_expiry'] = expiry_date
            except ValueError:
                return {'error': _("Format de date invalide."), 'success': False}
        
        # Execute write with transaction safety
        try:
            partner.write(updates)
            partner._compute_compliance_state()  # Force immediate recompute
            
            # Audit trail in chatter
            partner.message_post(
                body=_("📄 Document '%s' soumis via le portail (workflow de staging).") % doc_key,
                message_type='notification'
            )
            
            return {
                'success': True,
                'doc_key': doc_key,
                'status': getattr(partner, f'{file_field}_status', 'valid'),
                'is_compliant': partner.compliance_state == 'compliant'
            }
        except Exception as e:
            _logger.error(f"Submit error for {partner.name} - {doc_key}: {str(e)}")
            return {'error': str(e), 'success': False}

    # ============= SERVER-SIDE SESSION STAGING ============= #
    # Fixes localStorage quota exceeded error for large files
    
    def _get_session_key(self, token):
        """Generate unique session key for staging area."""
        return f'subcontractor_staged_{token}'
    
    def _validate_token(self, token):
        """Validate token and return partner or None.
        
        Returns:
            tuple: (partner, error_dict) - partner if valid, else (None, error)
        """
        partner = request.env['res.partner'].sudo().search([
            ('upload_token', '=', token)
        ], limit=1)
        
        if not partner:
            return None, {'error': _("Lien invalide ou partenaire introuvable."), 'success': False}
        
        if partner.token_expiration and partner.token_expiration < datetime.now():
            return None, {'error': _("Lien expiré."), 'success': False}
        
        return partner, None

    @http.route('/subcontractor/upload/<string:token>/stage', type='http', auth='public', 
                methods=['POST'], csrf=False)
    def stage_document(self, token, **post):
        """Stage a document in server session without saving to database.
        
        This avoids localStorage quota issues by storing files server-side.
        Files are stored in session until user clicks 'Submit All'.
        
        Args:
            token: Partner upload token
            doc_key: Document type key
            file: Uploaded file
            expiry_date: Optional expiry date
            
        Returns:
            JSON response with staged document info
        """
        import base64
        import os
        
        partner, error = self._validate_token(token)
        if error:
            return request.make_json_response(error, status=200)
        
        doc_key = post.get('doc_key')
        if not doc_key:
            return request.make_json_response(
                {'error': _("Type de document manquant."), 'success': False}, 
                status=200
            )
        
        # Get or create staging area in session
        session_key = self._get_session_key(token)
        
        # DEBUG: Log session state
        session_id = getattr(request.session, 'sid', 'NO_SID')
        _logger.info(f"STAGE DEBUG: session_id={session_id}, session_key={session_key}")
        _logger.info(f"STAGE DEBUG: current session keys={list(request.session.keys())}")
        
        # Get existing staged docs or create new dict
        staged_docs = dict(request.session.get(session_key, {}))
        _logger.info(f"STAGE DEBUG: existing staged_docs BEFORE add = {list(staged_docs.keys())}")
        
        # Process uploaded file
        if 'file' in request.httprequest.files:
            file = request.httprequest.files['file']
            if file.filename:
                file_content = base64.b64encode(file.read()).decode('utf-8')
                ext = os.path.splitext(file.filename)[1] or '.pdf'
                
                # Expiry Logic - Auto-calculate for KBIS/URSSAF
                expiry_date_str = post.get('expiry_date')
                calculated_expiry = None
                
                if doc_key == 'kbis':
                    # KBIS valid for 3 months from today
                    calculated_expiry = (date.today() + relativedelta(months=3)).strftime('%Y-%m-%d')
                elif doc_key == 'urssaf':
                    # URSSAF valid for 6 months from today
                    calculated_expiry = (date.today() + relativedelta(months=6)).strftime('%Y-%m-%d')
                
                final_expiry = calculated_expiry if calculated_expiry else expiry_date_str

                staged_docs[doc_key] = {
                    'filename': file.filename,
                    'file_data': file_content,
                    'extension': ext,
                    'expiry_date': final_expiry,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Explicit reassignment and modification flag
                request.session[session_key] = staged_docs
                request.session.modified = True
                
                # DEBUG: Verify what's in session after update
                verify_docs = request.session.get(session_key, {})
                _logger.info(f"STAGE DEBUG: staged_docs AFTER add = {list(verify_docs.keys())}")
                
                _logger.info(f"Staged {doc_key} for token {token[:10]}..., session key: {session_key}, count: {len(staged_docs)}")
                
                return request.make_json_response({
                    'success': True,
                    'doc_key': doc_key,
                    'filename': file.filename,
                    'staged_count': len(staged_docs),
                    'expiry_date': final_expiry
                })
        
        # Handle date update only? (Not used in current flow but kept for safety)
        if (post.get('expiry_date') or post.get('issue_date')) and doc_key in staged_docs:
             # Same logic...
             pass
        
        return request.make_json_response(
            {'error': _("Aucun fichier fourni."), 'success': False}, 
            status=200
        )

    @http.route('/subcontractor/upload/<string:token>/session-state', type='http', 
                auth='public', methods=['POST'], csrf=False)
    def get_session_state(self, token, **post):
        """Get current staging state from server session.
        
        Returns list of staged document keys for UI recovery.
        """
        partner, error = self._validate_token(token)
        if error:
            return request.make_json_response(error, status=400)
        
        session_key = self._get_session_key(token)
        staged_docs = request.session.get(session_key, {})
        
        return request.make_json_response({
            'success': True,
            'staged_docs': {
                key: {
                    'filename': doc['filename'],
                    'expiry_date': doc.get('expiry_date'),
                    'timestamp': doc.get('timestamp')
                }
                for key, doc in staged_docs.items()
            },
            'staged_count': len(staged_docs)
        })

    @http.route('/subcontractor/upload/<string:token>/submit-all', type='http', 
                auth='public', methods=['POST'], csrf=False)
    def submit_all_staged(self, token, **post):
        """Submit all staged documents to database.
        
        Moves documents from session staging area to partner record.
        Clears session after successful submission.
        """
        import os
        
        partner, error = self._validate_token(token)
        if error:
            return request.make_json_response(error, status=400)
        
        session_key = self._get_session_key(token)
        staged_docs = request.session.get(session_key, {})
        
        _logger.info(f"Submit-all for token {token[:10]}..., session key: {session_key}, staged_docs keys: {list(staged_docs.keys()) if staged_docs else 'EMPTY'}")
        
        if not staged_docs:
            return request.make_json_response({'error': _("Aucun document en attente. Veuillez d'abord sélectionner des fichiers."), 'success': False}, status=200)

        # VALIDATION: Check expiry dates for required docs
        REQUIRED_EXPIRY_DOCS = ['cni', 'insurance_dec']
        DOC_NAMES = {'cni': "Carte d'identité", 'insurance_dec': 'Assurance Décennale'}
        
        for key, doc_data in staged_docs.items():
            if key in REQUIRED_EXPIRY_DOCS and not doc_data.get('expiry_date'):
                doc_name = DOC_NAMES.get(key, key)
                return request.make_json_response({
                    'error': _("La date d'expiration est manquante pour : %s") % doc_name, 
                    'success': False
                }, status=200)
        
        # ============= SERVER-SIDE VALIDATION GUARD ============= #
        # Verify all REQUIRED documents are present before allowing submit
        REQUIRED_DOCS = ['kbis', 'urssaf', 'insurance_dec', 'cni']
        
        # Check which required docs are being submitted OR already exist on partner
        missing_required = []
        for doc_key in REQUIRED_DOCS:
            is_in_staged = doc_key in staged_docs
            has_on_partner = bool(getattr(partner, f'doc_{doc_key}', None))
            
            if not is_in_staged and not has_on_partner:
                missing_required.append(doc_key.upper())
        
        if missing_required:
            return request.make_json_response({
                'error': _("Documents obligatoires manquants: %s. Veuillez les ajouter avant de soumettre.") % ', '.join(missing_required),
                'success': False,
                'missing_docs': missing_required
            }, status=200)
        
        # Document prefixes for consistent naming
        DOC_PREFIXES = {
            'kbis': 'KBIS',
            'urssaf': 'URSSAF',
            'insurance_dec': 'DECENNALE',
            'insurance_pro': 'RC_PRO',
            'cni': 'CNI',
            'rib': 'RIB',
        }
        
        updates = {}
        submitted_docs = []
        
        for doc_key, doc_data in staged_docs.items():
            file_field = f'doc_{doc_key}'
            
            # Generate standardized filename
            clean_name = "".join([
                c if c.isalnum() or c in (' ', '-', '_') else '_' 
                for c in partner.name
            ]).strip()
            prefix = DOC_PREFIXES.get(doc_key, doc_key.upper())
            date_str = datetime.today().strftime('%Y-%m-%d')
            ext = doc_data.get('extension', '.pdf')
            
            new_filename = f"{prefix} {clean_name} - {date_str}{ext}"
            
            # Add to updates
            updates[file_field] = doc_data['file_data']
            updates[f'{file_field}_filename'] = new_filename
            
            # Handle expiry date passed from stage
            if doc_data.get('expiry_date'):
                try:
                    expiry = datetime.strptime(doc_data['expiry_date'], '%Y-%m-%d').date()
                    updates[f'{file_field}_expiry'] = expiry
                except ValueError:
                    pass  # Skip invalid dates
            
            submitted_docs.append(doc_key)
        
        try:
            partner.write(updates)
            partner._compute_compliance_state()
            
            # Clear session staging area
            request.session[session_key] = {}
            
            # Audit trail
            partner.message_post(
                body=_("📄 %d document(s) soumis via le portail: %s") % (
                    len(submitted_docs), 
                    ', '.join(submitted_docs)
                ),
                message_type='notification'
            )
            
            return request.make_json_response({
                'success': True,
                'submitted_count': len(submitted_docs),
                'submitted_docs': submitted_docs,
                'is_compliant': partner.compliance_state == 'compliant',
                'redirect_url': f'/subcontractor/upload/{token}/success'
            })
        except Exception as e:
            _logger.error(f"Submit all error for {partner.name}: {str(e)}")
            return request.make_json_response({'error': str(e), 'success': False}, status=500)

    @http.route('/subcontractor/upload/<string:token>/clear-staged', type='json', 
                auth='public', csrf=False)
    def clear_staged(self, token, doc_key=None, **post):
        """Clear staged documents from session.
        
        Args:
            doc_key: Optional - clear specific doc, or all if not provided
        """
        partner, error = self._validate_token(token)
        if error:
            return error
        
        session_key = self._get_session_key(token)
        
        if doc_key:
            # Clear specific document
            staged_docs = request.session.get(session_key, {})
            if doc_key in staged_docs:
                del staged_docs[doc_key]
                request.session[session_key] = staged_docs
        else:
            # Clear all
            request.session[session_key] = {}
        
        return {'success': True, 'message': 'Staging area cleared'}

    @http.route('/subcontractor/upload/<string:token>/success', type='http', auth='public',
                csrf=False)
    def upload_success(self, token, **kwargs):
        """Display success page after document submission."""
        from odoo.http import Response
        
        partner, error = self._validate_token(token)
        if error:
            return Response(f"""
            <html>
            <head><title>Erreur</title></head>
            <body style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f5f5f5;">
                <div style="text-align:center;padding:40px;background:white;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                    <h1 style="color:#dc3545;">Erreur</h1>
                    <p>{str(error)}</p>
                </div>
            </body>
            </html>
            """, content_type='text/html')
        
        html = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Documents Soumis - BLG Groupe</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
            <style>
                body {{ background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%); min-height: 100vh; }}
                .success-card {{ border-radius: 20px; }}
            </style>
        </head>
        <body class="d-flex align-items-center justify-content-center">
            <div class="container py-5">
                <div class="row justify-content-center">
                    <div class="col-lg-8">
                        <div class="text-center mb-4">
                            <h4 class="text-muted">BLG Groupe - Espace Partenaire</h4>
                        </div>
                        
                        <div class="card success-card shadow-lg border-0">
                            <div class="card-body text-center py-5">
                                <div class="mb-4">
                                    <i class="fa-solid fa-circle-check text-success" style="font-size: 100px;"></i>
                                </div>
                                <h1 class="text-success mb-3">Documents soumis avec succès !</h1>
                                <p class="lead text-muted mb-4">
                                    Merci <strong>{partner.name}</strong> pour votre soumission.
                                </p>
                                
                                <div class="alert alert-info text-start mb-4" role="alert">
                                    <h5 class="alert-heading"><i class="fa-solid fa-info-circle me-2"></i>Prochaines étapes</h5>
                                    <hr>
                                    <ul class="mb-0">
                                        <li>Vos documents vont être <strong>vérifiés</strong> par notre équipe administrative.</li>
                                        <li>Vous recevrez une <strong>notification par email</strong> une fois la vérification terminée.</li>
                                        <li>En cas de problème, nous vous contacterons pour demander des corrections.</li>
                                    </ul>
                                </div>
                                
                                <div class="d-flex justify-content-center gap-3">
                                    <a href="/subcontractor/upload/{token}" class="btn btn-outline-secondary btn-lg">
                                        <i class="fa-solid fa-arrow-left me-2"></i>Retour au portail
                                    </a>
                                </div>
                            </div>
                        </div>
                        
                        <p class="text-center text-muted mt-4 small">
                            <i class="fa-solid fa-building me-1"></i> © 2025 BLG Groupe - Tous droits réservés
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return Response(html, content_type='text/html')
