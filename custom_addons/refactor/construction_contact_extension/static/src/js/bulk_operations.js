/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * Bulk Operations Component
 * Gère les opérations en lot sur les sous-traitants et documents
 */
export class BulkOperations extends Component {
    static template = "construction_contact_extension.BulkOperationsTemplate";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.action = useService("action");

        this.state = useState({
            selectedOperation: '',
            selectedPartners: [],
            isProcessing: false,
            progress: 0,
            results: [],
            operations: [
                {
                    key: 'generate_portal_links',
                    label: _t('Générer liens portail'),
                    description: _t('Génère des liens d\'accès au portail pour les partenaires sélectionnés'),
                    icon: 'fa-link',
                    requiresSelection: true
                },
                {
                    key: 'send_document_reminders',
                    label: _t('Envoyer rappels documents'),
                    description: _t('Envoie des rappels pour les documents manquants ou expirés'),
                    icon: 'fa-envelope',
                    requiresSelection: true
                },
                {
                    key: 'validate_all_pending',
                    label: _t('Valider documents en attente'),
                    description: _t('Valide tous les documents en attente de vérification'),
                    icon: 'fa-check',
                    requiresSelection: false
                },
                {
                    key: 'archive_expired_documents',
                    label: _t('Archiver documents expirés'),
                    description: _t('Archive automatiquement tous les documents expirés'),
                    icon: 'fa-archive',
                    requiresSelection: false
                },
                {
                    key: 'recalculate_scores',
                    label: _t('Recalculer scores santé'),
                    description: _t('Recalcule les scores de santé documentaire'),
                    icon: 'fa-calculator',
                    requiresSelection: true
                },
                {
                    key: 'export_report',
                    label: _t('Exporter rapport Excel'),
                    description: _t('Exporte un rapport complet au format Excel'),
                    icon: 'fa-file-excel-o',
                    requiresSelection: true
                },
                {
                    key: 'cleanup_old_tokens',
                    label: _t('Nettoyer tokens expirés'),
                    description: _t('Supprime les tokens d\'accès expirés'),
                    icon: 'fa-trash',
                    requiresSelection: false
                }
            ]
        });

