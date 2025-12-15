/** @odoo-module */

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class GanttRenderer extends Component {
    static template = "construction_planning.GanttRenderer";
    static props = ["model"];

    setup() {
        this.actionService = useService("action");
        this.containerRef = useRef("ganttContainer");

        // State for interactivity
        this.state = useState({
            scale: 'month', // week, month, year
            scrollX: 0,
            hoveredTask: null,
        });
    }

    // ==============================================================================================
    //                                      INTERACTIVITY
    // ==============================================================================================

    onTaskClick(taskId) {
        // Open Form View
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'construction.planning.task',
            res_id: taskId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    onScaleChange(newScale) {
        this.state.scale = newScale;
        // Trigger model reload/adjustment in real implementation
    }

    getTaskStyle(task) {
        // Sophisticated positioning logic (Mock)
        // In real impl: Calculate left/width based on dates vs timeline start/end
        const left = Math.random() * 800;
        const width = 50 + Math.random() * 200;

        let backgroundColor = '#3498db'; // Default blue
        if (task.has_conflict) {
            backgroundColor = '#e74c3c'; // Red for conflict
        } else if (task.state === 'done') {
            backgroundColor = '#2ecc71'; // Green for done
        }

        return `
            left: ${left}px; 
            width: ${width}px;
            top: ${task._rowIndex * 40 + 10}px;
            background-color: ${backgroundColor};
        `;
    }
}
