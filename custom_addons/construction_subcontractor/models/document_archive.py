# -*- coding: utf-8 -*-
"""
Subcontractor Document Archive Model

Stores history of replaced, deleted, or re-requested documents.
Provides full audit trail for compliance purposes.
"""

from odoo import models, fields, api, _


class SubcontractorDocumentArchive(models.Model):
    """Archived document from subcontractor.
    
    When a document is replaced, deleted, or re-requested,
    the old version is stored here for audit purposes.
    """
    _name = 'subcontractor.document.archive'
    _description = 'Archive des Documents Sous-traitant'
    _order = 'archived_date desc'
    
    # ============= CORE FIELDS ============= #
    partner_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    document_type = fields.Selection([
        ('kbis', 'KBIS'),
        ('urssaf', 'Attestation URSSAF'),
        ('insurance_dec', 'Assurance Décennale'),
        ('insurance_pro', 'RC Professionnelle'),
        ('cni', 'Carte d\'Identité (Gérant)'),
        ('rib', 'RIB'),
    ], string='Type de Document', required=True, index=True)
    
    # ============= DOCUMENT DATA ============= #
    file_data = fields.Binary(
        string='Fichier Archivé',
        attachment=True,
        required=True
    )
    
    filename = fields.Char(string='Nom du Fichier')
    
    expiry_date = fields.Date(
        string='Date d\'expiration (originale)'
    )
    
    # ============= AUDIT FIELDS ============= #
    archived_date = fields.Datetime(
        string='Date d\'archivage',
        default=fields.Datetime.now,
        readonly=True,
        index=True
    )
    
    replaced_by_user_id = fields.Many2one(
        'res.users',
        string='Archivé par',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    reason = fields.Selection([
        ('replaced', 'Remplacé par nouveau document'),
        ('deleted', 'Supprimé'),
        ('requested', 'Re-demandé'),
        ('rejected', 'Rejeté'),
        ('expired_cron', 'Expiré (Auto)'),
        ('expiring_cron', 'Expire bientôt (Auto)'),
    ], string='Raison', default='replaced', required=True, index=True)
    
    replaced_by_filename = fields.Char(
        string='Remplacé par',
        help="Nom du nouveau fichier (si remplacé)"
    )
    
    notes = fields.Text(
        string='Notes',
        help="Détails supplémentaires (ex: motif de rejet)"
    )
    
    # ============= VALIDATION STATE AT ARCHIVE TIME ============= #
    was_validated = fields.Boolean(
        string='Était validé',
        help="Le document était-il validé au moment de l'archivage?"
    )
    
    validated_by_name = fields.Char(
        string='Validé par',
        help="Nom du validateur au moment de l'archivage"
    )
    
    original_validated_at = fields.Datetime(
        string='Date de validation originale'
    )
    
    # ============= COMPUTED FIELDS ============= #
    partner_name = fields.Char(
        related='partner_id.name',
        string='Nom du sous-traitant',
        store=True
    )
    
    document_type_display = fields.Char(
        compute='_compute_document_type_display',
        string='Type (affichage)',
        store=True
    )
    
    @api.depends('document_type')
    def _compute_document_type_display(self):
        """Get human-readable doc type name."""
        type_labels = dict(self._fields['document_type'].selection)
        for record in self:
            record.document_type_display = type_labels.get(record.document_type, record.document_type)
    
    # ============= ACTIONS ============= #
    def action_download(self):
        """Download the archived document."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=file_data&filename={self.filename}&download=true',
            'target': 'new',
        }
    
    def action_view_partner(self):
        """Navigate to the partner record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

