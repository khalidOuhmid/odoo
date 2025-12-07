/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * ContractTimelineWidget
 * 
 * Displays a visual timeline of contract activities with icons and colors
 * based on activity type. Shows date/time, user, and description for each event.
 */
export class ContractTimelineWidget extends Component {
    static template = "construction_contract.ContractTimelineWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            activities: [],
            loading: true,
            expanded: false,
            maxVisible: 5,
        });

        onWillStart(async () => {
            await this.loadActivities();
        });
    }

    /**
     * Load activities from the server
     */
    async loadActivities() {
        this.state.loading = true;
        try {
            const contractId = this.props.record.resId;
            if (contractId) {
                const activities = await this.orm.searchRead(
                    "construction.contract.activity",
                    [["contract_id", "=", contractId]],
                    ["activity_type", "description", "user_id", "ip_address", "create_date", "icon", "color"],
                    { order: "create_date desc", limit: 50 }
                );
                this.state.activities = activities.map(activity => ({
                    ...activity,
                    formattedDate: this.formatDate(activity.create_date),
                    formattedTime: this.formatTime(activity.create_date),
                    typeLabel: this.getTypeLabel(activity.activity_type),
                    iconClass: this.getIconClass(activity.activity_type),
                    colorClass: this.getColorClass(activity.activity_type),
                }));
            }
        } catch (error) {
            console.error("Error loading activities:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Format date for display
     */
    formatDate(dateStr) {
        if (!dateStr) return "";
        const date = new Date(dateStr);
        return date.toLocaleDateString("fr-FR", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        });
    }

    /**
     * Format time for display
     */
    formatTime(dateStr) {
        if (!dateStr) return "";
        const date = new Date(dateStr);
        return date.toLocaleTimeString("fr-FR", {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    /**
     * Get human-readable label for activity type
     */
    getTypeLabel(activityType) {
        const labels = {
            created: "Création",
            generated: "PDF généré",
            sent: "Envoyé",
            viewed: "Consulté",
            page_validated: "Page validée",
            signed: "Signé",
            reminder: "Relance envoyée",
            state_change: "Changement de statut",
            modified: "Modifié",
            archived: "Archivé",
        };
        return labels[activityType] || activityType;
    }

    /**
     * Get Font Awesome icon class for activity type
     */
    getIconClass(activityType) {
        const icons = {
            created: "fa-plus-circle",
            generated: "fa-file-pdf-o",
            sent: "fa-paper-plane",
            viewed: "fa-eye",
            page_validated: "fa-check",
            signed: "fa-pencil-square-o",
            reminder: "fa-bell",
            state_change: "fa-exchange",
            modified: "fa-edit",
            archived: "fa-archive",
        };
        return icons[activityType] || "fa-circle";
    }

    /**
     * Get color class for activity type
     */
    getColorClass(activityType) {
        const colors = {
            created: "timeline-primary",
            generated: "timeline-info",
            sent: "timeline-warning",
            viewed: "timeline-muted",
            page_validated: "timeline-info",
            signed: "timeline-success",
            reminder: "timeline-warning",
            state_change: "timeline-primary",
            modified: "timeline-muted",
            archived: "timeline-danger",
        };
        return colors[activityType] || "timeline-muted";
    }

    /**
     * Get visible activities based on expanded state
     */
    get visibleActivities() {
        if (this.state.expanded) {
            return this.state.activities;
        }
        return this.state.activities.slice(0, this.state.maxVisible);
    }

    /**
     * Check if there are more activities to show
     */
    get hasMore() {
        return this.state.activities.length > this.state.maxVisible;
    }

    /**
     * Toggle expanded state
     */
    toggleExpanded() {
        this.state.expanded = !this.state.expanded;
    }

    /**
     * Refresh activities
     */
    async refresh() {
        await this.loadActivities();
    }
}

// Register the widget
registry.category("fields").add("contract_timeline", {
    component: ContractTimelineWidget,
    supportedTypes: ["one2many"],
});
