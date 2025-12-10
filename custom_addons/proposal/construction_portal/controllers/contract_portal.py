# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)

class ContractPortal(http.Controller):
    
    @http.route('/my/contract/<int:contract_id>/sign', type='http', auth='public', website=True)
    def contract_sign_portal(self, contract_id, access_token=None, **kwargs):
        _logger.info("Portal Access Attempt: Contract %s with token %s", contract_id, access_token)
        contract = request.env['construction.contract'].sudo().search([('id', '=', contract_id)], limit=1)
        
        if not contract:
             _logger.warning("Portal Access Denied: Contract %s not found", contract_id)
             return request.render('construction_portal.portal_error', {'error': 'Contract not found'})

        if contract.access_token != access_token:
            _logger.warning("Portal Access Denied: Invalid Token for Contract %s", contract_id)
            return request.render('construction_portal.portal_error', {'error': 'Invalid Token'})
            
        if contract.state == 'signed':
            _logger.info("Portal Access Info: Contract %s is already signed", contract_id)
            return request.render('construction_portal.portal_success', {
                'title': 'Contract Already Signed',
                'message': 'You have already signed this contract.'
            })
            
        return request.render('construction_portal.contract_sign_template', {
            'contract': contract,
            'token': access_token,
        })

    @http.route('/my/contract/<int:contract_id>/submit_sign', type='http', auth='public', methods=['POST'], website=True)
    def contract_submit_sign(self, contract_id, access_token=None, **kwargs):
        _logger.info("Signature Submission Attempt: Contract %s", contract_id)
        contract = request.env['construction.contract'].sudo().search([('id', '=', contract_id)], limit=1)
        
        if not contract or contract.access_token != access_token:
            _logger.warning("Signature Submission Failed: Invalid Token or Contract for %s", contract_id)
            return request.render('construction_portal.portal_error', {'error': 'Invalid Token'})
        
        try:
            signature_data = kwargs.get('signature')
            # Decode base64 if needed, but usually passed as base64 string from JS pad
            # We assume the JS sends "data:image/png;base64,..."
            if signature_data and ',' in signature_data:
                signature_data = signature_data.split(',')[1]

            contract.action_sign(signature_data=signature_data)
            _logger.info("Signature Success: Contract %s signed successfully", contract_id)
            
            return request.render('construction_portal.portal_success', {
                'title': 'Signature Confirmed',
                'message': 'Thank you! The contract has been signed.'
            })
        except Exception as e:
            _logger.error("Signature Submission Error for Contract %s: %s", contract_id, str(e), exc_info=True)
            return request.render('construction_portal.portal_error', {'error': 'An internal error occurred during signature.'})
