/** @odoo-module */

import { registry } from "@web/core/registry";
import { GanttController } from "./gantt_controller";
import { GanttModel } from "./gantt_model";
import { GanttRenderer } from "./gantt_renderer";
import { GanttArchParser } from "./gantt_arch_parser";

export const constructionGanttView = {
    type: "construction_gantt",
    display_name: "Planning (Archireport)",
    icon: "fa-tasks",
    multiRecord: true,
    Controller: GanttController,
    Model: GanttModel,
    Renderer: GanttRenderer,
    ArchParser: GanttArchParser,

    props: (genericProps, view) => {
        return {
            ...genericProps,
            Model: view.Model,
            Renderer: view.Renderer,
            archInfo: view.archInfo,
        };
    },
};

registry.category("views").add("construction_gantt", constructionGanttView);
