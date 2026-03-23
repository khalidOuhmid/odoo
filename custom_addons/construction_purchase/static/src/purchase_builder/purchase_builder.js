/** @odoo-module **/
/**
 * PurchaseBuilder — Constructeur de Bons de Commande BLG
 * ========================================================
 * Composant Owl pour la création interactive de lignes de BdC.
 *
 * Règle d'or : AUCUN calcul monétaire en JS.
 * Tous les totaux (HT, TVA, TTC, sous-totaux par lot) sont fournis
 * exclusivement par le serveur via `get_builder_totals` / `save_builder_lines`.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";

const FLOOR_LEVELS = [
    { value: '', label: '— Niveau —' },
    { value: 'basement', label: 'Sous-sol' },
    { value: 'ground', label: 'Rez-de-chaussée' },
    { value: 'floor_1', label: 'Étage 1' },
    { value: 'floor_2', label: 'Étage 2' },
    { value: 'floor_3', label: 'Étage 3' },
    { value: 'attic', label: 'Combles' },
];

export class PurchaseBuilder extends Component {
    static template = "construction_purchase.PurchaseBuilder";
    static props = ["action", "actionType?"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this._nextUid = 1;

        this.floorLevels = FLOOR_LEVELS;

        this.state = useState({
            loading: true,
            saving: false,
            orderId: null,
            chantierName: '',
            partnerName: '',
            products: [],
            lots: [],
            cart: [],           // lignes en cours de composition (avant save)
            totals: null,       // {amount_untaxed, amount_tax, amount_total, lot_totals}
            searchTerm: '',
            selectedLotId: null,
            // Wizard édition d'une ligne
            showLineWizard: false,
            wizardLine: null,
        });

        this.debouncedSearch = debounce(this._performSearch.bind(this), 300);

        onWillStart(async () => {
            const ctx = this.props.action?.context || {};
            this.state.orderId = ctx.active_id || ctx.default_order_id || null;
            await Promise.all([
                this._loadOrder(),
                this._loadProducts(),
            ]);
            this.state.loading = false;
        });
    }

    // ─── Chargement ───────────────────────────────────────────

    async _loadOrder() {
        if (!this.state.orderId) return;
        try {
            const orders = await this.orm.searchRead(
                'purchase.order',
                [['id', '=', this.state.orderId]],
                ['name', 'chantier_id', 'partner_id', 'lot_ids', 'order_line']
            );
            if (!orders.length) return;
            const order = orders[0];
            this.state.chantierName = order.chantier_id?.[1] || '';
            this.state.partnerName = order.partner_id?.[1] || '';

            // Charger les lots du chantier
            if (order.chantier_id) {
                this.state.lots = await this.orm.searchRead(
                    'construction.lot',
                    [['chantier_id', '=', order.chantier_id[0]]],
                    ['id', 'name', 'code', 'category_id'],
                    { order: 'sequence, code' }
                );
            }

            // Charger les lignes existantes du BdC dans le cart
            await this._loadExistingLines();

            // Totaux serveur initiaux
            await this._refreshTotals();
        } catch (e) {
            console.error("PurchaseBuilder._loadOrder :", e);
            this.notification.add("Erreur lors du chargement du bon de commande.", { type: "danger" });
        }
    }

    async _loadExistingLines() {
        if (!this.state.orderId) return;
        try {
            const lines = await this.orm.searchRead(
                'purchase.order.line',
                [['order_id', '=', this.state.orderId], ['display_type', '=', false]],
                ['id', 'product_id', 'name', 'product_qty', 'price_unit',
                 'lot_id', 'room_location', 'floor_level', 'construction_notes'],
                { order: 'sequence, id' }
            );
            this.state.cart = lines.map(l => ({
                _uid: this._nextUid++,
                id: l.id,
                product_id: l.product_id?.[0] || null,
                name: l.name || '',
                product_qty: l.product_qty || 1,
                price_unit: l.price_unit || 0,
                lot_id: l.lot_id?.[0] || null,
                room_location: l.room_location || '',
                floor_level: l.floor_level || '',
                construction_notes: l.construction_notes || '',
            }));
        } catch (e) {
            console.error("PurchaseBuilder._loadExistingLines :", e);
            this.notification.add("Erreur lors du chargement des lignes du bon de commande.", { type: "danger" });
        }
    }

    async _loadProducts() {
        try {
            let lotCategoryId = null;
            if (this.state.selectedLotId) {
                const lot = this.state.lots.find(l => l.id === this.state.selectedLotId);
                if (lot?.category_id) {
                    lotCategoryId = Array.isArray(lot.category_id) ? lot.category_id[0] : lot.category_id;
                }
            }
            this.state.products = await this.orm.call(
                'purchase.order',
                'search_products_for_builder',
                [this.state.searchTerm || '', lotCategoryId, 100]
            );
        } catch (e) {
            console.error("PurchaseBuilder._loadProducts :", e);
            this.notification.add("Erreur lors du chargement des produits.", { type: "danger" });
        }
    }

    async _performSearch() {
        await this._loadProducts();
    }

    async _refreshTotals() {
        if (!this.state.orderId) return;
        try {
            this.state.totals = await this.orm.call(
                'purchase.order',
                'get_builder_totals',
                [this.state.orderId]
            );
        } catch (e) {
            this.state.totals = null;
        }
    }

    // ─── Interactions sidebar ─────────────────────────────────

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        this.debouncedSearch();
    }

    onLotFilter(lotId) {
        this.state.selectedLotId = lotId === this.state.selectedLotId ? null : lotId;
        this._loadProducts();
    }

    getLotLineCount(lotId) {
        return this.state.cart.filter(l => l.lot_id === lotId).length;
    }

    // ─── Ajout de ligne ───────────────────────────────────────

    onProductClick(product) {
        this.state.wizardLine = {
            _uid: this._nextUid++,
            id: null,
            product_id: product.id,
            name: product.display_name || product.name || '',
            product_qty: 1,
            price_unit: product.standard_price || 0,
            lot_id: this.state.selectedLotId || null,
            room_location: '',
            floor_level: '',
            construction_notes: '',
        };
        this.state.showLineWizard = true;
    }

    onCloseWizard() {
        this.state.showLineWizard = false;
        this.state.wizardLine = null;
    }

    onWizardField(field, ev) {
        if (this.state.wizardLine) {
            const val = ev.target.type === 'number'
                ? (parseFloat(ev.target.value) || 0)
                : ev.target.value;
            this.state.wizardLine[field] = val;
        }
    }

    onWizardLotChange(ev) {
        if (this.state.wizardLine) {
            this.state.wizardLine.lot_id = parseInt(ev.target.value) || null;
        }
    }

    onWizardFloorChange(ev) {
        if (this.state.wizardLine) {
            this.state.wizardLine.floor_level = ev.target.value || '';
        }
    }

    onConfirmWizard() {
        const wl = this.state.wizardLine;
        if (!wl) return;
        if (!wl.lot_id) {
            this.notification.add("Veuillez sélectionner un lot.", { type: "warning" });
            return;
        }
        // Edit existing or add new
        const existingIdx = this.state.cart.findIndex(l => l._uid === wl._uid);
        if (existingIdx >= 0) {
            this.state.cart[existingIdx] = { ...wl };
        } else {
            this.state.cart.push({ ...wl });
        }
        this.onCloseWizard();
    }

    // ─── Édition inline ───────────────────────────────────────

    onEditLine(line) {
        this.state.wizardLine = { ...line };
        this.state.showLineWizard = true;
    }

    onRemoveLine(uid) {
        const idx = this.state.cart.findIndex(l => l._uid === uid);
        if (idx >= 0) {
            this.state.cart.splice(idx, 1);
        }
    }

    // ─── Groupement par lot ───────────────────────────────────

    getGroupedCart() {
        const groups = {};
        this.state.cart.forEach(line => {
            const key = line.lot_id || 0;
            if (!groups[key]) {
                const lot = this.state.lots.find(l => l.id === line.lot_id);
                groups[key] = {
                    id: key,
                    label: lot ? `${lot.code} — ${lot.name}` : '⚠ Sans lot',
                    lines: [],
                };
            }
            groups[key].lines.push(line);
        });
        return Object.values(groups).sort((a, b) => {
            if (a.id === 0) return 1;
            if (b.id === 0) return -1;
            return a.label.localeCompare(b.label);
        });
    }

    getLotName(lotId) {
        const lot = this.state.lots.find(l => l.id === lotId);
        return lot ? `${lot.code} — ${lot.name}` : '—';
    }

    // ─── Sauvegarde ───────────────────────────────────────────

    async onSave() {
        if (!this.state.orderId) {
            this.notification.add("Aucun BdC ouvert.", { type: "warning" });
            return;
        }
        if (this.state.cart.length === 0) {
            this.notification.add("Aucune ligne à enregistrer.", { type: "warning" });
            return;
        }
        const missingLot = this.state.cart.filter(l => !l.lot_id);
        if (missingLot.length) {
            this.notification.add(`${missingLot.length} ligne(s) sans lot.`, { type: "danger" });
            return;
        }
        try {
            this.state.saving = true;
            const payload = this.state.cart.map(l => ({
                id: l.id || null,
                product_id: l.product_id,
                name: l.name,
                product_qty: l.product_qty,
                price_unit: l.price_unit,
                lot_id: l.lot_id || null,
                room_location: l.room_location || '',
                floor_level: l.floor_level || '',
                construction_notes: l.construction_notes || '',
            }));
            const totals = await this.orm.call(
                'purchase.order',
                'save_builder_lines',
                [this.state.orderId, payload]
            );
            this.state.totals = totals;
            // Reload lines to get server-assigned IDs
            await this._loadExistingLines();
            this.notification.add("BdC enregistré.", { type: "success" });
        } catch (e) {
            console.error("PurchaseBuilder.onSave :", e);
            const msg = e?.data?.message || "Erreur lors de la sauvegarde du bon de commande.";
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("construction_purchase.purchase_builder", PurchaseBuilder);
