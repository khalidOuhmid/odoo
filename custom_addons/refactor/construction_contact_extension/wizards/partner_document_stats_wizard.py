# -*- coding: utf-8 -*-
"""
Assistant pour les statistiques documentaires d'un partenaire
============================================================

Affiche des statistiques détaillées sur l'état des documents d'un partenaire.
"""

from odoo import models, fields, api
from odoo.addons.construction_core.utils.helpers import DateHelper, FormatHelper
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class PartnerDocumentStatsWizard(models.TransientModel):
    """Statistiques documentaires détaillées d'un partenaire"""

    _name = 'partner.document.stats.wizard'
    _description = 'Statistiques Documents Partenaire'

    # =================== CHAMPS PRINCIPAUX ===================

    partner_id = fields.Many2one(
        'res.partner',
        string='Partenaire',
        required=True,
        readonly=True
    )

    # Scores généraux
    health_score = fields.Float(
        string='Score de santé documentaire',
        readonly=True,
        help="Score global de santé documentaire (0-100)"
    )

    completion_rate = fields.Float(
        string='Taux de complétion (%)',
        readonly=True,
        help="Pourcentage de documents valides"
    )

    reliability_score = fields.Float(
        string='Score de fiabilité',
        readonly=True,
        help="Score de fiabilité du partenaire"
    )

    # =================== STATISTIQUES DÉTAILLÉES ===================

    total_documents = fields.Integer(
        string='Total documents',
        compute='_compute_detailed_stats',
        help="Nombre total de documents"
    )

    valid_documents = fields.Integer(
        string='Documents valides',
        compute='_compute_detailed_stats'
    )

    expired_documents = fields.Integer(
        string='Documents expirés',
        compute='_compute_detailed_stats'
    )

    expiring_documents = fields.Integer(
        string='Documents expirant',
        compute='_compute_detailed_stats'
    )

    rejected_documents = fields.Integer(
        string='Documents rejetés',
        compute='_compute_detailed_stats'
    )

    missing_documents = fields.Integer(
        string='Documents manquants',
        compute='_compute_detailed_stats'
    )

    to_check_documents = fields.Integer(
        string='Documents à vérifier',
        compute='_compute_detailed_stats'
    )

    # =================== ANALYSE TEMPORELLE ===================

    first_upload_date = fields.Datetime(
        string='Premier upload',
        compute='_compute_temporal_stats',
        help="Date du premier upload de document"
    )

    last_upload_date = fields.Datetime(
        string='Dernier upload',
        compute='_compute_temporal_stats',
        help="Date du dernier upload"
    )

    uploads_last_30_days = fields.Integer(
        string='Uploads (30 jours)',
        compute='_compute_temporal_stats',
        help="Nombre d'uploads dans les 30 derniers jours"
    )

    uploads_last_90_days = fields.Integer(
        string='Uploads (90 jours)',
        compute='_compute_temporal_stats',
        help="Nombre d'uploads dans les 90 derniers jours"
    )

    average_processing_days = fields.Float(
        string='Délai moyen de traitement (jours)',
        compute='_compute_temporal_stats',
        help="Délai moyen entre upload et validation"
    )

    # =================== PROCHAINES ÉCHÉANCES ===================

    next_expiry_date = fields.Date(
        string='Prochaine expiration',
        compute='_compute_expiry_analysis',
        help="Date de la prochaine expiration"
    )

    next_expiry_document = fields.Char(
        string='Document expirant',
        compute='_compute_expiry_analysis',
        help="Nom du prochain document à expirer"
    )

    expiry_within_30_days = fields.Integer(
        string='Expirations (30 jours)',
        compute='_compute_expiry_analysis',
        help="Nombre de documents expirant dans 30 jours"
    )

    expiry_within_60_days = fields.Integer(
        string='Expirations (60 jours)',
        compute='_compute_expiry_analysis'
    )

    expiry_within_90_days = fields.Integer(
        string='Expirations (90 jours)',
        compute='_compute_expiry_analysis'
    )

    # =================== ANALYSE PAR TYPE ===================

    document_type_stats = fields.Text(
        string='Statistiques par type',
        compute='_compute_type_analysis',
        help="Répartition par type de document"
    )

    mandatory_docs_complete = fields.Boolean(
        string='Documents obligatoires complets',
        compute='_compute_type_analysis'
    )

    optional_docs_uploaded = fields.Integer(
        string='Documents optionnels uploadés',
        compute='_compute_type_analysis'
    )

    # =================== ALERTES ET RECOMMANDATIONS ===================

    alerts_count = fields.Integer(
        string='Nombre d\'alertes',
        compute='_compute_alerts_and_recommendations'
    )

    alerts_text = fields.Html(
        string='Alertes',
        compute='_compute_alerts_and_recommendations'
    )

    recommendations_text = fields.Html(
        string='Recommandations',
        compute='_compute_alerts_and_recommendations'
    )

    # =================== MÉTHODES CALCULÉES ===================

    @api.depends('partner_id')
    def _compute_detailed_stats(self):
        """Calcule les statistiques détaillées"""
        for wizard in self:
            if not wizard.partner_id:
                # Initialiser à zéro
                for field in ['total_documents', 'valid_documents', 'expired_documents',
                              'expiring_documents', 'rejected_documents', 'missing_documents',
                              'to_check_documents']:
                    setattr(wizard, field, 0)
                continue

            # Récupérer tous les documents du partenaire
            all_docs = wizard.partner_id.document_ids

            wizard.total_documents = len(all_docs)
            wizard.valid_documents = len(all_docs.filtered(lambda d: d.state == 'valid'))
            wizard.expired_documents = len(all_docs.filtered(lambda d: d.state == 'expired'))
            wizard.expiring_documents = len(all_docs.filtered(lambda d: d.state == 'expiring'))
            wizard.rejected_documents = len(all_docs.filtered(lambda d: d.state == 'rejected'))
            wizard.missing_documents = len(all_docs.filtered(lambda d: d.state == 'missing'))
            wizard.to_check_documents = len(all_docs.filtered(lambda d: d.state == 'to_check'))

    @api.depends('partner_id')
    def _compute_temporal_stats(self):
        """Calcule les statistiques temporelles"""
        for wizard in self:
            if not wizard.partner_id:
                wizard.first_upload_date = False
                wizard.last_upload_date = False
                wizard.uploads_last_30_days = 0
                wizard.uploads_last_90_days = 0
                wizard.average_processing_days = 0.0
                continue

            docs = wizard.partner_id.document_ids.filtered('upload_date')

            if docs:
                wizard.first_upload_date = min(docs.mapped('upload_date'))
                wizard.last_upload_date = max(docs.mapped('upload_date'))
            else:
                wizard.first_upload_date = False
                wizard.last_upload_date = False

            # Uploads récents
            cutoff_30 = fields.Datetime.now() - timedelta(days=30)
            cutoff_90 = fields.Datetime.now() - timedelta(days=90)

            wizard.uploads_last_30_days = len(docs.filtered(lambda d: d.upload_date >= cutoff_30))
            wizard.uploads_last_90_days = len(docs.filtered(lambda d: d.upload_date >= cutoff_90))

            # Délai moyen de traitement
            validated_docs = docs.filtered(lambda d: d.validation_date and d.upload_date)
            if validated_docs:
                total_days = sum(
                    (doc.validation_date - doc.upload_date).days
                    for doc in validated_docs
                )
                wizard.average_processing_days = total_days / len(validated_docs)
            else:
                wizard.average_processing_days = 0.0

    @api.depends('partner_id')
    def _compute_expiry_analysis(self):
        """Calcule l'analyse des expirations"""
        for wizard in self:
            if not wizard.partner_id:
                wizard.next_expiry_date = False
                wizard.next_expiry_document = ""
                wizard.expiry_within_30_days = 0
                wizard.expiry_within_60_days = 0
                wizard.expiry_within_90_days = 0
                continue

            docs_with_expiry = wizard.partner_id.document_ids.filtered('expiry_date')
            future_docs = docs_with_expiry.filtered(lambda d: d.expiry_date >= date.today())

            if future_docs:
                next_doc = min(future_docs, key=lambda d: d.expiry_date)
                wizard.next_expiry_date = next_doc.expiry_date
                wizard.next_expiry_document = next_doc.document_type_id.name
            else:
                wizard.next_expiry_date = False
                wizard.next_expiry_document = ""

            # Compter les expirations par période
            today = date.today()
            wizard.expiry_within_30_days = len(future_docs.filtered(
                lambda d: d.expiry_date <= today + timedelta(days=30)
            ))
            wizard.expiry_within_60_days = len(future_docs.filtered(
                lambda d: d.expiry_date <= today + timedelta(days=60)
            ))
            wizard.expiry_within_90_days = len(future_docs.filtered(
                lambda d: d.expiry_date <= today + timedelta(days=90)
            ))

    @api.depends('partner_id')
    def _compute_type_analysis(self):
        """Calcule l'analyse par type de document"""
        for wizard in self:
            if not wizard.partner_id:
                wizard.document_type_stats = ""
                wizard.mandatory_docs_complete = False
                wizard.optional_docs_uploaded = 0
                continue

            # Statistiques par type
            type_stats = []
            all_types = wizard.partner_id.document_ids.mapped('document_type_id')

            for doc_type in all_types:
                type_docs = wizard.partner_id.document_ids.filtered(
                    lambda d: d.document_type_id == doc_type
                )
                valid_count = len(type_docs.filtered(lambda d: d.state == 'valid'))
                total_count = len(type_docs)

                type_stats.append(f"{doc_type.name}: {valid_count}/{total_count}")

            wizard.document_type_stats = "\n".join(type_stats)

            # Documents obligatoires
            mandatory_types = wizard.env['document.type'].search([
                ('is_mandatory', '=', True),
                ('active', '=', True)
            ])

            mandatory_docs_valid = all(
                any(
                    doc.document_type_id == mtype and doc.state == 'valid'
                    for doc in wizard.partner_id.document_ids
                )
                for mtype in mandatory_types
            )
            wizard.mandatory_docs_complete = mandatory_docs_valid

            # Documents optionnels
            optional_types = wizard.env['document.type'].search([
                ('is_mandatory', '=', False),
                ('active', '=', True)
            ])
            wizard.optional_docs_uploaded = len([
                otype for otype in optional_types
                if any(
                    doc.document_type_id == otype and doc.file_content
                    for doc in wizard.partner_id.document_ids
                )
            ])

    @api.depends('partner_id', 'expired_documents', 'expiring_documents', 'missing_documents')
    def _compute_alerts_and_recommendations(self):
        """Calcule les alertes et recommandations"""
        for wizard in self:
            alerts = []
            recommendations = []

            if not wizard.partner_id:
                wizard.alerts_count = 0
                wizard.alerts_text = ""
                wizard.recommendations_text = ""
                continue

            # Alertes
            if wizard.expired_documents > 0:
                alerts.append(f"🚨 {wizard.expired_documents} document(s) expiré(s)")

            if wizard.expiring_documents > 0:
                alerts.append(f"⚠️ {wizard.expiring_documents} document(s) expire(nt) bientôt")

            if wizard.missing_documents > 0:
                alerts.append(f"❌ {wizard.missing_documents} document(s) manquant(s)")

            if wizard.completion_rate < 50:
                alerts.append("📉 Taux de complétion très faible")

            if wizard.health_score < 30:
                alerts.append("🏥 Score de santé critique")

            # Recommandations
            if wizard.to_check_documents > 0:
                recommendations.append(f"✅ Valider les {wizard.to_check_documents} document(s) en attente")

            if wizard.expiry_within_30_days > 0:
                recommendations.append("📅 Planifier le renouvellement des documents expirant")

            if wizard.uploads_last_90_days == 0:
                recommendations.append("📤 Encourager l'upload de nouveaux documents")

            if not wizard.mandatory_docs_complete:
                recommendations.append("📋 Compléter les documents obligatoires")

            if wizard.average_processing_days > 7:
                recommendations.append("⚡ Accélérer le processus de validation")

            wizard.alerts_count = len(alerts)
            wizard.alerts_text = "<br/>".join(alerts) if alerts else "Aucune alerte"
            wizard.recommendations_text = "<br/>".join(recommendations) if recommendations else "Aucune recommandation"

    # =================== ACTIONS ===================

    def action_view_documents(self):
        """Affiche tous les documents du partenaire"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Documents - {self.partner_id.name}',
            'res_model': 'partner.document',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {
                'default_partner_id': self.partner_id.id,
                'search_default_group_by_state': 1
            }
        }

    def action_view_expired_documents(self):
        """Affiche les documents expirés"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Documents expirés - {self.partner_id.name}',
            'res_model': 'partner.document',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('state', '=', 'expired')
            ]
        }

    def action_view_expiring_documents(self):
        """Affiche les documents expirant bientôt"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Documents expirant - {self.partner_id.name}',
            'res_model': 'partner.document',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                ('state', '=', 'expiring')
            ]
        }

    def action_send_reminder(self):
        """Envoie un rappel au partenaire"""
        self.ensure_one()

        if self.alerts_count == 0:
            from odoo.addons.construction_core.utils.helpers import NotificationHelper
            return NotificationHelper.create_odoo_notification(
                "Aucune alerte, pas besoin de rappel",
                'info'
            )

        return self.partner_id.action_send_document_request()

    def action_generate_report(self):
        """Génère un rapport PDF des statistiques"""
        self.ensure_one()

        return {
            'type': 'ir.actions.report',
            'report_name': 'construction_contact_extension.partner_document_stats_report',
            'report_type': 'qweb-pdf',
            'data': self._prepare_report_data(),
            'context': {
                'active_id': self.id,
                'active_model': self._name
            }
        }

    def action_export_data(self):
        """Exporte les données en Excel"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Exporter les statistiques',
            'res_model': 'document.stats.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_stats_data': self._prepare_export_data()
            }
        }

    # =================== MÉTHODES UTILITAIRES ===================

    def _prepare_report_data(self):
        """Prépare les données pour le rapport PDF"""
        self.ensure_one()

        return {
            'partner': {
                'name': self.partner_id.name,
                'email': self.partner_id.email,
                'phone': self.partner_id.phone,
                'is_subcontractor': self.partner_id.is_subcontractor
            },
            'scores': {
                'health_score': self.health_score,
                'completion_rate': self.completion_rate,
                'reliability_score': self.reliability_score
            },
            'stats': {
                'total_documents': self.total_documents,
                'valid_documents': self.valid_documents,
                'expired_documents': self.expired_documents,
                'expiring_documents': self.expiring_documents,
                'rejected_documents': self.rejected_documents,
                'missing_documents': self.missing_documents,
                'to_check_documents': self.to_check_documents
            },
            'temporal': {
                'first_upload_date': self.first_upload_date,
                'last_upload_date': self.last_upload_date,
                'uploads_last_30_days': self.uploads_last_30_days,
                'uploads_last_90_days': self.uploads_last_90_days,
                'average_processing_days': self.average_processing_days
            },
            'expiry': {
                'next_expiry_date': self.next_expiry_date,
                'next_expiry_document': self.next_expiry_document,
                'expiry_within_30_days': self.expiry_within_30_days,
                'expiry_within_60_days': self.expiry_within_60_days,
                'expiry_within_90_days': self.expiry_within_90_days
            },
            'alerts': {
                'count': self.alerts_count,
                'text': self.alerts_text,
                'recommendations': self.recommendations_text
            },
            'generation_date': fields.Datetime.now()
        }

    def _prepare_export_data(self):
        """Prépare les données pour l'export Excel"""
        self.ensure_one()

        # Données par document
        document_data = []
        for doc in self.partner_id.document_ids:
            document_data.append({
                'Type': doc.document_type_id.name,
                'État': dict(doc._fields['state'].selection)[doc.state],
                'Date upload': doc.upload_date,
                'Date expiration': doc.expiry_date,
                'Jours avant expiration': doc.days_until_expiry,
                'Validé par': doc.validated_by.name if doc.validated_by else '',
                'Date validation': doc.validation_date,
                'Taille fichier': doc.file_size_human
            })

        return {
            'summary': self._prepare_report_data(),
            'documents_detail': document_data
        }

    def get_performance_indicators(self):
        """Retourne les indicateurs de performance"""
        self.ensure_one()

        return {
            'completion_trend': self._calculate_completion_trend(),
            'upload_frequency': self._calculate_upload_frequency(),
            'validation_efficiency': self._calculate_validation_efficiency(),
            'compliance_score': self._calculate_compliance_score()
        }

    def _calculate_completion_trend(self):
        """Calcule la tendance de complétion"""
        # Comparaison avec les 30 derniers jours
        if self.uploads_last_30_days > self.uploads_last_90_days - self.uploads_last_30_days:
            return 'positive'
        elif self.uploads_last_30_days < (self.uploads_last_90_days - self.uploads_last_30_days) / 2:
            return 'negative'
        else:
            return 'stable'

    def _calculate_upload_frequency(self):
        """Calcule la fréquence d'upload"""
        if self.uploads_last_30_days >= 5:
            return 'high'
        elif self.uploads_last_30_days >= 2:
            return 'medium'
        else:
            return 'low'

    def _calculate_validation_efficiency(self):
        """Calcule l'efficacité de validation"""
        if self.average_processing_days <= 2:
            return 'excellent'
        elif self.average_processing_days <= 5:
            return 'good'
        elif self.average_processing_days <= 10:
            return 'average'
        else:
            return 'poor'

    def _calculate_compliance_score(self):
        """Calcule le score de conformité"""
        if self.mandatory_docs_complete and self.expired_documents == 0:
            return 100
        elif self.mandatory_docs_complete:
            return 80
        elif self.completion_rate >= 70:
            return 60
        else:
            return 40
