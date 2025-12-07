/** @odoo-module */

export class GanttModel {
    constructor() {
        this.data = [];
        this.rows = [];
    }

    async load(params) {
        // Mock Data Loading simulating groupings
        // In real implementation: use model.search_read with grouping

        // Mock Rows (Chantier/Lot)
        this.rows = [
            { id: 1, name: "Chantier A - Gros Oeuvre", tasks: [] },
            { id: 2, name: "Chantier A - Plomberie", tasks: [] },
            { id: 3, name: "Chantier B - Élec", tasks: [] }
        ];

        // Mock Tasks with Conflicts
        const mockTasks = [
            { id: 1, name: "Fondations", date_start: "2024-01-01", date_end: "2024-01-15", state: 'done', has_conflict: false, _rowIndex: 0 },
            { id: 2, name: "Murs RDC", date_start: "2024-01-16", date_end: "2024-02-01", state: 'planned', has_conflict: true, _rowIndex: 0 }, // Conflict!
            { id: 3, name: "Tuyauterie", date_start: "2024-01-20", date_end: "2024-01-25", state: 'planned', has_conflict: false, _rowIndex: 1 },
            { id: 4, name: "Câblage", date_start: "2024-02-01", date_end: "2024-02-10", state: 'planned', has_conflict: true, _rowIndex: 2 }
        ];

        // Distribute tasks to rows
        this.rows[0].tasks.push(mockTasks[0], mockTasks[1]);
        this.rows[1].tasks.push(mockTasks[2]);
        this.rows[2].tasks.push(mockTasks[3]);

        this.data = mockTasks;
    }
}
