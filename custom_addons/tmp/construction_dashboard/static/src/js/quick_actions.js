/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class QuickActions extends Component {
    static template = "construction_dashboard.QuickActions";
    static props = {
        widget: Object,
    };

    setup() {
        this.action = useService("action");
    }

    get actions() {
        return this.props.widget.actions || [];
    }

    get title() {
        return this.props.widget.title || this.props.widget.name;
    }

    get iconClass() {
        return `fa ${this.props.widget.icon || 'fa-bolt'}`;
    }

    async onActionClick(action) {
        if (action.action_id) {
            // Execute Odoo action by ID
            await this.action.doAction(action.action_id);
        } else if (action.action_xml_id) {
            // Execute Odoo action by XML ID
            await this.action.doAction(action.action_xml_id);
        } else if (action.url) {
            // Open URL
            window.open(action.url, action.target || '_blank');
        } else if (action.method) {
            // Call a method (could be extended)
            console.log('Method call not implemented:', action.method);
        }
    }

    getActionIcon(action) {
        return `fa ${action.icon || 'fa-arrow-right'}`;
    }

    getActionClass(action) {
        const colorMap = {
            primary: 'btn-blg-terre-cuite',
            success: 'btn-success',
            warning: 'btn-warning',
            danger: 'btn-danger',
            info: 'btn-info',
            secondary: 'btn-secondary',
        };
        return colorMap[action.color] || 'btn-blg-terre-cuite';
    }
}
