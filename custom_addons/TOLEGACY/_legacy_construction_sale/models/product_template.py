# models/product_template.py
from odoo import models, fields, _


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

    def action_open_edit_modal(self):
        """Open this product in a modal form for editing from wizards/lists."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Product - %s') % (self.display_name or self.name),
            'res_model': 'product.product',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_categ_id': self.categ_id.id,
            },
        }

    def action_open_product_in_new_tab(self):
        """Open the product in a new browser tab to avoid closing the wizard modal."""
        self.ensure_one()
        url = '/web#id=%d&model=product.product&view_type=form' % self.id
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

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
