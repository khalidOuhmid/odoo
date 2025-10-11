/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Patch du composant Chatter pour modifier le comportement du bouton "Send message"
 * et ouvrir directement le full composer au lieu du mini composer
 */
patch(Chatter.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
    },

    /**
     * Override de la méthode toggleComposer pour ouvrir le full composer
     * directement quand on clique sur "Send message"
     */
    toggleComposer(type) {
        if (type === "message") {
            this.openFullComposer(type);
        } else {
            // Pour les notes, garder le comportement original
            super.toggleComposer(type);
        }
    },

    /**
     * Ouvre le full composer directement
     */
    async openFullComposer(messageType = "comment") {
        if (!this.state.thread?.id) {
            // Si le thread n'existe pas encore, sauvegarder d'abord l'enregistrement
            const saved = await this.props.saveRecord?.();
            if (!saved) {
                return;
            }
        }

        const context = {
            default_model: this.props.threadModel,
            default_res_ids: [this.props.threadId],
            default_message_type: messageType,
            default_subtype_xmlid: 'mail.mt_comment',
            mail_post_autofollow: true,
        };

        // Ajouter les destinataires suggérés s'ils existent
        if (this.state.thread?.suggestedRecipients?.length > 0) {
            context.default_partner_ids = this.state.thread.suggestedRecipients
                .filter(recipient => recipient.checked)
                .map(recipient => recipient.partner?.id)
                .filter(Boolean);
        }

        const action = {
            name: _t("Compose Email"),
            type: "ir.actions.act_window",
            res_model: "mail.compose.message",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: context,
        };

        await this.action.doAction(action);
    },
});
