from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class ResPartner(models.Model):
    _inherit = 'res.partner'

    document_cctp = fields.Binary(
        string="CCTP",
        attachment=True,
    )
    document_subcontractor_contract = fields.Binary(
        string="Contrat de Sous-traitance",
        attachment=True,
    )
    document_subcontractor_contract_signed = fields.Binary(
        string="Contrat de Sous-traitance signé",
        attachment=True,
    )

    # Upload token for secure portal access
    upload_token = fields.Char(
        string="Upload Token",
        copy=False,
        help="Secure token for document upload portal access"
    )

    token_expiration = fields.Datetime(
        string="Token Expiration",
        copy=False,
        help="Expiration date/time for upload token"
    )

    # Ajout du champ compute pour l'URL de dépôt
    subcontractor_contract_upload_url = fields.Char(
        string="Lien de dépôt du contrat de sous-traitance",
        compute="_compute_subcontractor_contract_upload_url",
        store=False
    )

    def _generate_upload_token(self):
        """
        Génère un token unique pour l'upload de documents via le portail.
        """
        import secrets
        import string
        from datetime import datetime, timedelta

        # Générer un token sécurisé
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(32))

        # Définir l'expiration à 7 jours
        expiration = datetime.now() + timedelta(days=7)

        self.write({
            'upload_token': token,
            'token_expiration': expiration
        })

        return token

    @api.depends('upload_token')
    def _compute_subcontractor_contract_upload_url(self):
        """
        Calcule l'URL de dépôt du contrat de sous-traitance.
        """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for partner in self:
            if partner.upload_token:
                partner.subcontractor_contract_upload_url = f"{base_url}/subcontractor/contract/upload/{partner.upload_token}"
            else:
                partner.subcontractor_contract_upload_url = ''
