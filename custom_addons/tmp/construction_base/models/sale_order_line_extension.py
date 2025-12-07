from odoo import models, fields, api, _


class SaleOrderLine(models.Model):
    """Extension du modèle sale.order.line pour la gestion des commandes"""
    
    _inherit = 'sale.order.line'
    
    # Champs pour la gestion des commandes
    tracking_link = fields.Char(
        string='Lien de tracking',
        help="Lien de suivi du colis"
    )
    
    order_date = fields.Date(
        string='Date de commande',
        help="Date à laquelle la commande a été passée"
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        domain="[('is_company', '=', True), ('supplier_rank', '>', 0)]",
        help="Fournisseur de cet article"
    )
    
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot associé',
        help="Lot de construction associé à cet article"
    )
    
    @api.model
    def get_common_suppliers(self):
        """Retourne les fournisseurs les plus courants"""
        return [
            'REXEL',
            'LEROY MERLIN', 
            'CASTORAMA',
            'POINT P',
            'CEDEO',
            'GEDIMAT',
            'WELDOM',
            'BRICO DEPOT'
        ]
