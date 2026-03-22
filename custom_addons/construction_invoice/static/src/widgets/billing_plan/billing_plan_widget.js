/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * BillingPlanWidget
 * =================
 * Replaces the inline One2many list of billing steps in the chantier form.
 * Reads/writes billing steps directly via RPC for immediate feedback.
 *
 * Features:
 *  - Step list: sequence badge (BLG bordeaux), editable name & %, computed amount, state badge
 *  - Progress bar: turns red if total > 100%
 *  - "Appliquer modèle 30/30/40" with confirmation if draft steps exist
 *  - Add / delete draft steps inline
 *  - "Créer la facture" button on draft steps
 */
export class BillingPlanWidget extends Component {
    static template = "construction_invoice.BillingPlanWidget";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            steps: [],
            cycleData: null,
            loading: false,
            editingId: null,          // id of step currently being edited
            editName: "",
            editPercent: 0,
        });

        onWillStart(async () => {
            await this.loadSteps();
        });

        onWillUpdateProps(async (nextProps) => {
            const newCycleId = this._getCycleId(nextProps.record);
            if (newCycleId !== this.cycleId) {
                await this.loadSteps(newCycleId);
            }
        });
    }

    // ── Helpers ────────────────────────────────────────────────────────────────

    _getCycleId(record) {
        const val = record.data.billing_cycle_id;
        if (!val) return null;
        if (Array.isArray(val)) return val[0] || null;
        if (typeof val === "object" && val.id) return val.id;
        return null;
    }

    get cycleId() {
        return this._getCycleId(this.props.record);
    }

    get totalPercent() {
        return this.state.steps.reduce((acc, s) => acc + (s.percentage || 0), 0);
    }

    get isOverBilled() {
        return this.totalPercent > 100.001;
    }

    get progressBarWidth() {
        return Math.min(this.totalPercent, 100);
    }

    get totalAmount() {
        return this.state.cycleData ? this.state.cycleData.total_amount_confirmed : 0;
    }

    formatAmount(amount) {
        if (!amount && amount !== 0) return "—";
        return new Intl.NumberFormat("fr-FR", {
            style: "currency",
            currency: "EUR",
            minimumFractionDigits: 2,
        }).format(amount);
    }

    stateLabel(state) {
        return state === "paid" ? _t("Payé") : state === "invoiced" ? _t("Facturé") : _t("Brouillon");
    }

    stateBadgeClass(state) {
        return state === "paid"
            ? "bg-success"
            : state === "invoiced"
            ? "bg-primary"
            : "bg-secondary";
    }

    // ── Data loading ───────────────────────────────────────────────────────────

    async loadSteps(cycleId = this.cycleId) {
        if (!cycleId) {
            this.state.steps = [];
            this.state.cycleData = null;
            return;
        }
        this.state.loading = true;
        try {
            const [cycleData] = await this.orm.read(
                "construction.billing.cycle",
                [cycleId],
                ["total_amount_confirmed", "currency_id"]
            );
            this.state.cycleData = cycleData;

            this.state.steps = await this.orm.searchRead(
                "construction.billing.step",
                [["cycle_id", "=", cycleId]],
                ["id", "name", "sequence", "percentage", "amount", "state", "invoice_id"],
                { order: "sequence asc, id asc" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    // ── Inline editing ─────────────────────────────────────────────────────────

    startEditing(step) {
        if (step.state !== "draft") return;
        this.state.editingId = step.id;
        this.state.editName = step.name;
        this.state.editPercent = step.percentage;
    }

    cancelEditing() {
        this.state.editingId = null;
    }

    async saveEditing() {
        const id = this.state.editingId;
        if (!id) return;
        await this.orm.write("construction.billing.step", [id], {
            name: this.state.editName,
            percentage: parseFloat(this.state.editPercent) || 0,
        });
        this.state.editingId = null;
        await this.loadSteps();
    }

    async onKeydownEdit(ev) {
        if (ev.key === "Enter") await this.saveEditing();
        if (ev.key === "Escape") this.cancelEditing();
    }

    // ── Step actions ───────────────────────────────────────────────────────────

    async onAddStep() {
        if (!this.cycleId) return;
        const nextSeq = this.state.steps.length > 0
            ? Math.max(...this.state.steps.map((s) => s.sequence)) + 10
            : 10;
        await this.orm.create("construction.billing.step", [
            {
                cycle_id: this.cycleId,
                name: _t("Nouvelle étape"),
                percentage: 0,
                sequence: nextSeq,
            },
        ]);
        await this.loadSteps();
    }

    async onDeleteStep(step) {
        if (step.state !== "draft") {
            this.notification.add(
                _t("Seules les étapes brouillon peuvent être supprimées."),
                { type: "warning" }
            );
            return;
        }
        await this.orm.unlink("construction.billing.step", [step.id]);
        await this.loadSteps();
    }

    async onCreateInvoice(step) {
        try {
            const result = await this.orm.call(
                "construction.billing.step",
                "action_create_invoice",
                [step.id]
            );
            await this.loadSteps();
            if (result && result.type) {
                await this.action.doAction(result);
            }
        } catch (e) {
            this.notification.add(
                _t("Erreur lors de la création de la facture : %s", e.message || ""),
                { type: "danger" }
            );
        }
    }

    // ── Template application ───────────────────────────────────────────────────

    async onApplyTemplate() {
        if (!this.cycleId) return;
        const hasDraftSteps = this.state.steps.some((s) => s.state === "draft");

        const doApply = async () => {
            await this.orm.call(
                "construction.billing.cycle",
                "action_apply_template",
                [this.cycleId]
            );
            await this.loadSteps();
            this.notification.add(_t("Modèle 30/30/40 appliqué."), { type: "success" });
        };

        if (hasDraftSteps) {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Appliquer le modèle standard"),
                body: _t(
                    "Les étapes brouillon existantes seront supprimées et remplacées " +
                    "par le modèle standard (30 % / 30 % / 40 %). Continuer ?"
                ),
                confirm: doApply,
            });
        } else {
            await doApply();
        }
    }
}

registry.category("view_widgets").add("billing_plan", {
    component: BillingPlanWidget,
});
