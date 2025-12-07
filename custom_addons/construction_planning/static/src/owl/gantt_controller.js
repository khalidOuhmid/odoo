/** @odoo-module */

import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class GanttController extends Component {
    static template = "construction_planning.GanttController";
    static components = { Layout };

    setup() {
        this.actionService = useService("action");
        this.model = useState(this.env.model);
    }
}
