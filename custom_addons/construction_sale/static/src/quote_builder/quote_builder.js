/** @odoo-module **/

import { Component, useState, onWillStart, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { debounce } from "@web/core/utils/timing";

/**
 * QuoteBuilder - Professional Construction Estimator
 * ===================================================
 * Production-ready quote builder with:
 * - Dimension Calculator ("Métré")
 * - Cost & Margin Cockpit (managers only)
 * - Lot-based organization
 * - LocalStorage persistence (F5-safe)
 * - Custom product creation wizard
 */
export class QuoteBuilder extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // Storage Keys - Note: cartStoreKey is set dynamically after orderId is known
        this.projectStoreKey = 'blg_active_project';
        this.baseCartStoreKey = 'blg_quote_draft';

        // Reactive State
        this.state = useState({
            loading: true,
            products: [],
            cart: [],
            chantierId: null,
            chantierName: "",
            orderId: null,
            searchTerm: "",
            selectedLotId: null,
            lots: [],
            uomList: [],
            showMargin: true,  // Always show margin fields
            defaultMargin: 50,  // Global margin default
            // Wizard states
            showLineConfigWizard: false,
            showCreateProductWizard: false,
            wizardProduct: null,
            newProduct: null,
            // US-SAL-003: Track modifications
            isDirty: false,
            // US-SAL-005: Reset confirmation modal
            showResetConfirm: false,
            resetConfirmChecked: false,
        });

        onWillStart(async () => {
            await this.initializeContext();
            // CRITICAL: Load existing lines FIRST if we have an order
            const existingLinesLoaded = await this.loadExistingOrderLines();
            // Only restore draft if no existing lines were found
            if (!existingLinesLoaded) {
                this.restoreDraft();
            }
            await this.loadInitialData();
        });

        // Auto-save with debounce
        useEffect(() => {
            this.saveDraft();
            this.state.isDirty = true;
        }, () => [this.state.cart, this.state.chantierId]);

        // US-SAL-003: Auto-save every 30 seconds
        useEffect(() => {
            const interval = setInterval(() => {
                if (this.state.cart.length > 0 && this.state.isDirty) {
                    this.saveDraft();
                    this.notification.add("Brouillon sauvegardé", { type: "info", sticky: false });
                    console.log('[QuoteBuilder] Auto-save triggered');
                }
            }, 30000);
            return () => clearInterval(interval);
        }, () => []);

        // US-SAL-003: Warning on page exit with unsaved changes
        useEffect(() => {
            const handleBeforeUnload = (e) => {
                if (this.state.cart.length > 0 && this.state.isDirty) {
                    e.preventDefault();
                    e.returnValue = 'Vous avez des modifications non sauvegardées.';
                    return e.returnValue;
                }
            };
            window.addEventListener('beforeunload', handleBeforeUnload);
            return () => window.removeEventListener('beforeunload', handleBeforeUnload);
        }, () => []);

        // Debounced search
        this.debouncedSearch = debounce(this._performSearch.bind(this), 300);
    }

    // ===========================================
    // CONTEXT INITIALIZATION
    // ===========================================

    async initializeContext() {
        console.log('[QuoteBuilder] Initializing...');

        let chantierId = this.props.action?.context?.default_chantier_id;
        let orderId = this.props.action?.context?.default_order_id;

        if (!chantierId) {
            const stored = localStorage.getItem(this.projectStoreKey);
            if (stored) {
                try {
                    const parsed = JSON.parse(stored);
                    chantierId = parsed.chantierId;
                    orderId = parsed.orderId;
                } catch (e) {
                    console.warn('[QuoteBuilder] Failed to parse stored project');
                }
            }
        }

        if (chantierId) {
            this.persistProjectContext(chantierId, orderId);
            this.state.chantierId = chantierId;
            this.state.orderId = orderId;
        }
    }

    persistProjectContext(chantierId, orderId) {
        localStorage.setItem(this.projectStoreKey, JSON.stringify({
            chantierId,
            orderId,
            timestamp: new Date().toISOString()
        }));
    }

    // ===========================================
    // DATA LOADING
    // ===========================================

    async loadInitialData() {
        try {
            // Load products (unfiltered initially)
            const products = await this.orm.call(
                "sale.order",
                "search_products_for_spa",
                ["", null],  // search_term, lot_category_id
                { limit: 100 }
            );
            this.state.products = products;

            if (this.state.chantierId) {
                await this.loadChantierDetails(this.state.chantierId);
            }
        } catch (e) {
            console.error("[QuoteBuilder] Load error", e);
            this.notification.add("Erreur chargement", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async loadProducts() {
        try {
            this.state.loading = true;

            // FIX FILTRAGE: Get the category_id of the selected lot
            let lotCategoryId = null;
            if (this.state.selectedLotId) {
                const selectedLot = this.state.lots.find(l => l.id === this.state.selectedLotId);
                console.log("[QuoteBuilder] Selected lot:", selectedLot);

                if (selectedLot && selectedLot.category_id) {
                    // Many2one returns [id, name] array
                    lotCategoryId = Array.isArray(selectedLot.category_id)
                        ? selectedLot.category_id[0]
                        : selectedLot.category_id;
                    console.log("[QuoteBuilder] Filtering by category_id:", lotCategoryId);
                } else {
                    console.warn("[QuoteBuilder] Selected lot has no category_id:", selectedLot);
                }
            } else {
                console.log("[QuoteBuilder] No lot selected, showing all products");
            }

            console.log("[QuoteBuilder] Calling RPC with search_term:", this.state.searchTerm, "lot_category_id:", lotCategoryId);

            this.state.products = await this.orm.call(
                "sale.order",
                "search_products_for_spa",
                [this.state.searchTerm || "", lotCategoryId, 100]  // Pass all positional args
            );

            console.log("[QuoteBuilder] Loaded", this.state.products.length, "products");
        } catch (e) {
            console.error("[QuoteBuilder] Refresh error", e);
        } finally {
            this.state.loading = false;
        }
    }

    async loadChantierDetails(chantierId) {
        try {
            const chantiers = await this.orm.searchRead(
                "construction.chantier",
                [["id", "=", chantierId]],
                ["name", "lots_ids"]
            );

            if (chantiers.length > 0) {
                this.state.chantierName = chantiers[0].name;

                if (chantiers[0].lots_ids?.length > 0) {
                    // FIX FILTRAGE: Also fetch category_id for lot filtering
                    this.state.lots = await this.orm.searchRead(
                        "construction.lot",
                        [["id", "in", chantiers[0].lots_ids]],
                        ["id", "name", "code", "category_id"]
                    );
                }
            }
        } catch (e) {
            console.error("[QuoteBuilder] Chantier load error", e);
        }
    }

    /**
     * TASK 2: Load existing order lines into cart
     * When opening builder on existing quote S00123, populate cart with existing lines
     */
    async loadExistingOrderLines() {
        const orderId = this.state.orderId || this.props.action?.context?.active_id;

        if (!orderId) {
            console.log('[QuoteBuilder] No order ID - starting with empty cart');
            return false;
        }

        try {
            console.log('[QuoteBuilder] Loading existing lines for order:', orderId);

            // Fetch all lines for this order
            const lines = await this.orm.searchRead(
                "sale.order.line",
                [["order_id", "=", orderId], ["display_type", "=", false]],
                [
                    "id", "product_id", "name", "product_uom_qty", "price_unit",
                    "lot_id", "room_location", "color", "construction_notes",
                    "dimension_l", "dimension_w", "dimension_h",
                    "price_buy", "target_margin_percent"
                ],
                { order: "sequence, id" }
            );

            if (lines.length === 0) {
                console.log('[QuoteBuilder] No existing lines found');
                return false;
            }

            // Convert to cart format, grouped by lot
            const cartItems = lines.map(line => ({
                id: line.id,  // Keep server ID for updates
                product_id: line.product_id?.[0],
                name: line.name,
                qty: line.product_uom_qty,
                price_unit: line.price_unit,
                price_buy: line.price_buy || 0,
                target_margin_percent: line.target_margin_percent || 50,
                lot_id: line.lot_id?.[0] || null,
                dimension_l: line.dimension_l || 0,
                dimension_w: line.dimension_w || 0,
                dimension_h: line.dimension_h || 0,
                isOptional: false,
                specs: {
                    location: line.room_location || '',
                    color: line.color || '',
                    notes: line.construction_notes || '',
                },
            }));

            // Sort by lot for proper grouping
            cartItems.sort((a, b) => (a.lot_id || 0) - (b.lot_id || 0));

            this.state.cart = cartItems;
            console.log('[QuoteBuilder] Loaded', cartItems.length, 'existing lines');

            return true;
        } catch (e) {
            console.error('[QuoteBuilder] Error loading existing lines:', e);
            return false;
        }
    }

    async checkUserPermissions() {
        // Margin always visible - no permission check needed
        this.state.showMargin = true;
    }

    // ===========================================
    // SEARCH HANDLERS
    // ===========================================

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        this.debouncedSearch();
    }

    async _performSearch() {
        await this.loadProducts();
    }

    // ===========================================
    // LOT HANDLERS
    // ===========================================

    onLotClick(lotId) {
        // Toggle lot selection
        this.state.selectedLotId = lotId === this.state.selectedLotId ? null : lotId;
        // FIX FILTRAGE: Reload products when lot selection changes
        this.loadProducts();
    }

    getLotItemCount(lotId) {
        return this.state.cart.filter(l => l.lot_id === lotId).length;
    }

    // Global margin change
    onGlobalMarginChange(ev) {
        const margin = parseFloat(ev.target.value) || 50;
        if (margin >= 0) {
            this.state.defaultMargin = margin;
            // Also apply to all existing lines that haven't been manually changed
            this.state.cart.forEach(line => {
                line.target_margin_percent = margin;
                line.price_unit = this.calculatePriceFromMargin(line.price_buy, margin);
            });
        }
    }

    // ===========================================
    // CREATE PRODUCT WIZARD
    // ===========================================

    async onCreateProduct() {
        if (this.state.uomList.length === 0) {
            try {
                this.state.uomList = await this.orm.searchRead(
                    "uom.uom",
                    [],
                    ["id", "name"],
                    { limit: 100 }
                );
            } catch (e) {
                console.warn('[QuoteBuilder] UoM load failed');
            }
        }

        this.state.newProduct = {
            name: "",
            color: "",
            uom_id: null,
            dimension_l: 0,
            dimension_w: 0,
            list_price: 0,
            standard_price: 0,
            lot_ids: [],
        };
        this.state.showCreateProductWizard = true;
    }

    onCloseCreateProductWizard() {
        this.state.showCreateProductWizard = false;
        this.state.newProduct = null;
    }

    onNewProductNameChange(ev) {
        if (this.state.newProduct) {
            this.state.newProduct.name = ev.target.value;
        }
    }

    onNewProductColorChange(ev) {
        if (this.state.newProduct) {
            this.state.newProduct.color = ev.target.value;
        }
    }

    onNewProductUomChange(ev) {
        if (this.state.newProduct) {
            this.state.newProduct.uom_id = parseInt(ev.target.value) || null;
        }
    }

    onNewProductDimLChange(ev) {
        if (this.state.newProduct) {
            this.state.newProduct.dimension_l = parseFloat(ev.target.value) || 0;
        }
    }

    onNewProductDimWChange(ev) {
        if (this.state.newProduct) {
            this.state.newProduct.dimension_w = parseFloat(ev.target.value) || 0;
        }
    }

    onNewProductPriceChange(ev) {
        if (this.state.newProduct) {
            this.state.newProduct.list_price = parseFloat(ev.target.value) || 0;
        }
    }

    onNewProductCostChange(ev) {
        if (this.state.newProduct) {
            this.state.newProduct.standard_price = parseFloat(ev.target.value) || 0;
        }
    }

    onToggleNewProductLot(lotId) {
        if (!this.state.newProduct) return;
        const idx = this.state.newProduct.lot_ids.indexOf(lotId);
        if (idx >= 0) {
            this.state.newProduct.lot_ids.splice(idx, 1);
        } else {
            this.state.newProduct.lot_ids.push(lotId);
        }
    }

    async onConfirmCreateProductWizard() {
        const np = this.state.newProduct;
        if (!np?.name?.trim()) {
            this.notification.add("Nom obligatoire", { type: "danger" });
            return;
        }
        if (!np.uom_id) {
            this.notification.add("Unité de mesure obligatoire", { type: "danger" });
            return;
        }

        try {
            this.state.loading = true;

            // The entered price is the COST (what we pay)
            // list_price is calculated by applying the default margin
            const cost = np.list_price || 0;  // User enters this
            const sellingPrice = cost > 0
                ? this.calculatePriceFromMargin(cost, this.state.defaultMargin)
                : 0;

            console.log('[QuoteBuilder] Creating product:', {
                name: np.name?.trim(),
                uom_id: np.uom_id,
                cost: cost,
                sellingPrice: sellingPrice
            });

            // FIX: Get lot_category_ids from the WIZARD'S lot_ids selection (not sidebar)
            // The user selects multiple lots in the wizard, we need to extract their category_ids
            let lotCategoryIds = [];

            if (np.lot_ids && np.lot_ids.length > 0) {
                // Get category_id from each selected lot
                for (const lotId of np.lot_ids) {
                    const lot = this.state.lots.find(l => l.id === lotId);
                    if (lot && lot.category_id) {
                        const catId = Array.isArray(lot.category_id) ? lot.category_id[0] : lot.category_id;
                        if (catId && !lotCategoryIds.includes(catId)) {
                            lotCategoryIds.push(catId);
                        }
                    }
                }
                console.log('[QuoteBuilder] Assigning lot_category_ids from wizard:', lotCategoryIds);
            } else if (this.state.selectedLotId) {
                // Fallback: use sidebar selected lot if no lots in wizard
                const selectedLot = this.state.lots.find(l => l.id === this.state.selectedLotId);
                if (selectedLot && selectedLot.category_id) {
                    const catId = Array.isArray(selectedLot.category_id)
                        ? selectedLot.category_id[0]
                        : selectedLot.category_id;
                    if (catId) lotCategoryIds.push(catId);
                    console.log('[QuoteBuilder] Fallback: using sidebar lot_category_id:', catId);
                }
            }

            // Create product with cost, calculated selling price, and lot_category_ids (Many2many)
            const productData = {
                name: np.name.trim(),
                uom_id: np.uom_id,
                uom_po_id: np.uom_id,
                standard_price: cost,  // Save entered price as COST
                list_price: sellingPrice,  // Calculate selling price with margin
                sale_ok: true,
            };

            // Add lot_category_ids (Many2many) if any categories were found
            // Use Odoo command format: [[6, 0, [ids]]] to set the relation
            if (lotCategoryIds.length > 0) {
                productData.lot_category_ids = [[6, 0, lotCategoryIds]];
            }

            const result = await this.orm.create("product.template", [productData]);
            console.log('[QuoteBuilder] Created product ID:', result);

            this.notification.add(`✓ Produit créé: ${np.name}`, { type: "success" });
            await this.loadProducts();
            this.onCloseCreateProductWizard();
        } catch (e) {
            console.error('[QuoteBuilder] Create error', e);
            // Extract server error message if available
            const serverMsg = e?.data?.message || e?.message || "Création impossible";
            this.notification.add("Erreur: " + serverMsg, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // ===========================================
    // LINE CONFIG WIZARD
    // ===========================================

    onProductClick(product) {
        const uomType = this.getUomType(product);
        const margin = this.state.defaultMargin;  // Use global margin

        // Logic:
        // - If product has standard_price (cost) → use it as cost, apply margin to get selling price
        // - If no standard_price → use list_price as selling price, cost = 0
        let cost, price;

        if (product.standard_price && product.standard_price > 0) {
            // Product has a cost → calculate selling price with margin
            cost = product.standard_price;
            price = this.calculatePriceFromMargin(cost, margin);
        } else {
            // Product has no cost → use list_price directly as selling price
            cost = 0;
            price = product.list_price || 0;
        }

        this.state.wizardProduct = {
            id: product.id,
            overrideName: product.name || product.display_name,
            location: "",
            color: "",
            notes: "",
            qty: 1,
            price_buy: cost,
            target_margin_percent: margin,
            price_unit: price,
            lot_id: this.state.selectedLotId,
            isOptional: false,
            uom_type: uomType,
            dimension_l: 0,
            dimension_w: 0,
            dimension_h: 0,
        };
        this.state.showLineConfigWizard = true;
    }

    onCloseLineWizard() {
        this.state.showLineConfigWizard = false;
        this.state.wizardProduct = null;
    }

    onWizardNameChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.overrideName = ev.target.value;
        }
    }

    onWizardQtyChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.qty = parseFloat(ev.target.value) || 1;
        }
    }

    onWizardLocationChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.location = ev.target.value;
        }
    }

    onWizardColorChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.color = ev.target.value;
        }
    }

    onWizardLotChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.lot_id = parseInt(ev.target.value) || null;
        }
    }

    onWizardMarginChange(ev) {
        if (this.state.wizardProduct) {
            const margin = parseFloat(ev.target.value) || 50;
            this.state.wizardProduct.target_margin_percent = margin;
            this.state.wizardProduct.price_unit = this.calculatePriceFromMargin(
                this.state.wizardProduct.price_buy,
                margin
            );
        }
    }

    onWizardNotesChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.notes = ev.target.value;
        }
    }

    onWizardOptionalToggle() {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.isOptional = !this.state.wizardProduct.isOptional;
        }
    }

    onWizardDimLChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.dimension_l = parseFloat(ev.target.value) || 0;
            this.recalculateWizardQty();
        }
    }

    onWizardDimWChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.dimension_w = parseFloat(ev.target.value) || 0;
            this.recalculateWizardQty();
        }
    }

    onWizardDimHChange(ev) {
        if (this.state.wizardProduct) {
            this.state.wizardProduct.dimension_h = parseFloat(ev.target.value) || 0;
            this.recalculateWizardQty();
        }
    }

    recalculateWizardQty() {
        const wp = this.state.wizardProduct;
        if (!wp) return;

        const l = wp.dimension_l || 0;
        const w = wp.dimension_w || 0;
        const h = wp.dimension_h || 0;

        let qty = 1;
        switch (wp.uom_type) {
            case 'ml':
                qty = l > 0 ? l : 1;
                break;
            case 'm2':
                qty = (l > 0 && w > 0) ? l * w : 1;
                break;
            case 'm3':
                qty = (l > 0 && w > 0 && h > 0) ? l * w * h : 1;
                break;
            default:
                qty = 1;
        }

        this.state.wizardProduct.qty = parseFloat(qty.toFixed(3));
    }

    onConfirmLineWizard() {
        const wp = this.state.wizardProduct;
        if (!wp) return;

        this.state.cart.push({
            product_id: wp.id,
            name: wp.overrideName,
            qty: wp.qty,
            price_unit: wp.price_unit,
            price_buy: wp.price_buy,
            target_margin_percent: wp.target_margin_percent,
            lot_id: wp.lot_id,
            uom_type: wp.uom_type,
            dimension_l: wp.dimension_l,
            dimension_w: wp.dimension_w,
            dimension_h: wp.dimension_h,
            isOptional: wp.isOptional,
            specs: {
                location: wp.location,
                color: wp.color,
                notes: wp.notes,
            },
        });

        this.notification.add(`✓ Ajouté: ${wp.overrideName}`, { type: "success" });
        this.onCloseLineWizard();
    }

    // ===========================================
    // CART INLINE EDITING
    // ===========================================

    onLineNameChange(ev, index) {
        if (this.state.cart[index]) {
            this.state.cart[index].name = ev.target.value;
        }
    }

    onLineDimLChange(ev, index) {
        if (this.state.cart[index]) {
            this.state.cart[index].dimension_l = parseFloat(ev.target.value) || 0;
            this.recalculateLineQty(index);
        }
    }

    onLineDimWChange(ev, index) {
        if (this.state.cart[index]) {
            this.state.cart[index].dimension_w = parseFloat(ev.target.value) || 0;
            this.recalculateLineQty(index);
        }
    }

    onLineDimHChange(ev, index) {
        if (this.state.cart[index]) {
            this.state.cart[index].dimension_h = parseFloat(ev.target.value) || 0;
            this.recalculateLineQty(index);
        }
    }

    onLineQtyChange(ev, index) {
        if (this.state.cart[index]) {
            this.state.cart[index].qty = parseFloat(ev.target.value) || 1;
        }
    }

    onLineCostChange(ev, index) {
        const line = this.state.cart[index];
        if (line) {
            const cost = parseFloat(ev.target.value);
            if (cost <= 0) {
                this.notification.add("Le coût doit être supérieur à 0", { type: "danger" });
                // Reset to previous value logic is hard without tracking, but UI will show invalid
                return;
            }
            line.price_buy = cost;
            // Recalculate selling price to maintain margin
            line.price_unit = this.calculatePriceFromMargin(cost, line.target_margin_percent);
        }
    }

    onLineMarginChange(ev, index) {
        const line = this.state.cart[index];
        if (line) {
            const margin = parseFloat(ev.target.value) || 50;
            if (margin >= 0 && margin < 500) {
                line.target_margin_percent = margin;
                line.price_unit = this.calculatePriceFromMargin(line.price_buy, margin);
            }
        }
    }

    onLineOptionalToggle(index) {
        if (this.state.cart[index]) {
            this.state.cart[index].isOptional = !this.state.cart[index].isOptional;
        }
    }

    onRemoveLine(index) {
        const line = this.state.cart[index];
        this.state.cart.splice(index, 1);
        this.notification.add(`Supprimé: ${line?.name}`, { type: "info" });
    }

    recalculateLineQty(index) {
        const line = this.state.cart[index];
        if (!line) return;

        const L = line.dimension_l || 0;
        const W = line.dimension_w || 0;
        const H = line.dimension_h || 0;

        if (line.uom_type === 'm2' && L > 0 && W > 0) {
            line.qty = L * W;
        } else if (line.uom_type === 'm3' && L > 0 && W > 0 && H > 0) {
            line.qty = L * W * H;
        } else if (line.uom_type === 'ml' && L > 0) {
            line.qty = L;
        }
    }

    // ===========================================
    // UTILITIES
    // ===========================================

    getUomType(product) {
        if (!product.uom_id) return 'unit';
        const uomName = (product.uom_id[1] || '').toLowerCase();
        if (uomName.includes('m²') || uomName.includes('m2')) return 'm2';
        if (uomName.includes('m³') || uomName.includes('m3')) return 'm3';
        if (uomName.includes('ml') || uomName === 'm') return 'ml';
        return 'unit';
    }

    calculatePriceFromMargin(cost, marginPercent) {
        // MARKUP formula: selling_price = cost * (1 + markup%/100)
        // For 15€ cost and 50% markup: 15 * 1.50 = 22.50€
        // Profit = 22.50 - 15 = 7.50€ (50% of the cost)
        if (cost <= 0) return 0;
        if (marginPercent < 0) return cost;

        return cost * (1 + marginPercent / 100);
    }

    formatMoney(amount) {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR'
        }).format(amount || 0);
    }

    getTotalQty() {
        return this.state.cart.reduce((sum, l) => sum + l.qty, 0);
    }

    getCartTotal() {
        return this.state.cart
            .filter(l => !l.isOptional)
            .reduce((sum, l) => sum + (l.qty * l.price_unit), 0);
    }

    getCartCost() {
        return this.state.cart
            .filter(l => !l.isOptional)
            .reduce((sum, l) => sum + (l.qty * (l.price_buy || 0)), 0);
    }

    getCartMargin() {
        return this.getCartTotal() - this.getCartCost();
    }

    getCartMarginPercent() {
        // FIXED: Show MARKUP percentage (margin/cost), not margin on revenue
        // User enters 50% markup → should see 50% displayed
        const cost = this.getCartCost();
        return cost === 0 ? 0 : (this.getCartMargin() / cost) * 100;
    }

    getGroupedCart() {
        const groups = {};
        this.state.cart.forEach((line, idx) => {
            // FIX: Do NOT filter cart lines by selected lot
            // The lot selection only affects the product CATALOG, not the cart display
            // All cart lines should always be visible, grouped by their lot

            const lotId = line.lot_id || 'unassigned';
            if (!groups[lotId]) {
                const lot = this.state.lots.find(l => l.id === line.lot_id);
                groups[lotId] = {
                    id: lotId,
                    name: lot ? `${lot.code} - ${lot.name}` : '⚠️ Sans Lot',
                    lines: [],
                    total: 0
                };
            }
            groups[lotId].lines.push({ ...line, _index: idx });
            if (!line.isOptional) {
                groups[lotId].total += line.qty * line.price_unit;
            }
        });

        return Object.values(groups).sort((a, b) => {
            if (a.id === 'unassigned') return 1;
            if (b.id === 'unassigned') return -1;
            return a.name.localeCompare(b.name);
        });
    }

    getLineIndex(line) {
        return line._index;
    }

    // ===========================================
    // PERSISTENCE
    // ===========================================

    restoreDraft() {
        const cartKey = this.getCartStoreKey();
        if (!cartKey) return; // No orderId yet, skip restore

        const saved = localStorage.getItem(cartKey);
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                // Only restore if same chantier AND same order
                if (parsed.chantierId === this.state.chantierId &&
                    parsed.orderId === this.state.orderId) {
                    this.state.cart = parsed.cart || [];
                    if (this.state.cart.length > 0) {
                        this.notification.add(`Brouillon restauré (${this.state.cart.length})`, { type: "info" });
                    }
                }
            } catch (e) {
                console.warn('[QuoteBuilder] Restore failed');
            }
        }
    }

    saveDraft() {
        const cartKey = this.getCartStoreKey();
        if (!cartKey) return; // No orderId yet, skip save

        localStorage.setItem(cartKey, JSON.stringify({
            cart: this.state.cart,
            chantierId: this.state.chantierId,
            orderId: this.state.orderId,
            timestamp: new Date().toISOString(),
        }));
    }

    // Methods moved to use the improved versions below

    getCartStoreKey() {
        // CRITICAL: Each order has its own storage key to prevent data pollution
        const orderId = this.state.orderId;
        if (!orderId) return null;
        return `${this.baseCartStoreKey}_order_${orderId}`;
    }

    clearDraft() {
        const cartKey = this.getCartStoreKey();
        if (cartKey) {
            localStorage.removeItem(cartKey);
        }
        this.state.cart = [];
        this.state.isDirty = false;
        this.state.showResetConfirm = false;
        this.state.resetConfirmChecked = false;
        this.notification.add("Panier réinitialisé", { type: "warning" });
    }

    // US-SAL-005: Reset confirmation modal handlers
    onResetClick() {
        this.state.showResetConfirm = true;
        this.state.resetConfirmChecked = false;
    }

    onResetConfirmCheckbox(ev) {
        this.state.resetConfirmChecked = ev.target.checked;
    }

    onCancelReset() {
        this.state.showResetConfirm = false;
        this.state.resetConfirmChecked = false;
    }

    onConfirmReset() {
        if (this.state.resetConfirmChecked) {
            this.clearDraft();
        }
    }

    // ===========================================
    // QUOTE CREATION
    // ===========================================

    async createQuote() {
        const billableLines = this.state.cart.filter(l => !l.isOptional);

        if (!billableLines.length) {
            this.notification.add("Aucune ligne facturable", { type: "warning" });
            return;
        }

        if (!this.state.chantierId) {
            this.notification.add("⚠️ Aucun chantier lié", { type: "danger" });
            return;
        }

        const missingLots = this.state.cart.filter(l => !l.lot_id && !l.isOptional);
        if (missingLots.length > 0) {
            this.notification.add(`${missingLots.length} ligne(s) sans lot`, { type: "danger" });
            return;
        }

        try {
            this.state.loading = true;

            // Get chantier info to get partner_id
            const chantierData = await this.orm.searchRead(
                "construction.chantier",
                [["id", "=", this.state.chantierId]],
                ["client"]
            );

            const partnerId = chantierData[0]?.client?.[0];
            if (!partnerId) {
                this.notification.add("Aucun client sur le chantier", { type: "danger" });
                return;
            }

            // Build order lines data
            const orderLineData = this.state.cart.filter(l => !l.isOptional).map(line => [0, 0, {
                product_id: line.product_id,
                name: line.name + (line.specs?.location ? ` (${line.specs.location})` : ''),
                product_uom_qty: line.qty,
                price_unit: line.price_unit,
                price_buy: line.price_buy,
                target_margin_percent: line.target_margin_percent,
                lot_id: line.lot_id,  // Required for construction orders
            }]);

            let orderId = this.state.orderId;

            if (orderId) {
                // Check if order is confirmed (can't modify confirmed orders in Odoo)
                const orderInfo = await this.orm.searchRead(
                    "sale.order",
                    [["id", "=", orderId]],
                    ["state", "name"]
                );

                const orderState = orderInfo[0]?.state;
                const orderName = orderInfo[0]?.name || "Quote";

                if (orderState === 'sale' || orderState === 'done') {
                    // CONFIRMED ORDER: Cannot modify lines, create a new revision
                    console.log("[QuoteBuilder] Order is confirmed, creating revision...");

                    // Generate v2 name (or v3, v4, etc.)
                    let newName = orderName;
                    const versionMatch = orderName.match(/-v(\d+)$/);
                    if (versionMatch) {
                        const nextVersion = parseInt(versionMatch[1]) + 1;
                        newName = orderName.replace(/-v\d+$/, `-v${nextVersion}`);
                    } else {
                        newName = `${orderName}-v2`;
                    }

                    // Create new order as revision
                    const newOrderData = await this.orm.call("sale.order", "create_from_spa", [{
                        chantier_id: this.state.chantierId,
                        partner_id: partnerId,
                        order_line: orderLineData,
                        name_override: newName  // Pass custom name if supported
                    }]);

                    orderId = newOrderData.id;
                    this.state.orderId = orderId;
                    this.persistProjectContext(this.state.chantierId, orderId);

                    this.notification.add(`✅ Nouvelle version créée: ${newName}`, { type: "success" });
                } else {
                    // DRAFT ORDER: Can update normally
                    console.log("[QuoteBuilder] Updating draft order:", orderId);

                    const lineCommands = [
                        [5, 0, 0],  // Clear all existing lines
                        ...this.state.cart.filter(l => !l.isOptional).map(line => [0, 0, {
                            product_id: line.product_id,
                            name: line.name + (line.specs?.location ? ` (${line.specs.location})` : ''),
                            product_uom_qty: line.qty,
                            price_unit: line.price_unit,
                            lot_id: line.lot_id,
                        }])
                    ];

                    await this.orm.write("sale.order", [orderId], {
                        order_line: lineCommands
                    });

                    this.notification.add("✅ Devis mis à jour!", { type: "success" });
                }
            } else {
                // CREATE new order
                console.log("[QuoteBuilder] Creating new order for chantier:", this.state.chantierId);

                const orderData = await this.orm.call("sale.order", "create_from_spa", [{
                    chantier_id: this.state.chantierId,
                    partner_id: partnerId,
                    order_line: orderLineData
                }]);

                orderId = orderData.id;
                this.state.orderId = orderId;
                this.persistProjectContext(this.state.chantierId, orderId);

                this.notification.add("✅ Devis créé!", { type: "success" });
            }

            localStorage.removeItem(this.cartStoreKey);

            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'sale.order',
                res_id: orderId,
                views: [[false, 'form']],
            });
        } catch (e) {
            console.error("[QuoteBuilder] Save failed", e);
            this.notification.add("Erreur: " + (e.message || "Sauvegarde impossible"), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

QuoteBuilder.template = "construction_sale.QuoteBuilder";
registry.category("actions").add("construction_sale.quote_builder", QuoteBuilder);
