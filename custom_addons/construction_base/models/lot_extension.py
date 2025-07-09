from odoo import models, fields, api, _

class ConstructionLot(models.Model):
    """Extension du modèle lot pour la construction avec fonctionnalités avancées"""
    
    _name = 'construction.lot'
    _inherit = ['lot', 'mail.thread', 'mail.activity.mixin']
    _description = 'Lot de construction'
    
    # =================== CHAMPS FINANCIERS ===================
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    price = fields.Monetary(
        string='Prix estimé', 
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help="Prix estimé ou contractuel du lot"
    )
    
    # =================== RELATIONS ===================
    
    subcontractor_ids = fields.Many2many(
        'res.partner', 
        string='Sous-traitants',
        domain="[('supplier_rank', '>', 0)]",
        help="Sous-traitants assignés à ce lot"
    )
    
    # =================== ÉTAT ET PROGRESSION ===================
    
    is_finished = fields.Boolean(
        string='Terminé', 
        default=False,
        tracking=True,
        help="Indique si le lot est terminé"
    )
    
    quote_state = fields.Selection([
        ('draft', 'Pas de devis'),
        ('sent', 'Devis envoyé'),
        ('accepted', 'Devis accepté'),
        ('rejected', 'Devis rejeté')
    ], string='Statut devis', default='draft', tracking=True)
    
    # =================== CHAMPS ADDITIONNELS ===================
    
    description = fields.Text(
        string='Description',
        help="Description détaillée du lot de travaux"
    )
    
    notes = fields.Text(
        string='Notes',
        help="Notes internes sur le lot"
    )
    
    # =================== CONTRAINTES ===================
    
    _sql_constraints = [
        ('positive_price', 'CHECK(price >= 0)', 'Le prix doit être positif'),
    ]

