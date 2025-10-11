/** @odoo-module **/

import { messageActionsRegistry } from "@mail/core/common/message_actions";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * Ajout de l'action "Reply" pour créer une vraie réponse à un message
 * Cette action ouvre le full composer avec le contexte de réponse approprié
 */
messageActionsRegistry.add("email-reply", {
    condition: (component) => {
        const message = component.props.message;
        const thread = component.props.thread;
        
        // Disponible seulement pour les messages dans un thread avec écriture autorisée
        // et si ce n'est pas une note ou une notification
        return (
            message &&
            thread &&
            thread.hasWriteAccess &&
            message.message_type !== "notification" &&
            !message.is_note &&
            message.model &&
            message.res_id
        );
    },
    icon: "fa fa-reply",
    title: _t("Reply"),
    onClick: async (component) => {
        const message = component.props.message;
        const thread = component.props.thread;
        
        // Préparer le contexte pour la réponse
        const context = {
            default_model: message.model,
            default_res_ids: [message.res_id],
            default_parent_id: message.id,
            default_composition_mode: "comment",
            default_message_type: "comment",
            default_subtype_xmlid: "mail.mt_comment",
            mail_post_autofollow: true,
        };

        // Préparer le sujet de la réponse
        let subject = message.subject || thread.displayName || _t("Message");
        if (!subject.startsWith("Re:")) {
            subject = _t("Re: %s", subject);
        }
        context.default_subject = subject;

        // Ajouter l'auteur du message original comme destinataire
        if (message.author_id?.id) {
            context.default_partner_ids = [message.author_id.id];
        }

        // Debug: log du contexte
        console.log("Email Enhancement: Contexte pour le composer:", context);

        // Créer l'action pour ouvrir le full composer
        const action = {
            name: _t("Reply to Message"),
            type: "ir.actions.act_window",
            res_model: "mail.compose.message",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: context,
        };

        // Utiliser le service d'action du composant parent
        const actionService = component.env.services.action;
        if (actionService) {
            await actionService.doAction(action);
        } else {
            console.error("Email Enhancement: Action service not available");
        }
    },
    sequence: 15, // Placer après les réactions mais avant mark as TODO
});
