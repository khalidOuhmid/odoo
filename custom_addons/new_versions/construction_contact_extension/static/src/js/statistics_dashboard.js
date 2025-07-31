/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Statistics Dashboard Component
 * Tableau de bord avec graphiques et métriques pour les sous-traitants
 */
export class StatisticsDashboard extends Component {
    static template = "construction_contact_extension.StatisticsDashboardTemplate";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            isLoading: true,
            refreshInterval: null,
            selectedPeriod: '30',
            selectedView: 'overview',
            data: {
                overview: {
                    totalPartners: 0,
                    completeFiles: 0,
                    pendingValidation: 0,
                    expiredDocs: 0,
                    averageHealthScore: 0,
                    averageCompletionRate: 0
                },
                charts: {
                    documentStatus: [],
                    healthScoreDistribution: [],
                    uploadTrends: [],
                    partnerActivity: []
                },
                topPerformers: [],
                criticalAlerts: [],
                recentActivity: []
            },
            filters: {
                specialityIds: [],
                healthScoreMin: 0,
                healthScoreMax: 100,
                includeInactive: false
            },
            charts: {
                documentStatusChart: null,
                healthScoreChart: null,
                uploadTrendsChart: null,
                activityChart: null
            }
        });

        onMounted(() => {
            this._initializeCharts();
            this._loadDashboardData();
            this._setupAutoRefresh();
        });

        onWillUnmount(() => {
            this._cleanupCharts();
            this._clearAutoRefresh();
        });
    }

    /**
     * Initialisation des graphiques
     */
    _initializeCharts() {
        // Vérifier que Chart.js est disponible
        if (typeof Chart === 'undefined') {
            console.error("Chart.js not loaded");
            return;
        }

        // Configuration par défaut des graphiques
        Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
        Chart.defaults.color = '#64748b';
        Chart.defaults.scale.grid.color = '#e2e8f0';
    }

    /**
     * Chargement des données du tableau de bord
     */
    async _loadDashboardData() {
        this.state.isLoading = true;

        try {
            const data = await this.orm.call(
                "res.partner",
                "get_dashboard_statistics",
                [],
                {
                    period_days: parseInt(this.state.selectedPeriod),
                    filters: this.state.filters
                }
            );

            this.state.data = data;
            await this._updateCharts();

        } catch (error) {
            console.error("Erreur chargement données dashboard:", error);
            this.notification.add(
                _t("Erreur lors du chargement des statistiques"),
                { type: "danger" }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Mise à jour des graphiques
     */
    async _updateCharts() {
        await this._updateDocumentStatusChart();
        await this._updateHealthScoreChart();
        await this._updateUploadTrendsChart();
        await this._updateActivityChart();
    }

    /**
     * Graphique de statut des documents
     */
    async _updateDocumentStatusChart() {
        const canvas = this.el.querySelector('#documentStatusChart');
        if (!canvas) return;

        // Détruire le graphique existant
        if (this.state.charts.documentStatusChart) {
            this.state.charts.documentStatusChart.destroy();
        }

        const ctx = canvas.getContext('2d');
        const data = this.state.data.charts.documentStatus;

        this.state.charts.documentStatusChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(item => item.label),
                datasets: [{
                    data: data.map(item => item.value),
                    backgroundColor: [
                        '#16a34a', // Valides - vert
                        '#eab308', // En attente - jaune
                        '#dc2626', // Expirés - rouge
                        '#64748b', // Manquants - gris
                        '#f59e0b'  // Rejetés - orange
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.raw / total) * 100).toFixed(1);
                                return `${context.label}: ${context.raw} (${percentage}%)`;
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const status = data[index].status;
                        this._openDocumentsByStatus(status);
                    }
                }
            }
        });
    }

    /**
     * Graphique de distribution des scores de santé
     */
    async _updateHealthScoreChart() {
        const canvas = this.el.querySelector('#healthScoreChart');
        if (!canvas) return;

        if (this.state.charts.healthScoreChart) {
            this.state.charts.healthScoreChart.destroy();
        }

        const ctx = canvas.getContext('2d');
        const data = this.state.data.charts.healthScoreDistribution;

        this.state.charts.healthScoreChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.range),
                datasets: [{
                    label: _t('Nombre de partenaires'),
                    data: data.map(item => item.count),
                    backgroundColor: 'rgba(30, 64, 175, 0.8)',
                    borderColor: 'rgba(30, 64, 175, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            title: (context) => `Score: ${context[0].label}`,
                            label: (context) => `${context.raw} partenaire(s)`
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const range = data[index];
                        this._openPartnersByHealthScore(range.min, range.max);
                    }
                }
            }
        });
    }

    /**
     * Graphique des tendances d'upload
     */
    async _updateUploadTrendsChart() {
        const canvas = this.el.querySelector('#uploadTrendsChart');
        if (!canvas) return;

        if (this.state.charts.uploadTrendsChart) {
            this.state.charts.uploadTrendsChart.destroy();
        }

        const ctx = canvas.getContext('2d');
        const data = this.state.data.charts.uploadTrends;

        this.state.charts.uploadTrendsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.date),
                datasets: [
                    {
                        label: _t('Uploads'),
                        data: data.map(item => item.uploads),
                        borderColor: '#16a34a',
                        backgroundColor: 'rgba(22, 163, 74, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: _t('Validations'),
                        data: data.map(item => item.validations),
                        borderColor: '#0ea5e9',
                        backgroundColor: 'rgba(14, 165, 233, 0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    }
                }
            }
        });
    }

    /**
     * Graphique d'activité des partenaires
     */
    async _updateActivityChart() {
        const canvas = this.el.querySelector('#activityChart');
        if (!canvas) return;

        if (this.state.charts.activityChart) {
            this.state.charts.activityChart.destroy();
        }

        const ctx = canvas.getContext('2d');
        const data = this.state.data.charts.partnerActivity;

        this.state.charts.activityChart = new Chart(ctx, {
            type: 'horizontalBar',
            data: {
                labels: data.map(item => item.partner_name),
                datasets: [{
                    label: _t('Score d\'activité'),
                    data: data.map(item => item.activity_score),
                    backgroundColor: data.map(item => {
                        if (item.activity_score >= 80) return '#16a34a';
                        if (item.activity_score >= 60) return '#eab308';
                        return '#dc2626';
                    }),
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const partner = data[index];
                        this._openPartnerDetails(partner.partner_id);
                    }
                }
            }
        });
    }

    /**
     * Configuration de l'actualisation automatique
     */
    _setupAutoRefresh() {
        this.state.refreshInterval = setInterval(() => {
            this._loadDashboardData();
        }, 300000); // 5 minutes
    }

    /**
     * Nettoyage de l'actualisation automatique
     */
    _clearAutoRefresh() {
        if (this.state.refreshInterval) {
            clearInterval(this.state.refreshInterval);
            this.state.refreshInterval = null;
        }
    }

    /**
     * Nettoyage des graphiques
     */
    _cleanupCharts() {
        Object.values(this.state.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
    }

    /**
     * Changement de période
     */
    async onPeriodChange(period) {
        this.state.selectedPeriod = period;
        await this._loadDashboardData();
    }

    /**
     * Changement de vue
     */
    onViewChange(view) {
        this.state.selectedView = view;
    }

    /**
     * Actualisation manuelle
     */
    async onRefresh() {
        await this._loadDashboardData();
        this.notification.add(_t("Données actualisées"), { type: "success" });
    }

    /**
     * Export des données
     */
    async onExportData() {
        try {
            const result = await this.orm.call(
                "res.partner",
                "export_dashboard_data",
                [],
                {
                    period_days: parseInt(this.state.selectedPeriod),
                    filters: this.state.filters
                }
            );

            // Téléchargement du fichier
            const link = document.createElement('a');
            link.href = result.download_url;
            link.download = result.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            this.notification.add(_t("Export téléchargé"), { type: "success" });

        } catch (error) {
            console.error("Erreur export:", error);
            this.notification.add(_t("Erreur lors de l'export"), { type: "danger" });
        }
    }

    /**
     * Ouverture des documents par statut
     */
    _openDocumentsByStatus(status) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Documents'),
            res_model: 'partner.document',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['state', '=', status]],
            context: { search_default_group_by_partner: 1 }
        });
    }

    /**
     * Ouverture des partenaires par score de santé
     */
    _openPartnersByHealthScore(minScore, maxScore) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Partenaires'),
            res_model: 'res.partner',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [
                ['is_subcontractor', '=', true],
                ['document_health_score', '>=', minScore],
                ['document_health_score', '<', maxScore]
            ]
        });
    }

    /**
     * Ouverture des détails d'un partenaire
     */
    _openPartnerDetails(partnerId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Détails Partenaire'),
            res_model: 'res.partner',
            res_id: partnerId,
            view_mode: 'form',
            views: [[false, 'form']]
        });
    }

    /**
     * Gestion d'une alerte critique
     */
    async onHandleCriticalAlert(alertId) {
        try {
            await this.orm.call(
                "partner.notification.service",
                "handle_critical_alert",
                [alertId]
            );

            // Recharger les données
            await this._loadDashboardData();

        } catch (error) {
            console.error("Erreur gestion alerte:", error);
            this.notification.add(_t("Erreur lors du traitement"), { type: "danger" });
        }
    }

    /**
     * Getters pour le template
     */
    get isOverviewView() {
        return this.state.selectedView === 'overview';
    }

    get isChartsView() {
        return this.state.selectedView === 'charts';
    }

    get isAlertsView() {
        return this.state.selectedView === 'alerts';
    }

    get isActivityView() {
        return this.state.selectedView === 'activity';
    }

    get hasCriticalAlerts() {
        return this.state.data.criticalAlerts && this.state.data.criticalAlerts.length > 0;
    }

    get overviewData() {
        return this.state.data.overview;
    }

    get criticalAlerts() {
        return this.state.data.criticalAlerts || [];
    }

    get recentActivity() {
        return this.state.data.recentActivity || [];
    }

    get topPerformers() {
        return this.state.data.topPerformers || [];
    }
}

// Enregistrement du composant
export const statisticsDashboard = {
    component: StatisticsDashboard,
};
