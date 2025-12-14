/** @odoo-module **/
/**
 * Stub widgets for missing module dependencies
 * ============================================
 * These stubs prevent OWL errors when views reference widgets
 * from modules that are not fully installed.
 */

import { Component } from "@odoo/owl";
import { registry } from '@web/core/registry';
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

// Stub for sale_pdf_quote_builder's widget
class CustomContentKanbanLikeWidgetStub extends Component {
    static template = "construction_sale.StubWidget";
    static props = {
        ...standardWidgetProps,
    };
}

const customContentKanbanLikeWidget = {
    component: CustomContentKanbanLikeWidgetStub,
};

// Only register if not already registered
const viewWidgets = registry.category("view_widgets");
if (!viewWidgets.contains("customContentKanbanLikeWidget")) {
    viewWidgets.add("customContentKanbanLikeWidget", customContentKanbanLikeWidget);
}
