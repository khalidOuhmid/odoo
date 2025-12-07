/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { KPICard } from "./kpi_card";
import { AlertPanel } from "./alert_panel";
import { QuickActions } from "./quick_actions";

export class ConstructionDashboard extends Component {
    static template = "construction_dashboard.Dashboard";
    static components = { KPICard, AlertPanel, QuickActions };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            dashboard: null,
            widgets: [],
            loading: true,
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });

        onMounted(() => {
            this.setupAutoRefresh();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            const dashboards = await this.orm.call(
                "construction.dashboard",
                "get_dashboard_for_user",
                []
            );
            if (dashboards) {
                const data = await this.orm.call(
                    "construction.dashboard",
                    "get_dashboard_data",
                    [dashboards.id || dashboards]
                );
                this.state.dashboard = data;
                this.state.widgets = data.widgets || [];
            }
        } catch (error) {
            console.error("Error loading dashboard:", error);
        }
        this.state.loading = false;
    }

    setupAutoRefresh() {
        // Setup auto-refresh for widgets with refresh_interval > 0
        this.state.widgets.forEach(widget => {
            if (widget.refresh_interval && widget.refresh_interval > 0) {
                setInterval(() => {
                    this.refreshWidget(widget.id);
                }, widget.refresh_interval * 1000);
            }
        });
    }

    async refreshWidget(widgetId) {
        const widget = this.state.widgets.find(w => w.id === widgetId);
        if (widget) {
            try {
                const data = await this.orm.call(
                    "construction.dashboard.widget",
                    "get_widget_data",
                    [widgetId]
                );
                Object.assign(widget, data);
            } catch (error) {
                console.error("Error refreshing widget:", error);
            }
        }
    }

    getWidgetStyle(widget) {
        const pos = widget.position || {};
        return `grid-column: ${(pos.x || 0) + 1} / span ${pos.width || 3}; grid-row: ${(pos.y || 0) + 1} / span ${pos.height || 2};`;
    }

    getColorClass(color) {
        const colorMap = {
            primary: 'bg-blg-terre-cuite',
            success: 'bg-success',
            warning: 'bg-warning',
            danger: 'bg-danger',
            info: 'bg-info',
            secondary: 'bg-secondary',
        };
        return colorMap[color] || 'bg-blg-terre-cuite';
    }

    async onQuickAction(action) {
        if (action.action_id) {
            await this.action.doAction(action.action_id);
        } else if (action.url) {
            window.open(action.url, '_blank');
        }
    }
}

registry.category("actions").add("construction_dashboard", ConstructionDashboard);
