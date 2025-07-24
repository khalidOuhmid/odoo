/** @odoo-module **/

import { GanttRenderer } from "@web_gantt/gantt_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

// Patch the GanttRenderer to add our custom button
patch(GanttRenderer.prototype, "construction_gantt_renderer", {
    setup() {
        this._super(...arguments);
        this.actionService = useService("action");
    },

    /**
     * @override
     */
    get extraButtons() {
        const buttons = this._super();
        buttons.push({
            icon: "fa-plus-circle",
            title: this.env._t("Créer tâche avancée"),
            click: () => this._onCreateAdvancedTask(),
        });
        return buttons;
    },

    /**
     * Handle click on our custom button
     * @private
     */
    _onCreateAdvancedTask() {
        const context = Object.assign({}, this.props.context);
        
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'construction.planning.task.create',
            view_mode: 'form',
            view_type: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: context,
        });
    },
});
