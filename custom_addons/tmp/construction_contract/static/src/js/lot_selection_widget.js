/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

/**
 * LotSelectionWidget - Enhanced lot selection widget for construction contracts
 * 
 * Features:
 * - Checkbox-based selection with search functionality
 * - Category grouping (collapsible sections)
 * - Dual-list mode for large datasets (>50 lots)
 * - Displays amount, dates, and status per lot
 * - Select All / Deselect All actions
 * 
 * Requirements: 4.1, 4.4
 */
export class LotSelectionWidget extends Component {
    static template = "construction_contract.LotSelectionWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            lots: [],
            selectedIds: new Set(),
            searchTerm: "",
            categories: [],
            expandedCategories: new Set(),
            viewMode: "checkbox", // "checkbox" or "dual-list"
            loading: false,
            chantierId: null,
        });

        onWillStart(async () => {
            await this.initializeWidget();
        });

        onWillUpdateProps(async (nextProps) => {
            // Reload lots if chantier changes
            const newChantierId = this._getChantierId(nextProps);
            if (newChantierId !== this.state.chantierId) {
                this.state.chantierId = newChantierId;
                await this.loadLots(newChantierId);
            }
            // Update selected IDs from props
            this._syncSelectedFromProps(nextProps);
        });
    }

    async initializeWidget() {
        const chantierId = this._getChantierId(this.props);
        this.state.chantierId = chantierId;
        
        // Initialize selected IDs from current value
        this._syncSelectedFromProps(this.props);
        
        if (chantierId) {
            await this.loadLots(chantierId);
        }
    }

    _getChantierId(props) {
        // Get chantier_id from record data
        const record = props.record;
        if (record && record.data && record.data.chantier_id) {
            const chantierId = record.data.chantier_id;
            // Handle both [id, name] format and direct id
            return Array.isArray(chantierId) ? chantierId[0] : chantierId;
        }
        return null;
    }

    _syncSelectedFromProps(props) {
        const value = props.record.data[props.name];
        this.state.selectedIds.clear();
        
        if (value && value.records) {
            // Many2many field with records
            value.records.forEach(rec => this.state.selectedIds.add(rec.id));
        } else if (Array.isArray(value)) {
            // Array of IDs
            value.forEach(id => this.state.selectedIds.add(id));
        }
    }

    /**
     * Load lots from the server for the given chantier
     */
    async loadLots(chantierId) {
        if (!chantierId) {
            this.state.lots = [];
            this.state.categories = [];
            return;
        }

        this.state.loading = true;
        
        try {
            const lots = await this.orm.searchRead(
                "construction.lot",
                [["chantier_id", "=", chantierId]],
                ["id", "name", "code", "price", "lot_date_start", "lot_date_end", "is_finished", "quote_state", "urssaf_code"]
            );
            
            this.state.lots = lots.map(lot => ({
                ...lot,
                category: this._getCategoryFromCode(lot.code, lot.urssaf_code),
                statusLabel: this._getStatusLabel(lot),
                statusColor: this._getStatusColor(lot),
            }));
            
            this.categorize();
            
            // Switch to dual-list if > 50 lots
            if (lots.length > 50) {
                this.state.viewMode = "dual-list";
            } else {
                this.state.viewMode = "checkbox";
            }
        } catch (error) {
            console.error("Error loading lots:", error);
            this.notification.add(_t("Erreur lors du chargement des lots"), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Determine category from lot code or URSSAF code
     */
    _getCategoryFromCode(code, urssafCode) {
        const codeUpper = (code || "").toUpperCase();
        const urssafUpper = (urssafCode || "").toUpperCase();
        
        // Gros œuvre codes
        const grosOeuvre = ["GO", "MAC", "TER", "FND", "STR", "CHA", "COU"];
        // Second œuvre codes  
        const secondOeuvre = ["ELE", "PLO", "CVC", "ISO", "MEN", "SER", "CLO"];
        // Finitions codes
        const finitions = ["PEI", "REV", "CAR", "PAR", "FAU", "NET"];
        
        for (const prefix of grosOeuvre) {
            if (codeUpper.startsWith(prefix) || urssafUpper.includes(prefix)) {
                return "Gros œuvre";
            }
        }
        
        for (const prefix of secondOeuvre) {
            if (codeUpper.startsWith(prefix) || urssafUpper.includes(prefix)) {
                return "Second œuvre";
            }
        }
        
        for (const prefix of finitions) {
            if (codeUpper.startsWith(prefix) || urssafUpper.includes(prefix)) {
                return "Finitions";
            }
        }
        
        return "Autres";
    }

    /**
     * Get status label for a lot
     */
    _getStatusLabel(lot) {
        if (lot.is_finished) return _t("Terminé");
        if (lot.quote_state === "accepted") return _t("Accepté");
        if (lot.quote_state === "sent") return _t("Devis envoyé");
        if (lot.quote_state === "rejected") return _t("Rejeté");
        return _t("En cours");
    }

    /**
     * Get status color class for a lot
     */
    _getStatusColor(lot) {
        if (lot.is_finished) return "success";
        if (lot.quote_state === "accepted") return "primary";
        if (lot.quote_state === "sent") return "warning";
        if (lot.quote_state === "rejected") return "danger";
        return "secondary";
    }

    /**
     * Organize lots by category
     */
    categorize() {
        const categoryOrder = ["Gros œuvre", "Second œuvre", "Finitions", "Autres"];
        const categories = {};
        
        for (const lot of this.state.lots) {
            const cat = lot.category || "Autres";
            if (!categories[cat]) {
                categories[cat] = [];
            }
            categories[cat].push(lot);
        }
        
        // Sort categories by predefined order
        this.state.categories = categoryOrder
            .filter(cat => categories[cat] && categories[cat].length > 0)
            .map(cat => ({
                name: cat,
                lots: categories[cat],
                count: categories[cat].length,
            }));
        
        // Expand all categories by default
        this.state.expandedCategories = new Set(categoryOrder);
    }

    /**
     * Toggle lot selection
     */
    toggleLot(lotId) {
        if (this.props.readonly) return;
        
        if (this.state.selectedIds.has(lotId)) {
            this.state.selectedIds.delete(lotId);
        } else {
            this.state.selectedIds.add(lotId);
        }
        this._updateValue();
    }

    /**
     * Select all visible lots
     */
    selectAll() {
        if (this.props.readonly) return;
        
        const filteredLots = this.getFilteredLots();
        filteredLots.forEach(lot => this.state.selectedIds.add(lot.id));
        this._updateValue();
    }

    /**
     * Deselect all lots
     */
    deselectAll() {
        if (this.props.readonly) return;
        
        this.state.selectedIds.clear();
        this._updateValue();
    }

    /**
     * Select all lots in a category
     */
    selectCategory(categoryName) {
        if (this.props.readonly) return;
        
        const category = this.state.categories.find(c => c.name === categoryName);
        if (category) {
            category.lots.forEach(lot => this.state.selectedIds.add(lot.id));
            this._updateValue();
        }
    }

    /**
     * Deselect all lots in a category
     */
    deselectCategory(categoryName) {
        if (this.props.readonly) return;
        
        const category = this.state.categories.find(c => c.name === categoryName);
        if (category) {
            category.lots.forEach(lot => this.state.selectedIds.delete(lot.id));
            this._updateValue();
        }
    }

    /**
     * Toggle category expansion
     */
    toggleCategory(categoryName) {
        if (this.state.expandedCategories.has(categoryName)) {
            this.state.expandedCategories.delete(categoryName);
        } else {
            this.state.expandedCategories.add(categoryName);
        }
    }

    /**
     * Check if category is expanded
     */
    isCategoryExpanded(categoryName) {
        return this.state.expandedCategories.has(categoryName);
    }

    /**
     * Check if lot is selected
     */
    isSelected(lotId) {
        return this.state.selectedIds.has(lotId);
    }

    /**
     * Get filtered lots based on search term
     */
    getFilteredLots() {
        const searchTerm = this.state.searchTerm.toLowerCase().trim();
        if (!searchTerm) {
            return this.state.lots;
        }
        
        return this.state.lots.filter(lot => 
            (lot.name && lot.name.toLowerCase().includes(searchTerm)) ||
            (lot.code && lot.code.toLowerCase().includes(searchTerm))
        );
    }

    /**
     * Get filtered categories with their filtered lots
     */
    getFilteredCategories() {
        const searchTerm = this.state.searchTerm.toLowerCase().trim();
        
        if (!searchTerm) {
            return this.state.categories;
        }
        
        return this.state.categories
            .map(category => ({
                ...category,
                lots: category.lots.filter(lot =>
                    (lot.name && lot.name.toLowerCase().includes(searchTerm)) ||
                    (lot.code && lot.code.toLowerCase().includes(searchTerm))
                ),
            }))
            .filter(category => category.lots.length > 0);
    }

    /**
     * Get available (unselected) lots for dual-list mode
     */
    getAvailableLots() {
        return this.getFilteredLots().filter(lot => !this.state.selectedIds.has(lot.id));
    }

    /**
     * Get selected lots for dual-list mode
     */
    getSelectedLots() {
        return this.state.lots.filter(lot => this.state.selectedIds.has(lot.id));
    }

    /**
     * Move lot from available to selected (dual-list mode)
     */
    moveToSelected(lotId) {
        if (this.props.readonly) return;
        this.state.selectedIds.add(lotId);
        this._updateValue();
    }

    /**
     * Move lot from selected to available (dual-list mode)
     */
    moveToAvailable(lotId) {
        if (this.props.readonly) return;
        this.state.selectedIds.delete(lotId);
        this._updateValue();
    }

    /**
     * Move all available lots to selected (dual-list mode)
     */
    moveAllToSelected() {
        if (this.props.readonly) return;
        this.getAvailableLots().forEach(lot => this.state.selectedIds.add(lot.id));
        this._updateValue();
    }

    /**
     * Move all selected lots to available (dual-list mode)
     */
    moveAllToAvailable() {
        if (this.props.readonly) return;
        this.state.selectedIds.clear();
        this._updateValue();
    }

    /**
     * Update search term
     */
    onSearchInput(event) {
        this.state.searchTerm = event.target.value;
    }

    /**
     * Clear search
     */
    clearSearch() {
        this.state.searchTerm = "";
    }

    /**
     * Switch view mode
     */
    switchViewMode(mode) {
        this.state.viewMode = mode;
    }

    /**
     * Format price for display
     */
    formatPrice(price) {
        if (!price) return "-";
        return new Intl.NumberFormat("fr-FR", {
            style: "currency",
            currency: "EUR",
        }).format(price);
    }

    /**
     * Format date for display
     */
    formatDate(dateStr) {
        if (!dateStr) return "-";
        const date = new Date(dateStr);
        return date.toLocaleDateString("fr-FR", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        });
    }

    /**
     * Get count of selected lots in a category
     */
    getSelectedCountInCategory(categoryName) {
        const category = this.state.categories.find(c => c.name === categoryName);
        if (!category) return 0;
        return category.lots.filter(lot => this.state.selectedIds.has(lot.id)).length;
    }

    /**
     * Check if all lots in category are selected
     */
    isAllCategorySelected(categoryName) {
        const category = this.state.categories.find(c => c.name === categoryName);
        if (!category || category.lots.length === 0) return false;
        return category.lots.every(lot => this.state.selectedIds.has(lot.id));
    }

    /**
     * Update the field value
     */
    _updateValue() {
        const selectedIds = [...this.state.selectedIds];
        
        // Use replaceWith command for Many2many field
        this.props.record.update({
            [this.props.name]: [["set", selectedIds]],
        });
    }

    /**
     * Get summary text for selected lots
     */
    get selectionSummary() {
        const count = this.state.selectedIds.size;
        const total = this.state.lots.length;
        
        if (count === 0) {
            return _t("Aucun lot sélectionné");
        }
        
        const selectedLots = this.getSelectedLots();
        const totalAmount = selectedLots.reduce((sum, lot) => sum + (lot.price || 0), 0);
        
        return _t("%(count)s lot(s) sélectionné(s) sur %(total)s - Total: %(amount)s", {
            count: count,
            total: total,
            amount: this.formatPrice(totalAmount),
        });
    }
}

// Register the widget in the field registry
registry.category("fields").add("lot_selection", {
    component: LotSelectionWidget,
    supportedTypes: ["many2many"],
});
