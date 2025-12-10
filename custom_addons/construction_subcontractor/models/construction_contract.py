# -*- coding: utf-8 -*-
"""
Construction Contract Model

Manages contracts between the company and subcontractors.
Linked to chantiers and lots with digital signature support.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class ConstructionContract(models.Model):
    """
    Construction Contract for Subcontractors.
    
    A contract consolidates all work packages (lots) assigned to a subcontractor
    for a specific construction site. Follows PLM stage philosophy.
    """
    _name = 'construction.contract'
    _description = 'Contrat Sous-traitant'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc'

    # ============= IDENTIFICATION ============= #
    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nouveau')
    )
    
    # ============= PARTIES ============= #
    partner_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        domain="[('is_subcontractor', '=', True)]",
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        required=True
    )
    
    # ============= CHANTIER & LOTS ============= #
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        tracking=True
    )
    lot_ids = fields.Many2many(
        'construction.lot',
        'contract_lot_rel',
        'contract_id', 'lot_id',
        string='Lots concernés',
        domain="[('chantier_id', '=', chantier_id)]"
    )
    lot_names = fields.Char(
        compute='_compute_lot_names',
        string='Lots'
    )
    
    # ============= DATES ============= #
    date_start = fields.Date(string='Date de début', tracking=True)
    date_end = fields.Date(string='Date de fin', tracking=True)
    signature_date = fields.Date(string='Date de signature', readonly=True)
    
    # ============= FINANCIALS ============= #
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id
    )
    amount_total = fields.Monetary(
        string='Montant total',
        currency_field='currency_id',
        compute='_compute_amount_total',
        store=True
    )
    retention_percentage = fields.Float(
        string='Retenue de garantie (%)',
        default=5.0,
        help="Pourcentage retenu jusqu'à la fin de la période de garantie"
    )
    
    # ============= STATE ============= #
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('signed', 'Signé'),
        ('active', 'En cours'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True, required=True)
    
    # ============= SIGNATURE ============= #
    signature = fields.Binary(string='Signature')
    signed_by = fields.Char(string='Signé par')
    signature_token = fields.Char(string='Jeton de signature', copy=False)
    
    # ============= PURCHASE ORDERS ============= #
    purchase_order_ids = fields.One2many(
        'purchase.order', 'contract_id',
        string='Bons de commande'
    )
    purchase_order_count = fields.Integer(
        compute='_compute_purchase_order_count'
    )
    
    # ============= NOTES ============= #
    notes = fields.Html(string='Conditions particulières')
    
    # ============= COMPUTED ============= #
    
    @api.depends('lot_ids')
    def _compute_lot_names(self):
        for contract in self:
            contract.lot_names = ', '.join(contract.lot_ids.mapped('name'))
    
    @api.depends('lot_ids.price')
    def _compute_amount_total(self):
        for contract in self:
            contract.amount_total = sum(contract.lot_ids.mapped('price'))
    
    def _compute_purchase_order_count(self):
        for contract in self:
            contract.purchase_order_count = len(contract.purchase_order_ids)
    
    # ============= CRUD ============= #
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.contract') or _('Nouveau')
        return super().create(vals_list)
    
    # ============= ACTIONS ============= #
    
    def action_send_for_signature(self):
        """Send contract to subcontractor for signature."""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Seuls les contrats brouillon peuvent être envoyés."))
        
        # Check subcontractor compliance
        is_compliant, message = self.partner_id.is_compliant_for_stage('DA')
        if not is_compliant:
            raise UserError(_(
                "Le sous-traitant n'est pas conforme:\n%s\n\n"
                "Veuillez régulariser la situation avant d'envoyer le contrat."
            ) % message)
        
        # Generate signature token
        import secrets
        self.signature_token = secrets.token_urlsafe(32)
        self.state = 'sent'
        
        # Post notification
        self.message_post(
            body=_("📤 Contrat envoyé au sous-traitant pour signature"),
            message_type='notification'
        )
        
        # TODO: Send email with signature link
        return True
    
    def action_mark_signed(self):
        """Mark contract as signed (manual or portal)."""
        self.ensure_one()
        
        if self.state != 'sent':
            raise UserError(_("Le contrat doit être en état 'Envoyé' pour être signé."))
        
        self.write({
            'state': 'signed',
            'signature_date': fields.Date.today(),
        })
        
        self.message_post(
            body=_("✅ Contrat signé le %s") % fields.Date.today(),
            message_type='notification'
        )
        return True
    
    def action_activate(self):
        """Activate the contract (work can begin)."""
        self.ensure_one()
        
        if self.state != 'signed':
            raise UserError(_("Le contrat doit être signé pour être activé."))
        
        self.state = 'active'
        self.message_post(
            body=_("🚀 Contrat activé - les travaux peuvent commencer"),
            message_type='notification'
        )
        return True
    
    def action_complete(self):
        """Mark contract as completed."""
        self.ensure_one()
        self.state = 'done'
        self.message_post(
            body=_("✅ Contrat terminé"),
            message_type='notification'
        )
        return True
    
    def action_cancel(self):
        """Cancel the contract."""
        self.ensure_one()
        if self.state in ('active', 'done'):
            raise UserError(_("Impossible d'annuler un contrat actif ou terminé."))
        self.state = 'cancelled'
        return True
    
    def action_view_purchase_orders(self):
        """View linked purchase orders."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bons de commande - %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {
                'default_contract_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_chantier_id': self.chantier_id.id,
            },
        }
    
    # ============= PORTAL ============= #
    
    def _compute_access_url(self):
        super()._compute_access_url()
        for contract in self:
            contract.access_url = f'/my/contracts/{contract.id}'


class PurchaseOrder(models.Model):
    """Extend purchase order to link to contract."""
    _inherit = 'purchase.order'
    
    contract_id = fields.Many2one(
        'construction.contract',
        string='Contrat',
        help="Contrat sous-traitant associé"
    )
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        related='contract_id.chantier_id',
        store=True,
        readonly=False
    )
