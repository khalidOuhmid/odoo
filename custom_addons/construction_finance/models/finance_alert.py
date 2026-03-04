# -*- coding: utf-8 -*-
"""
Finance Alert Model
====================
Système d'alertes automatiques pour la Tour de Contrôle Financière.
Chaque alerte est générée par un cron job et affichée dans le dashboard.
Les seuils sont configurables via res.config.settings.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ConstructionFinanceAlert(models.Model):
    """
    Alerte financière liée à un chantier.

    Générée automatiquement par le cron `_cron_detect_alerts`.
    Chaque type d'alerte dispose d'une action recommandée pour guider le dirigeant.
    """
    _name = 'construction.finance.alert'
    _description = 'Alerte Financière Chantier'
    _order = 'severity DESC, triggered_at DESC'
    _rec_name = 'message'

    # ============= RELATIONS ============= #
    chantier_id = fields.Many2one(
        'construction.chantier', string='Chantier',
        required=True, ondelete='cascade', index=True
    )

    # ============= TYPE & SÉVÉRITÉ ============= #
    alert_type = fields.Selection([
        ('margin',      '📉 Marge faible'),
        ('overrun',     '💸 Budget dépassé'),
        ('late_invoice','🕐 Facture en retard'),
        ('dependency',  '⚠️ Dépendance sous-traitant'),
        ('no_invoice',  '📋 Chantier sans facturation'),
    ], string='Type d\'alerte', required=True)

    severity = fields.Selection([
        ('warning',  'Attention'),
        ('critical', 'Critique'),
    ], string='Sévérité', required=True, default='warning')

    # ============= CONTENU ============= #
    message = fields.Char('Message', required=True)
    recommended_action = fields.Char(
        'Action recommandée',
        help="Ce que le dirigeant doit faire suite à cette alerte"
    )
    detail_value = fields.Float(
        'Valeur déclenchante',
        help="La valeur numérique qui a déclenché l'alerte (ex: 8.5 pour 8.5% de marge)"
    )
    threshold_value = fields.Float(
        'Seuil configuré',
        help="Le seuil paramétré au moment du déclenchement"
    )

    # ============= ÉTAT ============= #
    triggered_at = fields.Datetime('Déclenchée le', default=fields.Datetime.now, readonly=True)
    is_read = fields.Boolean('Lue', default=False)
    is_resolved = fields.Boolean('Résolue', default=False)
    resolved_at = fields.Datetime('Résolue le', readonly=True)
    resolved_by = fields.Many2one('res.users', 'Résolue par', readonly=True)

    # ============= ACTIONS ============= #
    def action_mark_read(self):
        """Marquer l'alerte comme lue."""
        self.write({'is_read': True})

    def action_resolve(self):
        """Marquer l'alerte comme résolue."""
        self.write({
            'is_resolved': True,
            'resolved_at': fields.Datetime.now(),
            'resolved_by': self.env.uid,
        })

    def action_view_chantier(self):
        """Naviguer directement vers le chantier concerné."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.chantier_id.name,
            'res_model': 'construction.chantier',
            'res_id': self.chantier_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ============= CRON ============= #
    @api.model
    def _cron_detect_alerts(self):
        """
        Détection automatique des alertes financières.
        Exécuté quotidiennement par le cron Odoo.

        Seuils lus depuis res.config.settings (paramétrables par l'admin).
        """
        config = self.env['ir.config_parameter'].sudo()

        # Seuils paramétrables (défauts selon le plan)
        margin_threshold = float(config.get_param('finance.alert.margin_threshold', '15.0'))
        late_invoice_days = int(config.get_param('finance.alert.late_invoice_days', '60'))
        no_invoice_days = int(config.get_param('finance.alert.no_invoice_days', '30'))
        budget_overrun_pct = float(config.get_param('finance.alert.budget_overrun_pct', '10.0'))

        # Lire la vue d'analyse (déjà enrichie)
        analyses = self.env['construction.finance.analysis.report'].search([
            ('chantier_id', '!=', False),
        ])

        created_alerts = []

        for analysis in analyses:
            chantier = analysis.chantier_id
            existing_types = self.search([
                ('chantier_id', '=', chantier.id),
                ('is_resolved', '=', False),
                ('triggered_at', '>=', fields.Datetime.now().replace(hour=0, minute=0, second=0)),
            ]).mapped('alert_type')

            # 1. Alerte marge faible
            if 'margin' not in existing_types and analysis.margin_percent < margin_threshold and analysis.invoiced_revenue > 0:
                severity = 'critical' if analysis.margin_percent < 5 else 'warning'
                created_alerts.append({
                    'chantier_id': chantier.id,
                    'alert_type': 'margin',
                    'severity': severity,
                    'message': f"Marge de {analysis.margin_percent:.1f}% sur {chantier.name}",
                    'recommended_action': "Contacter le chef de chantier pour analyser les surcoûts",
                    'detail_value': analysis.margin_percent,
                    'threshold_value': margin_threshold,
                })

            # 2. Alerte facture en retard (trop longtemps sans facturer)
            if 'no_invoice' not in existing_types and analysis.days_since_last_invoice > no_invoice_days:
                created_alerts.append({
                    'chantier_id': chantier.id,
                    'alert_type': 'no_invoice',
                    'severity': 'warning',
                    'message': f"{chantier.name} : {analysis.days_since_last_invoice} jours sans facture",
                    'recommended_action': "Vérifier l'avancement et émettre la facture d'acompte",
                    'detail_value': analysis.days_since_last_invoice,
                    'threshold_value': no_invoice_days,
                })

            # 3. Alerte dépassement budget
            if 'overrun' not in existing_types and analysis.budget_drift_percent > budget_overrun_pct:
                created_alerts.append({
                    'chantier_id': chantier.id,
                    'alert_type': 'overrun',
                    'severity': 'critical',
                    'message': f"Dépassement budget de {analysis.budget_drift_percent:.1f}% sur {chantier.name}",
                    'recommended_action': "Analyser les commandes fournisseur non planifiées",
                    'detail_value': analysis.budget_drift_percent,
                    'threshold_value': budget_overrun_pct,
                })

        # Créer toutes les alertes en bulk
        if created_alerts:
            self.create(created_alerts)
            _logger.info("Finance alerts created: %d", len(created_alerts))

        # Vérifier les alertes de dépendance sous-traitant séparément
        self._check_subcontractor_dependency_alerts()

        return True

    def _check_subcontractor_dependency_alerts(self):
        """Vérifie la dépendance aux sous-traitants (appel depuis _cron_detect_alerts)."""
        config = self.env['ir.config_parameter'].sudo()
        dependency_threshold = float(
            config.get_param('finance.alert.dependency_threshold', '40.0')
        )

        # Agréger les achats par sous-traitant
        self.env.cr.execute("""
            SELECT
                po.partner_id,
                SUM(po.amount_total) AS total,
                SUM(SUM(po.amount_total)) OVER () AS grand_total
            FROM purchase_order po
            WHERE po.state IN ('purchase','done')
              AND po.chantier_id IS NOT NULL
            GROUP BY po.partner_id
            HAVING SUM(po.amount_total) / SUM(SUM(po.amount_total)) OVER () * 100 > %s
        """, [dependency_threshold])

        risky_partners = self.env.cr.fetchall()

        for partner_id, total, grand_total in risky_partners:
            pct = (total / grand_total * 100) if grand_total else 0
            partner = self.env['res.partner'].browse(partner_id)
            existing = self.search([
                ('alert_type', '=', 'dependency'),
                ('is_resolved', '=', False),
                ('chantier_id.subcontractor_ids', 'in', [partner_id]),
            ], limit=1)
            if not existing:
                # Alerter sur le premier chantier avec ce sous-traitant
                chantier = self.env['construction.chantier'].search([
                    ('subcontractor_ids', 'in', [partner_id])
                ], limit=1)
                if chantier:
                    self.create({
                        'chantier_id': chantier.id,
                        'alert_type': 'dependency',
                        'severity': 'warning',
                        'message': f"{partner.name} représente {pct:.1f}% de vos achats sous-traitance",
                        'recommended_action': f"Diversifier : trouver un 2ème fournisseur pour les lots de {partner.name}",
                        'detail_value': pct,
                        'threshold_value': dependency_threshold,
                    })
