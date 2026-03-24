/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * LotProgressWidget
 * =================
 * Field widget for construction.lot.completion_percentage (Float, 0-200).
 *
 * Edit mode:
 *   - BLG bordeaux progress bar
 *   - 5 quick-set buttons: 0 / 25 / 50 / 75 / 100 (min 44px touch target)
 *   - Numeric input for exact value
 *   - Confirmation dialog when setting to 100%
 *   - urgentSave after each change
 *
 * Readonly mode (or is_finished):
 *   - Progress bar only, no controls
 *
 * Register: registry.category('fields').add('lot_progress', ...)
 */
export class LotProgressWidget extends Component {
    static template = "construction_core.LotProgressWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.state = useState({
            inputValue: String(this.props.value || 0),
        });

        this.QUICK_SET = [0, 25, 50, 75, 100];
    }

    // ── Computed ─────────────────────────────────────────────────────────────

    get currentValue() {
        return typeof this.props.value === "number" ? this.props.value : 0;
    }

    get isFinished() {
        return this.props.record?.data?.is_finished || false;
    }

    get isReadonly() {
        return this.props.readonly || this.isFinished;
    }

    get barWidth() {
        return Math.min(Math.max(this.currentValue, 0), 100);
    }

    get barColor() {
        if (this.currentValue > 100) return "#C62828"; // over-billing → red
        return "#8B3A3A";                               // BLG bordeaux
    }

    get displayLabel() {
        const v = this.currentValue;
        if (v > 100) return `${v.toFixed(0)}% ⚠️`;
        return `${v.toFixed(0)}%`;
    }

    // ── Internal save ─────────────────────────────────────────────────────────

    async _applyValue(newValue) {
        const parsed = Math.max(parseFloat(newValue) || 0, 0);
        await this.props.update(parsed);
        if (this.props.record?.urgentSave) {
            await this.props.record.urgentSave();
        }
    }

    // ── Quick-set buttons ─────────────────────────────────────────────────────

    onQuickSet = async (percent) => {
        if (this.isReadonly) return;

        if (percent === 100 && this.currentValue < 100) {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Marquer le lot comme terminé"),
                body: _t(
                    "Marquer ce lot comme terminé à 100 % ? Cette action est réversible."
                ),
                confirm: async () => {
                    this.state.inputValue = "100";
                    await this._applyValue(100);
                },
            });
        } else {
            this.state.inputValue = String(percent);
            await this._applyValue(percent);
        }
    };

    // ── Numeric input ─────────────────────────────────────────────────────────

    onInputChange = (ev) => {
        this.state.inputValue = ev.target.value;
    };

    onInputBlur = async (ev) => {
        const val = parseFloat(ev.target.value);
        if (!isNaN(val) && val !== this.currentValue) {
            if (val === 100 && this.currentValue < 100) {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Marquer le lot comme terminé"),
                    body: _t(
                        "Marquer ce lot comme terminé à 100 % ? Cette action est réversible."
                    ),
                    confirm: async () => {
                        await this._applyValue(100);
                    },
                    cancel: () => {
                        this.state.inputValue = String(this.currentValue);
                    },
                });
            } else {
                await this._applyValue(val);
            }
        } else {
            // Reset input display to actual value
            this.state.inputValue = String(this.currentValue);
        }
    };

    onInputKeydown = (ev) => {
        if (ev.key === "Enter") {
            ev.target.blur();
        } else if (ev.key === "Escape") {
            this.state.inputValue = String(this.currentValue);
            ev.target.blur();
        }
    };
}

registry.category("fields").add("lot_progress", {
    component: LotProgressWidget,
    supportedTypes: ["float", "integer"],
    displayName: _t("Lot Progress"),
});
