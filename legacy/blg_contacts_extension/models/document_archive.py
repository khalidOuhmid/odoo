"""
blg_contacts_extension.models.document_archive
=============================================

This module defines the DocumentArchive model for storing historical versions of
partner documents in BLG Groupe's document management system.

Features:
---------
- Archives previous versions of uploaded documents.
- Stores document type, file, partner, and metadata.
- Provides an action to view archived documents.

Classes:
--------
DocumentArchive (models.Model)
    Stores archived documents with metadata and provides view action.

Fields:
-------
- name: Filename of the archived document.
- document: Binary file content.
- document_type: Type of document (identity card, URSSAF, KBIS, insurance, RIB).
- partner_id: Related partner.
- create_date: Archive date.
- create_uid: User who archived the document.

Author: BLG IT Team
"""

from odoo import models, fields, api

class DocumentArchive(models.Model):
    _name = 'document.archive'
    _description = 'Document Archive'
    _order = 'create_date desc'

    name = fields.Char(string='Nom du fichier', required=True)
    document = fields.Binary(string='Document', attachment=True, required=True)
    document_type = fields.Selection([
        ('identity_card', "Carte d'identité"),
        ('urssaf', 'URSSAF'),
        ('kbis', 'KBIS'),
        ('insurance', 'Assurance'),
        ('rib', 'RIB')
    ], string='Type de document', required=True)
    partner_id = fields.Many2one('res.partner', string='Partenaire', required=True, ondelete='cascade')
    create_date = fields.Datetime(string='Date d\'archivage', readonly=True)
    create_uid = fields.Many2one('res.users', string='Archivé par', readonly=True)
    
    def action_view_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?model=document.archive&field=document&id=%s&filename=%s' % (
                self.id, self.name),
            'target': 'new',
        }
