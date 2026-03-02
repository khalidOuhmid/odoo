/** @odoo-module **/
/* global Sortable */

/**
 * QuoteBuilder — SortableJS Drag & Drop Patch
 * ============================================
 * Patches the existing QuoteBuilder prototype to add drag & drop
 * reordering of cart lines within lot groups.
 *
 * ARCHITECTURE:
 *   - Does NOT modify quote_builder.js
 *   - Patches prototype with initSortable() / destroySortable()
 *   - Uses this.el.querySelectorAll('[data-lot-id]') to find containers
 *   - One Sortable instance per lot group
 *   - useEffect hook triggers init when state.loading becomes false
 *   - Cleans up on willUnmount
 */

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
                // Small delay to ensure DOM is fully rendered after OWL patch
                const timer = setTimeout(() => {
                    this.destroySortable();
                    this.initSortable();
                }, 50);
                return () => clearTimeout(timer);
            }
        },
        () => [this.state.loading, this.state.cart.length]
    );

    // Cleanup on unmount
    onWillUnmount(() => {
        this.destroySortable();
    });
};

/**
 * Initialize a Sortable instance for each lot group container.
 * Containers are identified by the `data-lot-id` HTML attribute.
 */
QuoteBuilder.prototype.initSortable = function () {
    if (!this.el) return;

    const containers = this.el.querySelectorAll('[data-lot-id]');
    if (!containers.length) return;

    containers.forEach((container) => {
        const lotId = container.getAttribute('data-lot-id');

        const instance = new Sortable(container, {
            animation: 180,
            handle: '.qb__row-handle',
            ghostClass: 'sortable-ghost',
            dragClass: 'sortable-drag',
            chosenClass: 'sortable-chosen',
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
            forceFallback: false,

            onEnd: (evt) => {
                const { oldIndex, newIndex } = evt;
                if (oldIndex === newIndex) return;

                // 1. Get all lines for this lot group
                const lotIdParsed = lotId === 'unassigned' ? null : parseInt(lotId);
                const groupLines = [];

                this.state.cart.forEach((line, idx) => {
                    const lineLotId = line.lot_id || null;
                    // Match: both null (unassigned) OR same lot_id
                    if (
                        (lotIdParsed === null && lineLotId === null) ||
                        (lotIdParsed !== null && lineLotId === lotIdParsed)
                    ) {
                        groupLines.push({ ...line, _index: idx });
                    }
                });

                if (oldIndex >= groupLines.length || newIndex >= groupLines.length) {
                    console.warn('[QuoteBuilder DnD] Index out of bounds', { oldIndex, newIndex, groupSize: groupLines.length });
                    return;
                }

                // 2. Get the global indexes
                const globalOldIndex = groupLines[oldIndex]._index;
                const globalNewIndex = groupLines[newIndex]._index;

                // 3. Splice: remove from old position, insert at new position
                const [movedItem] = this.state.cart.splice(globalOldIndex, 1);

                // After removing, if globalNewIndex > globalOldIndex, the target index shifted by -1
                const adjustedNewIndex = globalNewIndex > globalOldIndex
                    ? globalNewIndex - 1
                    : globalNewIndex;

                this.state.cart.splice(adjustedNewIndex, 0, movedItem);

                console.log('[QuoteBuilder DnD] Moved line', {
                    lot: lotId,
                    from: globalOldIndex,
                    to: adjustedNewIndex,
                    item: movedItem.name,
                });
            },
        });

        this._sortableInstances.push(instance);
    });

    console.log('[QuoteBuilder DnD] Initialized', this._sortableInstances.length, 'sortable instances');
};

/**
 * Destroy all Sortable instances and clear the array.
 */
QuoteBuilder.prototype.destroySortable = function () {
    if (this._sortableInstances) {
        this._sortableInstances.forEach((instance) => {
            try {
                instance.destroy();
            } catch (e) {
                // Silently ignore if already destroyed
            }
        });
        this._sortableInstances = [];
    }
};
