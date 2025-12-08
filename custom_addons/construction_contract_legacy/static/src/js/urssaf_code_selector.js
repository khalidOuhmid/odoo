/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * URSSAF Code Selector Widget
 * Provides a searchable dropdown to select and insert URSSAF codes into templates
 */
export class URSSAFCodeSelector extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            codes: [],
            filteredCodes: [],
            searchTerm: "",
            selectedCategory: "all",
            isOpen: false,
            loading: true,
        });

        onWillStart(async () => {
            await this.loadURSSAFCodes();
        });
    }

    /**
     * Load all active URSSAF codes from the database
     */
    async loadURSSAFCodes() {
        try {
            this.state.loading = true;
            const codes = await this.orm.searchRead(
                "construction.urssaf.code",
                [["active", "=", true]],
                ["code", "name", "description", "category", "rate", "legal_reference"],
                { order: "category, code" }
            );
            this.state.codes = codes;
            this.state.filteredCodes = codes;
        } catch (error) {
            console.error("Error loading URSSAF codes:", error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Filter codes based on search term and category
     */
    filterCodes() {
        let filtered = this.state.codes;

        // Filter by category
        if (this.state.selectedCategory !== "all") {
            filtered = filtered.filter(
                (code) => code.category === this.state.selectedCategory
            );
        }

        // Filter by search term
        if (this.state.searchTerm) {
            const searchLower = this.state.searchTerm.toLowerCase();
            filtered = filtered.filter(
                (code) =>
                    code.code.toLowerCase().includes(searchLower) ||
                    code.name.toLowerCase().includes(searchLower) ||
                    (code.description && code.description.toLowerCase().includes(searchLower))
            );
        }

        this.state.filteredCodes = filtered;
    }

    /**
     * Handle search input change
     */
    onSearchChange(ev) {
        this.state.searchTerm = ev.target.value;
        this.filterCodes();
    }

    /**
     * Handle category filter change
     */
    onCategoryChange(ev) {
        this.state.selectedCategory = ev.target.value;
        this.filterCodes();
    }

    /**
     * Toggle dropdown visibility
     */
    toggleDropdown() {
        this.state.isOpen = !this.state.isOpen;
    }

    /**
     * Close dropdown
     */
    closeDropdown() {
        this.state.isOpen = false;
    }

    /**
     * Handle code selection
     * Triggers the onCodeSelected callback with the selected code
     */
    selectCode(code) {
        if (this.props.onCodeSelected) {
            this.props.onCodeSelected(code);
        }
        this.closeDropdown();
    }

    /**
     * Get category label in French
     */
    getCategoryLabel(category) {
        const labels = {
            cotisation: "Cotisation",
            exoneration: "Exonération",
            reduction: "Réduction",
            autre: "Autre",
        };
        return labels[category] || category;
    }

    /**
     * Get category badge class
     */
    getCategoryBadgeClass(category) {
        const classes = {
            cotisation: "badge-primary",
            exoneration: "badge-success",
            reduction: "badge-info",
            autre: "badge-secondary",
        };
        return classes[category] || "badge-secondary";
    }
}

URSSAFCodeSelector.template = "construction_contract.URSSAFCodeSelector";
URSSAFCodeSelector.props = {
    onCodeSelected: { type: Function, optional: true },
};

registry.category("fields").add("urssaf_code_selector", URSSAFCodeSelector);
