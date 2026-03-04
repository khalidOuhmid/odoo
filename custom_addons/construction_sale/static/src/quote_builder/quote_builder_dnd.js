/** @odoo-module **/
/* global Sortable */

import { QuoteBuilder } from "./quote_builder";
import { useEffect, onWillUnmount } from "@odoo/owl";

// ─── Store original setup ───
const _originalSetup = QuoteBuilder.prototype.setup;

QuoteBuilder.prototype.setup = function () {
    // Call original setup
    _originalSetup.call(this);

    // Storage for Sortable instances
    this._sortableInstances = [];

    // Init sortable when loading finishes and cart structure changes
    useEffect(
        () => {
            if (!this.state.loading) {
                // Using requestAnimationFrame to ensure the DOM is fully painted by Owl
                window.requestAnimationFrame(() => {
                    this.initSortable();
                });
            }

            // Clean up instances BEFORE the next effect runs or on unmount
            return () => this.destroySortable();
        },
        () => [
            this.state.loading,
            this.state.cart.length,
            // Re-run if we detect a change in the grouped structure ids to attach to new DOM nodes
            this.getGroupedCart().map(g => g.id).join(',')
        ]
    );

    // Final cleanup on unmount
    onWillUnmount(() => {
        this.destroySortable();
    });
};

/**
 * Initialize a Sortable instance for each lot group container.
 */
QuoteBuilder.prototype.initSortable = function () {
    // Make sure we clean up any orphaned instances first
    this.destroySortable();

    const containers = document.querySelectorAll('.qb__sortable-container');
    if (!containers || !containers.length) return;

    containers.forEach((container) => {
        const lotId = container.getAttribute('data-lot-id');

        const instance = new Sortable(container, {
            group: 'quote-lines', // Enable drag between lists
            animation: 180,
            handle: '.qb__row-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            chosenClass: 'sortable-chosen',
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
            forceFallback: false,
            // Prevent Owl from trying to patch while sorting
            filter: 'input, textarea',
            preventOnFilter: false,

            onEnd: (evt) => {
                const { oldIndex, newIndex, from, to } = evt;

                const fromLotId = from.getAttribute('data-lot-id');
                const toLotId = to.getAttribute('data-lot-id');

                if (fromLotId === toLotId && oldIndex === newIndex) return;

                // Push history for undo/redo before changing state
                if (typeof this._pushUndo === 'function') {
                    this._pushUndo();
                }

                // Parse lot IDs
                const fromLotParsed = fromLotId === 'unassigned' ? null : parseInt(fromLotId);
                const toLotParsed = toLotId === 'unassigned' ? null : parseInt(toLotId);

                // Reconstruct groups as they exist visually to figure out what was where
                const fromGroupLines = [];
                const toGroupLines = [];

                this.state.cart.forEach((line, idx) => {
                    const lineLotId = line.lot_id || null;
                    if (lineLotId === fromLotParsed) {
                        fromGroupLines.push({ ...line, _index: idx });
                    }
                    if (lineLotId === toLotParsed) {
                        toGroupLines.push({ ...line, _index: idx });
                    }
                });

                if (oldIndex >= fromGroupLines.length) return;

                // 2. Extirpate the moved item from the actual cart
                const globalOldIndex = fromGroupLines[oldIndex]._index;
                const [movedItem] = this.state.cart.splice(globalOldIndex, 1);

                // Update section assignment if moved cross-sections
                if (fromLotId !== toLotId) {
                    movedItem.lot_id = toLotParsed;
                }

                // 3. Figure out precisely where to splice it back in
                let adjustedNewIndex = this.state.cart.length;

                if (fromLotId === toLotId) {
                    // Simple reorder within same list
                    const globalNewIndex = fromGroupLines[newIndex]._index;
                    adjustedNewIndex = globalNewIndex > globalOldIndex
                        ? globalNewIndex - 1
                        : globalNewIndex;
                } else {
                    // Cross-list drop logic
                    if (toGroupLines.length === 0) {
                        // Easy, just put it anywhere, getGroupedCart handles visually grouping it
                        adjustedNewIndex = this.state.cart.length;
                    } else if (newIndex < toGroupLines.length) {
                        // Dropped amidst existing lines in the new section
                        const targetGlobalIndex = toGroupLines[newIndex]._index;
                        adjustedNewIndex = targetGlobalIndex > globalOldIndex
                            ? targetGlobalIndex - 1
                            : targetGlobalIndex;
                    } else {
                        // Dropped at the very bottom of the new section
                        const lastGlobalIndex = toGroupLines[toGroupLines.length - 1]._index;
                        adjustedNewIndex = lastGlobalIndex > globalOldIndex
                            ? lastGlobalIndex
                            : lastGlobalIndex + 1;
                    }
                }

                // Plop it into its new index
                this.state.cart.splice(adjustedNewIndex, 0, movedItem);

                // The state mutation triggers Owl to re-render, and since our dependencies changed, the useEffect rebuilds Sortable.

                // Save draft dynamically tracking
                if (typeof this.saveDraft === 'function') {
                    this.saveDraft();
                }
            },
        });

        this._sortableInstances.push(instance);
    });
};

/**
 * Destroy all Sortable instances and clear the array.
 */
QuoteBuilder.prototype.destroySortable = function () {
    if (this._sortableInstances && this._sortableInstances.length) {
        this._sortableInstances.forEach((instance) => {
            try {
                instance.destroy();
            } catch (e) { }
        });
        this._sortableInstances = [];
    }
};
