/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class LotProductSelector extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.state = useState({
            selectedLot: null,
            lots: [],
            products: [],
            loading: false
        });
        
        this.loadLots();
    }

    async loadLots() {
        if (this.props.chantier_id) {
            this.state.loading = true;
            try {
                const chantier = await this.orm.read("construction.chantier", [this.props.chantier_id], ["lots_ids"]);
                if (chantier.length > 0 && chantier[0].lots_ids.length > 0) {
                    this.state.lots = await this.orm.read("lot", chantier[0].lots_ids, ["name", "sequence"]);
                }
            } catch (error) {
                console.error("Erreur lors du chargement des lots:", error);
            }
            this.state.loading = false;
        }
    }

    async onLotSelected(lotId) {
        this.state.selectedLot = lotId;
        this.state.loading = true;
        
        try {
            // Charger les produits associés au lot
            const products = await this.orm.searchRead(
                "product.product",
                [["sale_ok", "=", true]],
                ["name", "list_price", "image_128"],
                { limit: 20 }
            );
            this.state.products = products;
        } catch (error) {
            console.error("Erreur lors du chargement des produits:", error);
        }
        
        this.state.loading = false;
    }

    async addProductToQuote(productId) {
        try {
            const action = await this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Ajouter produit',
                res_model: 'construction.quote.product.wizard',
                view_mode: 'form',
                target: 'new',
                context: {
                    default_sale_order_id: this.props.sale_order_id,
                    default_lot_id: this.state.selectedLot,
                    default_product_id: productId
                }
            });
            
            // Notification de succès
            this.notification.add("Produit ajouté au devis", { type: "success" });
            
        } catch (error) {
            console.error("Erreur lors de l'ajout du produit:", error);
            this.notification.add("Erreur lors de l'ajout du produit", { type: "danger" });
        }
    }
}

LotProductSelector.template = "construction_sale.LotProductSelector";
LotProductSelector.props = {
    chantier_id: { type: Number, optional: true },
    sale_order_id: { type: Number, optional: true }
};

registry.category("components").add("LotProductSelector", LotProductSelector); 