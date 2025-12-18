/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { messageActionsRegistry } from "@mail/core/common/message_actions";
import { useService } from "@web/core/utils/hooks";
import { useComponent } from "@odoo/owl";

/**
 * Message types that support quoted reply
 */
const QUOTED_REPLY_MESSAGE_TYPES = ["email", "comment"];

messageActionsRegistry.add("quoted-reply", {
    condition: (component) => {
        const message = component.props.message;
        // Only show for email/comment messages with a model/res_id
        return (
            message.message_type &&
            QUOTED_REPLY_MESSAGE_TYPES.includes(message.message_type) &&
            message.model &&
            message.res_id
        );
    },
    icon: "fa fa-quote-left",
    title: _t("Reply with Quote"),
    onClick: async (component) => {
        const message = component.props.message;
        // Call backend method to get the action with quoted body
        const action = await rpc("/web/dataset/call_kw/mail.message/reply_message", {
            model: "mail.message",
            method: "reply_message",
            args: [[message.id]],
            kwargs: {},
        });
        // Execute the action to open the composer
        await component.env.services.action.doAction(action, {
            onClose: async () => {
                // Refresh the thread after sending the reply
                if (component.props.thread) {
                    component.props.thread.fetchNewMessages?.();
                }
            },
        });
    },
    setup: () => {
        // Setup hook for any required services
        const component = useComponent();
        component.actionService = useService("action");
    },
    sequence: 15, // After reaction (10), before reply-to (20)
});
