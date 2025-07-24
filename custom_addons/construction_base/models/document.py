from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import io


class Document(models.Model):
    _name = 'construction.document'
    _description = 'Construction Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Document Name', required=True, tracking=True)
    chantier_id = fields.Many2one('construction.chantier', string='Project',
                                  required=True, tracking=True)
    chapter_id = fields.Many2one('construction.chapter', string='Chapter')
    stage_id = fields.Many2one('construction.stage', string='Stage')

    document_type = fields.Selection([
        ('quote', 'Devis'),
        ('contract', 'Contrat'),
        ('subcontract', 'Sous-traitance'),
        ('specs', 'Spécifications techniques'),
        ('plan', 'Plan'),
        ('schedule', 'Planning'),
        ('permit', 'Permis'),
        ('other', 'Autre')
    ], string='Type de Document', required=True, tracking=True)

    # Approche simplifiée avec champ Binary
    file_data = fields.Binary('File', required=True, attachment=True)
    filename = fields.Char('Nom du fichier', required=True)
    file_size = fields.Integer('Taille du fichier', readonly=True)
    
    # Champ pour l'attachement (référence vers ir.attachment)
    attachment_id = fields.Many2one('ir.attachment', string='Pièce jointe', readonly=True)

    description = fields.Text('Description')
    partner_id = fields.Many2one('res.partner', string='Partenaire associé')
    expiry_date = fields.Date('Date d\'expiration')
    amount = fields.Monetary('Montant', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Devise',
                                  default=lambda self: self.env.company.currency_id)

    @api.model
    def create(self, vals):
        """Créer le document et gérer l'attachment"""
        if 'file_data' in vals and vals['file_data']:
            # Calculer la taille du fichier
            file_content = base64.b64decode(vals['file_data'])
            vals['file_size'] = len(file_content)
            
        return super().create(vals)

    def write(self, vals):
        """Mettre à jour le document et gérer l'attachment"""
        if 'file_data' in vals and vals['file_data']:
            # Calculer la taille du fichier
            file_content = base64.b64decode(vals['file_data'])
            vals['file_size'] = len(file_content)
            
        return super().write(vals)

    def action_download_document(self):
        """Action pour télécharger le document"""
        self.ensure_one()
        
        if not self.file_data:
            raise ValidationError(_("Aucun fichier à télécharger."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/construction.document/{self.id}/file_data/{self.filename}?download=true',
            'target': 'self',
        }
