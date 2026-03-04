/** @odoo-module **/

import { useState } from "@odoo/owl";

/**
 * useUndoRedo hook
 * Handles immutable snapshots of state for Undo (Ctrl+Z) and Redo (Ctrl+Y).
 * 
 * @param {Function} getState - Optional callback to get current state if needed
 * @param {Number} maxSize - Max history size
 */
export function useUndoRedo(maxSize = 50) {
    const history = useState({
        past: [],
        future: [],
    });

    /**
     * Enregistre un snapshot de l'état courant dans l'historique.
     * Doit être appelé AVANT chaque mutation du state.
     * 
     * @param {Object} currentState - Snapshot immutable de l'état actuel
     */
    function pushHistory(currentState) {
        if (!currentState) return;

        // Deep clone to ensure immutability
        const snapshot = JSON.parse(JSON.stringify(currentState));

        history.past.push(snapshot);
        if (history.past.length > maxSize) {
            history.past.shift(); // FIFO — supprimer le plus ancien
        }

        // Toute nouvelle action efface le redo
        history.future = [];
    }

    /**
     * Annule la dernière action (Ctrl+Z).
     * @param {Object} currentState - L'état actuel à sauvegarder dans le redo avant de rollback
     * @returns {Object|null} - Le snapshot précédent, ou null si vide
     */
    function undo(currentState) {
        if (history.past.length === 0) return null;

        if (currentState) {
            const currentSnapshot = JSON.parse(JSON.stringify(currentState));
            history.future.push(currentSnapshot);
        }

        return history.past.pop();
    }

    /**
     * Rétablit la dernière action annulée (Ctrl+Y).
     * @param {Object} currentState - L'état actuel à sauvegarder dans le past avant de redo
     * @returns {Object|null} - Le snapshot suivant, ou null si vide
     */
    function redo(currentState) {
        if (history.future.length === 0) return null;

        if (currentState) {
            const currentSnapshot = JSON.parse(JSON.stringify(currentState));
            history.past.push(currentSnapshot);
        }

        return history.future.pop();
    }

    return {
        history,
        pushHistory,
        undo,
        redo,
        canUndo: () => history.past.length > 0,
        canRedo: () => history.future.length > 0
    };
}
