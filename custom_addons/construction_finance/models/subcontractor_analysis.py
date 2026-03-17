# -*- coding: utf-8 -*-
"""
Subcontractor Analysis — SQL View
===================================
Vue SQL agrégeant les achats par sous-traitant pour la Tour de Contrôle.

Réponse aux questions :
  - Qui travaille sur le plus de chantiers ?
  - Qui me facture le plus en cumulé ?
  - Suis-je trop dépendant d'un seul sous-traitant ?
"""
from odoo import tools, models, fields, api
import logging
_logger = logging.getLogger(__name__)


class ConstructionSubcontractorAnalysis(models.Model):
    """
    Vue SQL : analyse des achats par sous-traitant.

    Chaque ligne = un sous-traitant avec ses indicateurs agrégés.
    Calculé sur les commandes fournisseur confirmées (state IN purchase, done).
    """
    _name = 'construction.subcontractor.analysis'
    _description = 'Analyse Sous-Traitants'
    _auto = False
    _order = 'total_facture DESC'
    _rec_name = 'partner_id'

    # ============= DIMENSIONS ============= #
    partner_id = fields.Many2one('res.partner', 'Sous-Traitant', readonly=True)
    company_id = fields.Many2one('res.company', 'Société', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Devise', readonly=True)

    # ============= MESURES ============= #
    nb_chantiers = fields.Integer('Nb Chantiers', readonly=True,
                                  help="Nombre de chantiers sur lesquels ce sous-traitant intervient")
    nb_orders = fields.Integer('Nb Commandes', readonly=True,
                               help="Nombre de bons de commande envoyés à ce sous-traitant")
    total_facture = fields.Monetary('Total Facturé (€)', readonly=True,
                                    help="Montant total des commandes confirmées")
    pct_volume_total = fields.Float('Volume Total (%)', readonly=True,
                                    group_operator=False,
                                    help="Part de ce sous-traitant dans le volume total achats")
    is_high_dependency = fields.Boolean('Dépendance élevée', readonly=True,
                                        help="Vrai si ce sous-traitant représente > 40% du volume total")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """
            CREATE OR REPLACE VIEW {table} AS (
                WITH
                -- Total global par entreprise (denominateur pour dependance)
                total_global AS (
                    SELECT
                        company_id,
                        SUM(amount_total) AS grand_total
                    FROM purchase_order
                    WHERE state IN ('purchase','done')
                    GROUP BY company_id
                ),
                -- Agregation par sous-traitant
                agg AS (
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY po.partner_id) AS id,
                        po.partner_id,
                        po.company_id,
                        -- On prend la devise de la 1ere commande (simplification)
                        MIN(po.currency_id) AS currency_id,
                        COUNT(DISTINCT po.chantier_id) AS nb_chantiers,
                        COUNT(po.id)                   AS nb_orders,
                        SUM(po.amount_total)           AS total_facture
                    FROM purchase_order po
                    WHERE po.state IN ('purchase','done')
                      AND po.partner_id IS NOT NULL
                    GROUP BY po.partner_id, po.company_id
                )
                SELECT
                    a.id,
                    a.partner_id,
                    a.company_id,
                    a.currency_id,
                    a.nb_chantiers,
                    a.nb_orders,
                    a.total_facture,
                    -- part du volume global
                    CASE
                        WHEN tg.grand_total > 0
                        THEN ROUND((a.total_facture / tg.grand_total * 100)::numeric, 1)
                        ELSE 0
                    END AS pct_volume_total,
                    -- Alerte dependance (seuil 40)
                    CASE
                        WHEN tg.grand_total > 0
                         AND (a.total_facture / tg.grand_total * 100) > 40
                        THEN TRUE
                        ELSE FALSE
                    END AS is_high_dependency
                FROM agg a
                LEFT JOIN total_global tg ON tg.company_id = a.company_id
            )
        """.format(table=self._table)
        try:
            self.env.cr.execute(query)
        except Exception as e:
            _logger.error("Error in subcontractor_analysis.init: %s", e)
            _logger.error("Query was: %s", query)
            raise

    # ============= ACTIONS ============= #
    def action_view_purchase_orders(self):
        """Voir toutes les commandes de ce sous-traitant."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Commandes — {self.partner_id.name}',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id),
                       ('state', 'in', ['purchase', 'done'])],
        }
