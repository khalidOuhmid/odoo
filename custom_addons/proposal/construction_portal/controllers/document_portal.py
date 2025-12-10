# -*- coding: utf-8 -*-
from odoo import http, fields, _
from odoo.http import request
import base64
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class DocumentPortal(http.Controller):
    
    @http.route('/documents/upload/<string:token>', type='http', auth='public', website=True)
    def document_upload_portal(self, token, **kwargs):
        _logger.info("Document Portal Access Attempt with token: %s", token)
        partner = request.env['res.partner'].sudo().search([('upload_token', '=', token)], limit=1)
        
        if not partner:
            _logger.warning("Document Portal Access Denied: Invalid Token %s", token)
            return request.render('construction_portal.portal_error', {'error': 'Invalid Token'})
            
        doc_types = [
            ('kbis', 'KBIS'),
            ('urssaf', 'URSSAF'),
            ('insurance_dec', 'Décennale'),
            ('insurance_pro', 'RC Pro')
        ]
        
        return request.render('construction_portal.document_upload_template', {
            'partner': partner,
            'token': token,
            'doc_types': doc_types
        })

    @http.route('/documents/upload/submit', type='http', auth='public', methods=['POST'], website=True)
    def document_upload_submit(self, token, **kwargs):
        _logger.info("Document Upload Submission Attempt with token: %s", token)
        partner = request.env['res.partner'].sudo().search([('upload_token', '=', token)], limit=1)
        if not partner:
            _logger.warning("Document Upload Failed: Invalid Token %s", token)
            return request.render('construction_portal.portal_error', {'error': 'Invalid Token'})
            
        Document = request.env['construction.compliance.document'].sudo()
        
        uploaded_count = 0
        try:
            for key, file in kwargs.items():
                if key.startswith('file_') and file:
                    doc_type = key.replace('file_', '')
                    _logger.info("Processing file upload: Type=%s, Filename=%s for Partner %s", doc_type, file.filename, partner.name)
                    
                    file_content = file.read()
                    filename = file.filename
                    
                    Document.create({
                        'partner_id': partner.id,
                        'document_type': doc_type,
                        'file_data': base64.b64encode(file_content),
                        'filename': filename,
                        'expiry_date': fields.Date.today() + relativedelta(months=3), # Default expiry
                        'state': 'valid'
                    })
                    uploaded_count += 1
            
            _logger.info("Document Upload Success: %d files uploaded for Partner %s", uploaded_count, partner.name)
            
            return request.render('construction_portal.portal_success', {
                'title': 'Upload Successful',
                'message': f'{uploaded_count} documents have been uploaded successfully.'
            })
            
        except Exception as e:
            _logger.error("Document Upload Error for Partner %s: %s", partner.name, str(e), exc_info=True)
            return request.render('construction_portal.portal_error', {'error': 'An internal error occurred during upload.'})
