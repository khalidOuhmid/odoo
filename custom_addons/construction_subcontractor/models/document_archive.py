# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SubcontractorDocumentArchive(models.Model):
    _name = 'subcontractor.document.archive'
    _description = 'Archive des Documents Sous-traitant'
    _order = 'archived_date desc'

    partner_id = fields.Many2one('res.partner', string='Sous-traitant', required=True, ondelete='cascade')
    document_type = fields.Selection([
        ('kbis', 'KBIS'),
        ('urssaf', 'Attestation URSSAF'),
        ('insurance_dec', 'Assurance Décennale'),
        ('cni', 'Carte d\'Identité'),
        ('insurance_pro', 'Assurance RC Pro'),
        ('rib', 'RIB'),
    ], string='Type de Document', required=True)
    
    file_data = fields.Binary(string='Fichier Archivé', attachment=True, required=True)
    filename = fields.Char(string='Nom du Fichier')
    archived_date = fields.Datetime(string='Date d\'archivage', default=fields.Datetime.now, readonly=True)
    replaced_by_user_id = fields.Many2one('res.users', string='Remplacé par', default=lambda self: self.env.user, readonly=True)
    
    expiry_date = fields.Date(string='Date d\'expiration (au moment de l\'archive)')
