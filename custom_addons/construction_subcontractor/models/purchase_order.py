# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # =================== LIENS AVEC LES CHANTIERS ===================
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        help="Chantier de construction lié à ce bon de commande",
        tracking=True
    )
    
    # Linked to specific contract?
    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat Sous-traitant',
        domain="[('partner_id', '=', partner_id), ('chantier_id', '=', chantier_id)]"
    )

    lot_ids = fields.Many2many(
        'construction.lot',
        'purchase_order_construction_lot_rel',
        'purchase_order_id',
        'lot_id',
        string='Lots concernés',
        help="Lots de construction concernés par ce bon de commande"
    )

    construction_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('to_approve', 'À approuver'),
        ('purchase', 'Approuvé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État construction', default='draft', tracking=True)

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Mise à jour automatique du partenaire"""
        if self.chantier_id:
            # Si le chantier a des sous-traitants, proposer le premier comme fournisseur par défaut
            # if self.chantier_id.subcontractor_ids and not self.partner_id:
            #    self.partner_id = self.chantier_id.subcontractor_ids[0]
            if self.chantier_id.lot_ids:
                 # Standard logic: filter domains in view, don't auto-set M2M
                 pass

    def action_approve_construction(self):
        self.ensure_one()
        if not self.chantier_id:
             raise ValidationError(_("Ce bon de commande doit être lié à un chantier."))
        self.write({'construction_state': 'purchase', 'state': 'purchase'})
        self.message_post(body=_("Bon de commande approuvé pour le chantier %s") % self.chantier_id.name)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    lot_id = fields.Many2one('construction.lot', string='Lot')
    chantier_id = fields.Many2one('construction.chantier', related='order_id.chantier_id', store=True, readonly=True)
    
    # Location fields
    room_location = fields.Char(string='Localisation')
    floor_level = fields.Char(string='Étage')
    construction_notes = fields.Text(string='Notes construction')

    @api.constrains('lot_id', 'order_id')
    def _check_lot_compatibility(self):
        for record in self:
            if record.lot_id and record.order_id.chantier_id:
                if record.lot_id.chantier_id != record.order_id.chantier_id:
                     # This check might be too strict if reusing lots across phases? 
                     # But a Lot belongs to ONE Chantier. So it must match.
                     raise ValidationError(_("Le lot '%s' n'appartient pas au chantier sélectionné") % record.lot_id.name)
