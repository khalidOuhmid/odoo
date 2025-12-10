# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64

class Document(models.Model):
    _name = "construction.document"
    _description = "Document Chantier"
    _order = "create_date desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ============= Identification ============= #
    name = fields.Char(string="Nom du fichier", required=True, tracking=True)
    
    # ============= Relations ============= #
    chantier_id = fields.Many2one('construction.chantier', string="Chantier", required=True, ondelete='cascade', tracking=True)
    lot_id = fields.Many2one('construction.lot', string="Lot concerné", ondelete='set null')
    chapter_id = fields.Many2one('construction.chapter', string='Chapitre', tracking=True)
    stage_id = fields.Many2one('construction.stage', string='Étape', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Partenaire associé', 
                                  help="Sous-traitant, fournisseur ou client associé au document")
    
    # ============= File Management ============= #
    file_data = fields.Binary(string="Fichier", required=True, attachment=True)
    filename = fields.Char(string='Nom du fichier', required=True)
    file_size = fields.Integer(string='Taille du fichier', readonly=True, help="Taille en bytes")
    
    # ============= Classification ============= #
    document_type = fields.Selection([
        ('quote', 'Devis'),
        ('contract', 'Contrat'),
        ('subcontract', 'Sous-traitance'),
        ('specs', 'Spécifications techniques'),
        ('plan', 'Plan'),
        ('schedule', 'Planning'),
        ('permit', 'Permis'),
        ('invoice', 'Facture'),
        ('photo', 'Photo'),
        ('other', 'Autre')
    ], string='Type de Document', required=True, default='other', tracking=True)
    
    category = fields.Selection([
        ('technical', 'Technique'),
        ('contract', 'Contractuel'),
        ('financial', 'Financier'),
        ('plan', 'Plan'),
        ('photo', 'Photo'),
        ('other', 'Autre')
    ], string="Catégorie", default='technical', required=True)
    
    # ============= Financial & Legal ============= #
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string='Montant', currency_field='currency_id', 
                             help="Montant du contrat/devis si applicable")
    expiry_date = fields.Date(string='Date d\'expiration', 
                              help="Date d'expiration pour permis, contrats, etc.")
    
    # ============= Description ============= #
    description = fields.Text(string="Description")
    
    # ============= Attachment Reference ============= #
    attachment_id = fields.Many2one('ir.attachment', string='Pièce jointe', readonly=True)

    # ============= Lifecycle Hooks ============= #
    @api.model
    def create(self, vals):
        """Create document and calculate file size."""
        if 'file_data' in vals and vals['file_data']:
            file_content = base64.b64decode(vals['file_data'])
            vals['file_size'] = len(file_content)
        return super().create(vals)

    def write(self, vals):
        """Update document and recalculate file size if changed."""
        if 'file_data' in vals and vals['file_data']:
            file_content = base64.b64decode(vals['file_data'])
            vals['file_size'] = len(file_content)
        return super().write(vals)

    def action_download_document(self):
        """Action to download the document."""
        self.ensure_one()
        if not self.file_data:
            raise ValidationError("Aucun fichier à télécharger.")
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/construction.document/{self.id}/file_data/{self.filename}?download=true',
            'target': 'self',
        }
