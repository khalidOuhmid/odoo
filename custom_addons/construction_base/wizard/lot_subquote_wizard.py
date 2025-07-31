# -*- coding: utf-8 -*-
"""
Wizard simple pour créer un bon de commande d'achat à partir d'un lot spécifique.
Ce wizard permet de sélectionner un devis principal et de créer automatiquement
un bon de commande pour le lot sélectionné et le sous-traitant.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class LotSubquoteWizard(models.TransientModel):
    """Wizard simple pour créer un bon de commande d'achat à partir d'un lot."""

    _name = 'lot.subquote.wizard'
    _description = 'Création de bon de commande par lot'

    # =================== CHAMPS PRINCIPAUX ===================

    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        required=True,
        readonly=True,
        help="Lot pour lequel créer le bon de commande"
    )

    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True,
        help="Chantier associé"
    )

    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        domain="[('is_subcontractor', '=', True), ('supplier_rank', '>', 0)]",
        help="Sous-traitant qui recevra le bon de commande"
    )

    available_quotes = fields.Many2many(
        'sale.order',
        string='Devis disponibles',
        compute='_compute_available_quotes',
        help="Devis confirmés disponibles pour ce chantier"
    )

    selected_quote_id = fields.Many2one(
        'sale.order',
        string='Devis source',
        required=True,
        domain="[('chantier_id', '=', chantier_id), ('state', 'in', ['draft', 'sent', 'sale'])]",
        help="Devis principal dont extraire les éléments pour ce lot"
    )

    # =================== CHAMPS D'APERÇU ===================

    preview_lines = fields.Html(
        string='Aperçu du contenu',
        compute='_compute_preview',
        help="Aperçu des lignes qui seront extraites du devis"
    )

    estimated_amount = fields.Monetary(
        string='Montant estimé',
        compute='_compute_preview',
        currency_field='currency_id',
        help="Montant estimé du bon de commande"
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # =================== COMPUTED FIELDS ===================

    @api.depends('chantier_id')
    def _compute_available_quotes(self):
        """Calculer les devis disponibles pour ce chantier."""
        for wizard in self:
            if wizard.chantier_id:
                quotes = self.env['sale.order'].search([
                    ('chantier_id', '=', wizard.chantier_id.id),
                    ('state', 'in', ['draft', 'sent', 'sale'])
                ])
                wizard.available_quotes = quotes
            else:
                wizard.available_quotes = False

    @api.depends('selected_quote_id', 'lot_id')
    def _compute_preview(self):
        """Calculer l'aperçu du contenu du bon de commande."""
        for wizard in self:
            if wizard.selected_quote_id and wizard.lot_id:
                lines_info = wizard._analyze_quote_for_lot()
                wizard.preview_lines = wizard._generate_preview_html(lines_info)
                wizard.estimated_amount = lines_info.get('total_amount', 0.0)
            else:
                wizard.preview_lines = "<p>Sélectionnez un devis pour voir l'aperçu.</p>"
                wizard.estimated_amount = 0.0

    # =================== MÉTHODES D'ANALYSE ===================

    def _analyze_quote_for_lot(self):
        """Analyser le devis pour extraire les éléments liés à ce lot."""
        self.ensure_one()

        quote = self.selected_quote_id
        lot = self.lot_id

        # Rechercher les sections et lignes liées à ce lot
        related_lines = []
        current_section = None
        total_amount = 0.0

        # Identifier les sections liées au lot
        lot_keywords = [lot.name.lower(), lot.code.lower() if lot.code else '']
        lot_keywords = [kw for kw in lot_keywords if kw]  # Supprimer les chaînes vides

        for line in quote.order_line.sorted('sequence'):

            if line.display_type == 'line_section':
                # Vérifier si cette section correspond au lot
                section_name = line.name.lower() if line.name else ''
                if any(keyword in section_name for keyword in lot_keywords):
                    current_section = line
                    related_lines.append(line)
                else:
                    current_section = None

            elif current_section and not line.display_type:
                # Ligne de produit dans une section du lot
                related_lines.append(line)
                total_amount += line.price_subtotal

            elif not current_section and not line.display_type:
                # Ligne de produit sans section - vérifier si elle correspond au lot
                if line.product_id and self._is_product_for_lot(line.product_id, lot):
                    related_lines.append(line)
                    total_amount += line.price_subtotal

        return {
            'lines': related_lines,
            'total_amount': total_amount,
            'line_count': len([l for l in related_lines if not l.display_type])
        }

    def _is_product_for_lot(self, product, lot):
        """Déterminer si un produit correspond à un lot."""
        if not product:
            return False

        # Logique simple basée sur les mots-clés
        product_text = (product.name + ' ' + (product.categ_id.name or '')).lower()
        lot_keywords = [lot.name.lower()]
        if lot.code:
            lot_keywords.append(lot.code.lower())

        return any(keyword in product_text for keyword in lot_keywords)

    def _generate_preview_html(self, lines_info):
        """Générer l'aperçu HTML des lignes."""
        if not lines_info['lines']:
            return "<div class='alert alert-warning'>Aucune ligne trouvée pour ce lot dans le devis sélectionné.</div>"

        html = ["<div class='lot_purchase_preview'>"]
        html.append("<h5>🛒 Contenu détecté pour le lot '{}' :</h5>".format(self.lot_id.name))
        html.append("<table class='table table-sm'>")
        html.append("<thead><tr><th>Type</th><th>Description</th><th>Qté</th><th>Montant</th></tr></thead>")
        html.append("<tbody>")

        for line in lines_info['lines']:
            if line.display_type == 'line_section':
                html.append("<tr class='table-info'>")
                html.append("<td><strong>Section</strong></td>")
                html.append("<td><strong>{}</strong></td>".format(line.name))
                html.append("<td>-</td><td>-</td>")
                html.append("</tr>")
            elif not line.display_type:
                html.append("<tr>")
                html.append("<td>Produit</td>")
                html.append("<td>{}</td>".format(line.name))
                html.append("<td>{}</td>".format(line.product_uom_qty))
                html.append("<td>{:,.2f} {}</td>".format(line.price_subtotal, line.currency_id.symbol))
                html.append("</tr>")

        html.append("</tbody></table>")
        html.append("<p><strong>Total estimé : {:,.2f} {}</strong></p>".format(lines_info['total_amount'], self.currency_id.symbol))
        html.append("</div>")

        return "".join(html)

    # =================== ACTIONS ===================

    def action_create_purchase_order(self):
        """Créer le bon de commande pour le lot."""
        self.ensure_one()

        if not self.selected_quote_id:
            raise ValidationError(_("Veuillez sélectionner un devis source."))

        # Analyser le contenu à extraire
        lines_info = self._analyze_quote_for_lot()

        if not lines_info['lines']:
            raise ValidationError(_(
                "Aucun contenu trouvé pour le lot '%s' dans le devis sélectionné."
            ) % self.lot_id.name)

        # Créer le bon de commande
        purchase_order = self._create_purchase_order(lines_info)

        # S'assurer que le bon de commande est bien créé et enregistré dans la base de données
        self.env.cr.commit()

        # Log sur le chantier
        self.chantier_id.message_post(
            body=f"🛒 Bon de commande créé pour le lot '{self.lot_id.name}' :\n"
                 f"• BC : {purchase_order.name}\n"
                 f"• Sous-traitant : {self.subcontractor_id.name}\n"
                 f"• Montant : {purchase_order.amount_total:,.2f} {purchase_order.currency_id.symbol}\n"
                 f"• Basé sur : {self.selected_quote_id.name}",
            message_type='comment'
        )

        # Afficher une notification de succès et ouvrir le bon de commande créé
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _(f"Le bon de commande pour le lot '{self.lot_id.name}' a été créé avec succès."),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': f'Bon de commande - {self.lot_id.name}',
                    'res_model': 'purchase.order',
                    'res_id': purchase_order.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            }
        }

    def _create_purchase_order(self, lines_info):
        """Créer le bon de commande avec les lignes extraites."""
        # Valeurs du bon de commande
        purchase_vals = {
            'partner_id': self.subcontractor_id.id,
            'chantier_id': self.chantier_id.id,
            'lot_ids': [(6, 0, [self.lot_id.id])],
            'origin': self.selected_quote_id.name,
            'state': 'draft',
            'date_order': fields.Datetime.now(),
            'company_id': self.selected_quote_id.company_id.id,
            'currency_id': self.selected_quote_id.currency_id.id,
            'notes': f"Bon de commande généré automatiquement pour le lot : {self.lot_id.name}",
        }

        # Créer le bon de commande
        purchase_order = self.env['purchase.order'].create(purchase_vals)

        # Ajouter les lignes
        sequence = 10
        for line in lines_info['lines']:
            # Ne créer que les lignes de produit (pas les sections)
            if not line.display_type and line.product_id:
                line_vals = self._prepare_purchase_line(line, purchase_order, sequence)
                self.env['purchase.order.line'].create(line_vals)
                sequence += 10

        return purchase_order

    def _prepare_purchase_line(self, original_line, purchase_order, sequence):
        """Préparer les valeurs d'une ligne de bon de commande."""
        vals = {
            'order_id': purchase_order.id,
            'sequence': sequence,
            'display_type': original_line.display_type,
            'name': original_line.name,
        }

        if not original_line.display_type:
            # Ligne de produit
            vals.update({
                'product_id': original_line.product_id.id,
                'product_qty': original_line.product_uom_qty or 1.0,  # Valeur par défaut si None
                'product_uom': original_line.product_uom.id,
                'price_unit': original_line.price_unit or 0.0,
                'taxes_id': [(6, 0, original_line.tax_id.ids)],
                # Note: discount n'existe pas dans purchase.order.line
            })

            # Copier les champs construction spécifiques si ils existent
            construction_fields = ['room_location', 'floor_level', 'construction_notes']
            for field in construction_fields:
                if hasattr(original_line, field):
                    value = getattr(original_line, field)
                    if value:
                        vals[field] = value

        return vals

    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut depuis le contexte."""
        defaults = super().default_get(fields_list)

        # Récupérer les valeurs du contexte
        for field in ['lot_id', 'chantier_id', 'subcontractor_id']:
            context_key = f'default_{field}'
            if context_key in self.env.context:
                defaults[field] = self.env.context[context_key]

        return defaults
