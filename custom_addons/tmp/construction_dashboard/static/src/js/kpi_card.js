/** @odoo-module **/

import { Component } from "@odoo/owl";

export class KPICard extends Component {
    static template = "construction_dashboard.KPICard";
    static props = {
        widget: Object,
        onRefresh: { type: Function, optional: true },
    };

    get colorClass() {
        const colorMap = {
            primary: 'bg-blg-terre-cuite text-white',
            success: 'bg-success text-white',
            warning: 'bg-warning text-dark',
            danger: 'bg-danger text-white',
            info: 'bg-info text-white',
            secondary: 'bg-secondary text-white',
        };
        return colorMap[this.props.widget.color] || 'bg-blg-terre-cuite text-white';
    }

    get iconClass() {
        return `fa ${this.props.widget.icon || 'fa-chart-bar'}`;
    }

    get value() {
        return this.props.widget.value || 0;
    }

    get title() {
        return this.props.widget.title || this.props.widget.name;
    }

    get trend() {
        // Could be extended to show trend arrows
        return this.props.widget.trend || null;
    }

    onRefresh() {
        if (this.props.onRefresh) {
            this.props.onRefresh(this.props.widget.id);
        }
    }
}
