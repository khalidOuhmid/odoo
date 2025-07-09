# models/product_template.py
from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots de construction',
        help="Lots de construction où ce produit/service peut être utilisé"
    )

    construction_specialty = fields.Selection([
        ('general', 'Général'),
        ('demolition', 'Démolition'),
        ('maconnerie', 'Maçonnerie'),
        ('platrerie', 'Plâtrerie'),
        ('plomberie_cvc', 'Plomberie CVC'),
        ('electricite', 'Électricité'),
        ('menuiserie_ext', 'Menuiserie extérieure'),
        ('menuiserie_int', 'Menuiserie intérieure'),
        ('peinture', 'Peinture & finition'),
        ('sol', 'Sol souple et parquet'),
        ('carrelage', 'Carrelage & faïence'),
    ], string='Spécialité construction')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    lot_ids = fields.Many2many(related='product_tmpl_id.lot_ids', readonly=False)
    construction_specialty = fields.Selection(related='product_tmpl_id.construction_specialty', readonly=False)

    def action_add_product(self):
        """Ajouter ce produit au wizard de devis actif"""
        # Récupérer le wizard depuis le contexte
        wizard_id = self.env.context.get('wizard_id')
        active_id = self.env.context.get('active_id')
        
        if not wizard_id:
            # Essayer de récupérer depuis le contexte parent si disponible
            wizard_id = self.env.context.get('default_wizard_id')
        
        if wizard_id:
            wizard = self.env['construction.quote.wizard'].browse(wizard_id)
            wizard.with_context(product_id=self.id).action_add_product()
            
            # Recharger la vue wizard
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'construction.quote.wizard',
                'res_id': wizard_id,
                'view_mode': 'form',
                'target': 'new',
            }
        
        return {'type': 'ir.actions.do_nothing'}
