# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request

class ConstructionContractPortal(http.Controller):
    
    @http.route(['/my/contracts/<model("construction.contract"):contract>/sign'], type='http', auth='user', website=True)
    def portal_contract_sign(self, contract, **kwargs):
        """
        Subcontractor Portal for Signature.
        Displays the PDF and allows 'Click to Sign'.
        """
        vals = {
            'contract': contract,
            'page_name': 'contract_sign',
            'user': request.env.user
        }
        return request.render("construction_contract.portal_contract_sign_template", vals)

    @http.route(['/my/contracts/<model("construction.contract"):contract>/accept'], type='http', auth='user', methods=['POST'], website=True)
    def portal_contract_accept(self, contract, **kwargs):
        """
        Handle the signature action.
        """
        if contract.state != 'sent':
             return request.redirect('/my/home')
             
        # Mock Signature Logic (Update state)
        # In real life: Capture signature image, stamp PDF using reportlab, etc.
        contract.sudo().action_sign()
        
        return request.render("construction_contract.portal_contract_signed_success", {'contract': contract})
