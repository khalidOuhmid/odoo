from odoo import http, fields, _
from odoo.http import request
import base64
import logging
import urllib.parse
from datetime import datetime

_logger = logging.getLogger(__name__)

class PortalSubcontractorContractUpload(http.Controller):
    @http.route(['/subcontractor/contract/download/<int:partner_id>'], type='http', auth='public', website=True)
    def download_subcontractor_contract(self, partner_id, **kw):
        """Permet au sous-traitant de télécharger le contrat de sous-traitance (PDF) non signé."""
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner or not partner.document_subcontractor_contract:
            return request.not_found()
        pdf_content = base64.b64decode(partner.document_subcontractor_contract)
        filename = 'Contrat_de_sous_traitance.pdf'
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', f'attachment; filename="{filename}"')
        ]
        return request.make_response(pdf_content, headers)

    def portal_subcontractor_contract_upload(self, token, **kw):
        """
        Page publique pour téléverser le contrat de sous-traitance (PDF).
        Sécurisé par token lié à un partenaire.
        """
        partner = self._validate_token(token)
        if not partner:
            return request.render('construction_base.subcontractor_contract_upload_error', {
                'datetime': datetime,
            })

        # Ajout du lien de téléchargement si le contrat existe
        contract_download_url = None
        if partner.document_subcontractor_contract:
            contract_download_url = f"/subcontractor/contract/download/{partner.id}"

        # Récupérer tous les documents liés à ce partenaire (sous-traitant)
        document_domain = [('partner_id', '=', partner.id)]
        documents = request.env['construction.document'].sudo().search(document_domain)

        error = None
        success = False
        if request.httprequest.method == 'POST':
            file = request.httprequest.files.get('contract_file')
            if not file:
                error = _(u"Veuillez sélectionner un fichier PDF à téléverser.")
            else:
                filename = file.filename
                if not filename.lower().endswith('.pdf'):
                    error = _(u"Le fichier doit être au format PDF.")
                else:
                    file.seek(0)
                    file_content = file.read()
                    if not file_content:
                        error = _(u"Le fichier est vide.")
                    else:
                        try:
                            partner.sudo().write({
                                'document_subcontractor_contract': base64.b64encode(file_content),
                                'document_subcontractor_status': 'tocheck',
                            })
                            success = True
                        except Exception as e:
                            _logger.error(f"Erreur lors de l'enregistrement du contrat: {e}")
                            error = _(u"Erreur lors de l'enregistrement du document.")

        return request.render('construction_base.subcontractor_contract_upload_form', {
            'partner': partner,
            'contract_download_url': contract_download_url,
            'documents': documents,
            'error': error,
            'success': success,
            'datetime': datetime,
        })

    def _validate_token(self, token):
        try:
            decoded_token = urllib.parse.unquote(token)
            partner = request.env['res.partner'].sudo().search([
                '|',
                ('upload_token', '=', decoded_token),
                ('upload_token', '=', token)
            ], limit=1)
            if not partner or not partner.token_expiration or partner.token_expiration < fields.Datetime.now():
                _logger.warning(f"Token invalide ou expiré: {token}")
                return None
            return partner
        except Exception as e:
            _logger.error(f"Erreur de validation du token: {e}")
            return None
