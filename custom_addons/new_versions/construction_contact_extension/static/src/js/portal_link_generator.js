/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Portal Link Generator Component
 * Générateur de liens portail avec QR codes et personnalisation
 */
export class PortalLinkGenerator extends Component {
    static template = "construction_contact_extension.PortalLinkGeneratorTemplate";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            partnerId: null,
            partnerName: '',
            linkUrl: '',
            qrCodeUrl: '',
            isGenerating: false,
            validityDays: 7,
            customMessage: '',
            includeQrCode: true,
            sendByEmail: true,
            emailTemplate: 'default',
            linkExpiry: null,
            linkStats: {
                clicks: 0,
                lastAccess: null,
                uploadCount: 0
            },
            templates: [
                { value: 'default', label: _t('Template par défaut') },
                { value: 'urgent', label: _t('Rappel urgent') },
                { value: 'welcome', label: _t('Nouveau partenaire') },
                { value: 'renewal', label: _t('Renouvellement documents') }
            ]
        });

        onMounted(() => {
            this._loadConfiguration();
            this._loadPartnerInfo();
        });
    }

    /**
     * Chargement de la configuration
     */
    async _loadConfiguration() {
        try {
            // Durée de validité par défaut
            const validity = await this.orm.call(
                "ir.config_parameter",
                "get_param",
                ["construction_contact_extension.portal_token_validity_days", "7"]
            );
            this.state.validityDays = parseInt(validity);

            // QR Code activé
            const qrEnabled = await this.orm.call(
                "ir.config_parameter",
                "get_param",
                ["construction_contact_extension.enable_portal_qr_codes", "True"]
            );
            this.state.includeQrCode = qrEnabled === "True";

            // Message personnalisé par défaut
            const customMsg = await this.orm.call(
                "ir.config_parameter",
                "get_param",
                ["construction_contact_extension.portal_custom_instructions", ""]
            );
            this.state.customMessage = customMsg;

        } catch (error) {
            console.error("Erreur chargement configuration:", error);
        }
    }

    /**
     * Chargement des informations du partenaire
     */
    async _loadPartnerInfo() {
        if (!this.props.partnerId) return;

        try {
            const partner = await this.orm.read(
                "res.partner",
                [this.props.partnerId],
                ["name", "email", "upload_token", "token_expiration"]
            );

            if (partner.length > 0) {
                const partnerData = partner[0];
                this.state.partnerId = partnerData.id;
                this.state.partnerName = partnerData.name;

                // Si un token existe déjà
                if (partnerData.upload_token) {
                    this._generatePortalUrl(partnerData.upload_token);
                    this.state.linkExpiry = partnerData.token_expiration;
                    await this._loadLinkStats();
                }
            }
        } catch (error) {
            console.error("Erreur chargement partenaire:", error);
        }
    }

    /**
     * Génération du lien portail
     */
    async onGenerateLink() {
        if (!this.state.partnerId) {
            this.notification.add(_t("Aucun partenaire sélectionné"), { type: "warning" });
            return;
        }

        this.state.isGenerating = true;

        try {
            // Génération du token
            const result = await this.orm.call(
                "res.partner",
                "generate_upload_token",
                [this.state.partnerId],
                {
                    validity_days: this.state.validityDays,
                    custom_message: this.state.customMessage
                }
            );

            this.state.linkUrl = this._generatePortalUrl(result.token);
            this.state.linkExpiry = result.expiry_date;

            // Génération du QR Code si activé
            if (this.state.includeQrCode) {
                await this._generateQrCode();
            }

            // Envoi par email si demandé
            if (this.state.sendByEmail) {
                await this._sendEmailNotification();
            }

            // Mise à jour des stats
            await this._loadLinkStats();

            this.notification.add(
                _t("Lien portail généré avec succès"),
                { type: "success" }
            );

        } catch (error) {
            console.error("Erreur génération lien:", error);
            this.notification.add(
                _t("Erreur lors de la génération du lien"),
                { type: "danger" }
            );
        } finally {
            this.state.isGenerating = false;
        }
    }

    /**
     * Génération de l'URL du portail
     */
    _generatePortalUrl(token) {
        const baseUrl = window.location.origin;
        return `${baseUrl}/documents/upload/${token}`;
    }

    /**
     * Génération du QR Code
     */
    async _generateQrCode() {
        try {
            const result = await this.orm.call(
                "res.partner",
                "generate_portal_qr_code",
                [this.state.partnerId],
                { url: this.state.linkUrl }
            );

            this.state.qrCodeUrl = result.qr_code_url;
        } catch (error) {
            console.error("Erreur génération QR Code:", error);
        }
    }

    /**
     * Envoi de la notification email
     */
    async _sendEmailNotification() {
        try {
            await this.orm.call(
                "res.partner",
                "send_portal_link_notification",
                [this.state.partnerId],
                {
                    template: this.state.emailTemplate,
                    custom_message: this.state.customMessage,
                    include_qr_code: this.state.includeQrCode
                }
            );

            this.notification.add(
                _t("Email de notification envoyé"),
                { type: "success" }
            );

        } catch (error) {
            console.error("Erreur envoi email:", error);
            this.notification.add(
                _t("Erreur lors de l'envoi de l'email"),
                { type: "warning" }
            );
        }
    }

    /**
     * Chargement des statistiques du lien
     */
    async _loadLinkStats() {
        try {
            const stats = await this.orm.call(
                "res.partner",
                "get_portal_link_stats",
                [this.state.partnerId]
            );

            this.state.linkStats = {
                clicks: stats.clicks || 0,
                lastAccess: stats.last_access,
                uploadCount: stats.upload_count || 0
            };

        } catch (error) {
            console.error("Erreur chargement stats:", error);
        }
    }

    /**
     * Copie du lien dans le presse-papiers
     */
    async onCopyLink() {
        if (!this.state.linkUrl) {
            this.notification.add(_t("Aucun lien à copier"), { type: "warning" });
            return;
        }

        try {
            await navigator.clipboard.writeText(this.state.linkUrl);
            this.notification.add(_t("Lien copié dans le presse-papiers"), { type: "success" });
        } catch (error) {
            // Fallback pour les navigateurs plus anciens
            const textArea = document.createElement('textarea');
            textArea.value = this.state.linkUrl;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);

            this.notification.add(_t("Lien copié"), { type: "success" });
        }
    }

    /**
     * Ouverture du lien dans un nouvel onglet
     */
    onOpenLink() {
        if (!this.state.linkUrl) {
            this.notification.add(_t("Aucun lien disponible"), { type: "warning" });
            return;
        }

        window.open(this.state.linkUrl, '_blank');
    }

    /**
     * Téléchargement du QR Code
     */
    onDownloadQrCode() {
        if (!this.state.qrCodeUrl) {
            this.notification.add(_t("Aucun QR Code disponible"), { type: "warning" });
            return;
        }

        const link = document.createElement('a');
        link.href = this.state.qrCodeUrl;
        link.download = `qr-code-${this.state.partnerName}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    /**
     * Révocation du lien
     */
    async onRevokeLink() {
        if (!this.state.partnerId) return;

        try {
            await this.orm.call(
                "res.partner",
                "revoke_upload_token",
                [this.state.partnerId]
            );

            this.state.linkUrl = '';
            this.state.qrCodeUrl = '';
            this.state.linkExpiry = null;
            this.state.linkStats = { clicks: 0, lastAccess: null, uploadCount: 0 };

            this.notification.add(_t("Lien révoqué avec succès"), { type: "success" });

        } catch (error) {
            console.error("Erreur révocation lien:", error);
            this.notification.add(_t("Erreur lors de la révocation"), { type: "danger" });
        }
    }

    /**
     * Actualisation des statistiques
     */
    async onRefreshStats() {
        await this._loadLinkStats();
        this.notification.add(_t("Statistiques actualisées"), { type: "info" });
    }

    /**
     * Prévisualisation de l'email
     */
    async onPreviewEmail() {
        try {
            const preview = await this.orm.call(
                "res.partner",
                "preview_portal_email",
                [this.state.partnerId],
                {
                    template: this.state.emailTemplate,
                    custom_message: this.state.customMessage
                }
            );

            this.dialog.add("construction_contact_extension.EmailPreviewDialog", {
                subject: preview.subject,
                body: preview.body,
                partner: this.state.partnerName
            });

        } catch (error) {
            console.error("Erreur prévisualisation email:", error);
            this.notification.add(_t("Erreur de prévisualisation"), { type: "warning" });
        }
    }

    /**
     * Getters pour le template
     */
    get hasValidLink() {
        return this.state.linkUrl && this.state.linkExpiry;
    }

    get isLinkExpired() {
        if (!this.state.linkExpiry) return false;
        return new Date(this.state.linkExpiry) <= new Date();
    }

    get expiryFormatted() {
        if (!this.state.linkExpiry) return '';
        return new Date(this.state.linkExpiry).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    get lastAccessFormatted() {
        if (!this.state.linkStats.lastAccess) return _t('Jamais');
        return new Date(this.state.linkStats.lastAccess).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

// Enregistrement du composant
export const portalLinkGenerator = {
    component: PortalLinkGenerator,
};