        onMounted(() => {
            this._loadSelectedPartners();
        });
    }

    /**
     * Chargement des partenaires sélectionnés depuis le contexte
     */
    _loadSelectedPartners() {
        const context = this.props.context || {};
        const activeIds = context.active_ids || [];
        this.state.selectedPartners = activeIds;
    }

    /**
     * Sélection d'une opération
     */
    onOperationSelect(operationKey) {
        this.state.selectedOperation = operationKey;
        this.state.results = [];
    }

    /**
     * Exécution de l'opération sélectionnée
     */
    async onExecuteOperation() {
        const operation = this.state.operations.find(op => op.key === this.state.selectedOperation);
        if (!operation) {
            this.notification.add(_t("Veuillez sélectionner une opération"), { type: "warning" });
            return;
        }

        // Vérification de la sélection si nécessaire
        if (operation.requiresSelection && this.state.selectedPartners.length === 0) {
            this.notification.add(_t("Veuillez sélectionner au moins un partenaire"), { type: "warning" });
            return;
        }

        // Confirmation pour les opérations critiques
        if (['archive_expired_documents', 'cleanup_old_tokens'].includes(operation.key)) {
            const confirmed = await this._showConfirmationDialog(
                _t("Confirmer l'opération"),
                _t(`Êtes-vous sûr de vouloir exécuter "${operation.label}" ? Cette action peut être irréversible.`)
            );
            if (!confirmed) return;
        }

        this.state.isProcessing = true;
        this.state.progress = 0;
        this.state.results = [];

        try {
            await this._executeOperation(operation);
        } catch (error) {
            console.error("Erreur opération bulk:", error);
            this.notification.add(_t("Erreur lors de l'exécution"), { type: "danger" });
        } finally {
            this.state.isProcessing = false;
            this.state.progress = 0;
        }
    }

    /**
     * Exécution effective de l'opération
     */
    async _executeOperation(operation) {
        switch (operation.key) {
            case 'generate_portal_links':
                await this._generatePortalLinks();
                break;
            case 'send_document_reminders':
                await this._sendDocumentReminders();
                break;
            case 'validate_all_pending':
                await this._validateAllPending();
                break;
            case 'archive_expired_documents':
                await this._archiveExpiredDocuments();
                break;
            case 'recalculate_scores':
                await this._recalculateScores();
                break;
            case 'export_report':
                await this._exportReport();
                break;
            case 'cleanup_old_tokens':
                await this._cleanupOldTokens();
                break;
            default:
                throw new Error(`Opération inconnue: ${operation.key}`);
        }
    }

    /**
     * Génération des liens portail
     */
    async _generatePortalLinks() {
        const partners = this.state.selectedPartners;
        const results = [];

        for (let i = 0; i < partners.length; i++) {
            this.state.progress = Math.round((i / partners.length) * 100);

            try {
                const result = await this.orm.call(
                    "res.partner",
                    "generate_upload_token",
                    [partners[i]]
                );

                const partner = await this.orm.read("res.partner", [partners[i]], ["name"]);
                results.push({
                    partner: partner[0].name,
                    status: 'success',
                    message: _t('Lien généré avec succès'),
                    data: result
                });

            } catch (error) {
                const partner = await this.orm.read("res.partner", [partners[i]], ["name"]);
                results.push({
                    partner: partner[0].name,
                    status: 'error',
                    message: error.message || _t('Erreur inconnue')
                });
            }
        }

        this.state.results = results;
        this.state.progress = 100;

        const successCount = results.filter(r => r.status === 'success').length;
        this.notification.add(
            _t(`${successCount}/${partners.length} liens générés avec succès`),
            { type: successCount === partners.length ? "success" : "warning" }
        );
    }

    /**
     * Envoi des rappels de documents
     */
    async _sendDocumentReminders() {
        const partners = this.state.selectedPartners;
        const results = [];

        for (let i = 0; i < partners.length; i++) {
            this.state.progress = Math.round((i / partners.length) * 100);

            try {
                await this.orm.call(
                    "res.partner",
                    "send_document_reminder",
                    [partners[i]]
                );

                const partner = await this.orm.read("res.partner", [partners[i]], ["name"]);
                results.push({
                    partner: partner[0].name,
                    status: 'success',
                    message: _t('Rappel envoyé')
                });

            } catch (error) {
                const partner = await this.orm.read("res.partner", [partners[i]], ["name"]);
                results.push({
                    partner: partner[0].name,
                    status: 'error',
                    message: error.message || _t('Erreur envoi')
                });
            }
        }

        this.state.results = results;
        this.state.progress = 100;

        const successCount = results.filter(r => r.status === 'success').length;
        this.notification.add(
            _t(`${successCount}/${partners.length} rappels envoyés`),
            { type: "success" }
        );
    }

    /**
     * Validation de tous les documents en attente
     */
    async _validateAllPending() {
        try {
            const result = await this.orm.call(
                "partner.document",
                "bulk_validate_pending_documents",
                []
            );

            this.state.results = [{
                status: 'success',
                message: _t(`${result.validated_count} documents validés`)
            }];

            this.notification.add(
                _t(`${result.validated_count} documents validés avec succès`),
                { type: "success" }
            );

        } catch (error) {
            this.state.results = [{
                status: 'error',
                message: error.message || _t('Erreur lors de la validation')
            }];
        }

        this.state.progress = 100;
    }

    /**
     * Archivage des documents expirés
     */
    async _archiveExpiredDocuments() {
        try {
            const result = await this.orm.call(
                "partner.document",
                "bulk_archive_expired_documents",
                []
            );

            this.state.results = [{
                status: 'success',
                message: _t(`${result.archived_count} documents archivés`)
            }];

            this.notification.add(
                _t(`${result.archived_count} documents expirés archivés`),
                { type: "success" }
            );

        } catch (error) {
            this.state.results = [{
                status: 'error',
                message: error.message || _t('Erreur lors de l\'archivage')
            }];
        }

        this.state.progress = 100;
    }

    /**
     * Recalcul des scores
     */
    async _recalculateScores() {
        const partners = this.state.selectedPartners;
        const results = [];

        for (let i = 0; i < partners.length; i++) {
            this.state.progress = Math.round((i / partners.length) * 100);

            try {
                await this.orm.call(
                    "res.partner",
                    "calculate_document_health_score",
                    [partners[i]]
                );

                const partner = await this.orm.read("res.partner", [partners[i]], ["name"]);
                results.push({
                    partner: partner[0].name,
                    status: 'success',
                    message: _t('Score recalculé')
                });

            } catch (error) {
                const partner = await this.orm.read("res.partner", [partners[i]], ["name"]);
                results.push({
                    partner: partner[0].name,
                    status: 'error',
                    message: error.message || _t('Erreur calcul')
                });
            }
        }

        this.state.results = results;
        this.state.progress = 100;

        const successCount = results.filter(r => r.status === 'success').length;
        this.notification.add(
            _t(`${successCount}/${partners.length} scores recalculés`),
            { type: "success" }
        );
    }

    /**
     * Export de rapport
     */
    async _exportReport() {
        try {
            const result = await this.orm.call(
                "res.partner",
                "export_bulk_report",
                [this.state.selectedPartners]
            );

            // Téléchargement du rapport
            const link = document.createElement('a');
            link.href = result.download_url;
            link.download = result.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            this.state.results = [{
                status: 'success',
                message: _t('Rapport exporté avec succès')
            }];

            this.notification.add(_t("Rapport téléchargé"), { type: "success" });

        } catch (error) {
            this.state.results = [{
                status: 'error',
                message: error.message || _t('Erreur lors de l\'export')
            }];
        }

        this.state.progress = 100;
    }

    /**
     * Nettoyage des anciens tokens
     */
    async _cleanupOldTokens() {
        try {
            const result = await this.orm.call(
                "res.partner",
                "cleanup_expired_tokens",
                []
            );

            this.state.results = [{
                status: 'success',
                message: _t(`${result.cleaned_count} tokens supprimés`)
            }];

            this.notification.add(
                _t(`${result.cleaned_count} tokens expirés supprimés`),
                { type: "success" }
            );

        } catch (error) {
            this.state.results = [{
                status: 'error',
                message: error.message || _t('Erreur lors du nettoyage')
            }];
        }

        this.state.progress = 100;
    }

    /**
     * Affichage d'une boîte de confirmation
     */
    async _showConfirmationDialog(title, body) {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title,
                body,
                confirm: () => resolve(true),
                cancel: () => resolve(false)
            });
        });
    }

    /**
     * Getters pour le template
     */
    get selectedOperationData() {
        return this.state.operations.find(op => op.key === this.state.selectedOperation);
    }

    get canExecute() {
        return this.state.selectedOperation && !this.state.isProcessing;
    }

    get hasResults() {
        return this.state.results.length > 0;
    }

    get successResults() {
        return this.state.results.filter(r => r.status === 'success');
    }

    get errorResults() {
        return this.state.results.filter(r => r.status === 'error');
    }
}

// Enregistrement du composant
export const bulkOperations = {
    component: BulkOperations,
};
