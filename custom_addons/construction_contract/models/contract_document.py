# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ContractDocument(models.Model):
    _name = 'contract.document'
    _description = 'Contractual document attached to a contract'

    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        required=True,
        ondelete='cascade'
    )
    
    document_type = fields.Selection([
        ('cctp', 'CCTP'),
        ('planning_lot', 'Planning du Lot'),
        ('planning_general', 'Planning Général'),
        ('bon_de_commande', 'Bon de Commande'),
        ('autre', 'Autre')
    ], string='Type de Document', required=True)
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot Concerné'
    )
    
    attachment_id = fields.Many2one(
        'ir.attachment',
        string='Fichier (PDF)',
        ondelete='cascade'
    )
    
    is_auto_attached = fields.Boolean(
        string='Généré Automatiquement',
        default=False
    )
    
    state = fields.Selection([
        ('present', 'Présent'),
        ('missing', 'Manquant'),
        ('expired', 'Expiré')
    ], string='Statut', compute='_compute_state', store=True)

    @api.depends('attachment_id')
    def _compute_state(self):
        for doc in self:
            if doc.attachment_id:
                doc.state = 'present'
            else:
                doc.state = 'missing'
