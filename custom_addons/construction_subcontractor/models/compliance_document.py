# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date

class ConstructionComplianceDocument(models.Model):
    """
    Gestion des documents de conformité (Subcontractor Compliance).
    Remplace la logique hardcodée de blg_contacts_extension.
    """
    _name = 'construction.compliance.document'
    _description = 'Document de Conformité'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, id desc'

    name = fields.Char(string='Référence', required=True, copy=False, default='/')
    
    # TYPE DE DOCUMENT (Extensible via sélection ou table séparée si besoin)
    document_type = fields.Selection([
        ('kbis', 'KBIS (Moins de 3 mois)'),
        ('urssaf', 'Attestation URSSAF (Vigilance)'),
        ('insurance_pro', 'Assurance RC Pro'),
        ('insurance_dec', 'Assurance Décennale'),
        ('tax_cert', 'Attestation Fiscale'),
        ('rib', 'RIB Bancaire'),
        ('other', 'Autre')
    ], string='Type de Document', required=True, tracking=True)

    partner_id = fields.Many2one(
        'res.partner', 
        string='Sous-traitant', 
        required=True, 
        ondelete='cascade',
        domain="[('is_subcontractor', '=', True)]"
    )

    # FICHIER
    attachment_id = fields.Many2one('ir.attachment', string='Fichier Joint', tracking=True)
    # Champ binaire pour upload direct si on ne passe pas par ir.attachment
    file_data = fields.Binary(string='Fichier', attachment=True)
    filename = fields.Char(string='Nom du fichier')

    # VALIDITÉ
    issue_date = fields.Date(string='Date d\'émission')
    expiry_date = fields.Date(string='Date d\'expiration', required=True, tracking=True)
    
    # STATUT
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('valid', 'Valide'),
        ('expired', 'Expiré'),
        ('rejected', 'Rejeté')
    ], string='Statut', compute='_compute_state', store=True, tracking=True)
    
    rejection_reason = fields.Text(string='Motif de rejet')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                doc_type = vals.get('document_type', 'DOC').upper()
                vals['name'] = f"{doc_type}-{fields.Date.today()}"
        return super().create(vals_list)

    @api.depends('expiry_date', 'file_data')
    def _compute_state(self):
        today = date.today()
        for doc in self:
            if not doc.file_data:
                doc.state = 'draft'
            elif doc.expiry_date and doc.expiry_date < today:
                doc.state = 'expired'
            else:
                doc.state = 'valid'

    def action_validate_manually(self):
        self.ensure_one()
        if not self.file_data:
            return
            # Raise UserError handled by UI
        self.state = 'valid'

    def check_expiry(self):
        """ Cron Job method to update expired documents """
        expired_docs = self.search([('state', '=', 'valid'), ('expiry_date', '<', date.today())])
        expired_docs.write({'state': 'expired'})
        # Todo: Send email notification to partner
