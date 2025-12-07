/** @odoo-module **/

import { Component } from "@odoo/owl";

export class AlertPanel extends Component {
    static template = "construction_dashboard.AlertPanel";
    static props = {
        widget: Object,
        onRefresh: { type: Function, optional: true },
    };

    get alerts() {
        return this.props.widget.alerts || [];
    }

    get title() {
        return this.props.widget.title || this.props.widget.name;
    }

    get iconClass() {
        return `fa ${this.props.widget.icon || 'fa-exclamation-triangle'}`;
    }

    getPriorityClass(priority) {
        const priorityMap = {
            high: 'alert-danger',
            medium: 'alert-warning',
            low: 'alert-info',
        };
        return priorityMap[priority] || 'alert-info';
    }

    getPriorityIcon(priority) {
        const iconMap = {
            high: 'fa-exclamation-circle',
            medium: 'fa-exclamation-triangle',
            low: 'fa-info-circle',
        };
        return iconMap[priority] || 'fa-info-circle';
    }

    onRefresh() {
        if (this.props.onRefresh) {
            this.props.onRefresh(this.props.widget.id);
        }
    }
}
