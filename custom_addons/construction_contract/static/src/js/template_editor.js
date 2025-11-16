/** Template Editor Helpers
 *  Minimal bootstrap for GrapesJS editor context
 */

odoo.define('construction_contract.template_editor', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.ContractTemplateEditor = publicWidget.Widget.extend({
        selector: '.contract-template-editor',

        start() {
            // Placeholder for future behaviours (saving feedback, custom commands, etc.)
            return this._super.apply(this, arguments);
        },
    });
});


