# -*- coding: utf-8 -*-
from odoo import http, _, fields
from odoo.http import request
import base64
import logging

_logger = logging.getLogger(__name__)

class PortalContractController(http.Controller):

    @http.route('/portal/contract/<int:contract_id>/sign', type='http', auth='public', website=True)
    def contract_signature_page(self, contract_id, access_token=None, **kwargs):
        contract = self._get_contract_with_access(contract_id, access_token)
        if not contract:
            return request.render('construction_base.contract_access_denied', {'error': 'Accès non autorisé ou token invalide.'})

        if request.httprequest.method == 'POST':
            return self._process_signature(contract, kwargs)

        return request.render('construction_base.contract_signature_page', {
            'contract': contract,
            'access_token': access_token,
            'chantier': contract.chantier_id,
            'subcontractor': contract.subcontractor_id,
        })

    @http.route('/portal/contract/<int:contract_id>/html_preview', type='http', auth='public', website=True)
    def contract_html_preview(self, contract_id, access_token=None, **kwargs):
        contract = self._get_contract_with_access(contract_id, access_token)
        if not contract:
            return request.render('construction_base.contract_access_denied', {'error': 'Accès non autorisé.'})
        
        # Récupérer les images BLG en base64
        contract_service = request.env['construction.contract.service']
        blg_images = contract_service._get_blg_images_base64()
        
        return request.render('construction_base.contrat_sous_traitance_template', {
            'docs': [contract],
            'to_text': lambda b: b.decode('utf-8') if isinstance(b, bytes) else b,
            'blg_logo': blg_images['logo'],
            'blg_signature': blg_images['signature'],
        })

    @http.route('/portal/contract/<int:contract_id>/download', type='http', auth='public')
    def contract_download(self, contract_id, access_token=None, **kwargs):
        contract = self._get_contract_with_access(contract_id, access_token)
        if not contract or not contract.contract_pdf:
            return request.not_found()

        pdf_content = base64.b64decode(contract.contract_pdf)
        return request.make_response(pdf_content, [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', f'attachment; filename="{contract.filename or "Contrat.pdf"}"')
        ])

    @http.route('/portal/contract/<int:contract_id>/verify_signature', type='http', auth='public', website=True)
    def verify_signature(self, contract_id, access_token=None, **kwargs):
        """Page de vérification de l'authenticité de la signature électronique."""
        contract = self._get_contract_with_access(contract_id, access_token)
        if not contract:
            return request.render('construction_base.contract_access_denied', {'error': 'Accès non autorisé.'})
        
        signature_data = contract.get_signature_certificate_display()
        is_valid = contract.verify_signature_integrity()
        
        return request.render('construction_base.contract_signature_verification', {
            'contract': contract,
            'signature_data': signature_data,
            'is_valid': is_valid,
            'access_token': access_token,
        })

    def _get_contract_with_access(self, contract_id, access_token):
        try:
            contract = request.env['construction.subcontractor.contract'].sudo().browse(contract_id)
            if not contract.exists() or not access_token or contract.access_token != access_token:
                return None
            return contract
        except Exception as e:
            _logger.error(f"Erreur d'accès au contrat {contract_id}: {e}")
            return None

    def _process_signature(self, contract, form_data):
        try:
            if contract.signature_state == 'signed':
                return request.render('construction_base.contract_already_signed', {'contract': contract})

            signature_image_b64 = form_data.get('signature_image', '').split(',')[1] if form_data.get('signature_image') else False
            
            contract.action_electronic_signature({
                'ip': request.httprequest.remote_addr,
                'comment': form_data.get('signature_comment', ''),
                'signature_image': signature_image_b64,
                'user_agent': request.httprequest.headers.get('User-Agent', ''),
            })

            return request.render('construction_base.contract_signature_success', {'contract': contract, 'access_token': contract.access_token})
        except Exception as e:
            _logger.error(f"Erreur traitement signature contrat {contract.id}: {e}")
            return request.render('construction_base.contract_signature_error', {'contract': contract, 'error': str(e)})
