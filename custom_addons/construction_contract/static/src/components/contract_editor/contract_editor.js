/** @odoo-module **/

import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";

export class ContractEditor extends Component {
    setup() {
        this.editorRef = useRef("editor");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            saving: false,
        });

        onMounted(async () => {
            // Load GrapeJS libraries dynamically if not already loaded
            await loadBundle("construction_contract.assets_template_editor");
            this.initializeEditor();
        });
    }

    initializeEditor() {
        const editor = grapesjs.init({
            container: this.editorRef.el,
            height: '100vh',
            width: '100%',
            fromElement: false,
            storageManager: false,
            plugins: ['gjs-preset-webpage', this.customPlugin.bind(this)],
            pluginsOpts: {
                'gjs-preset-webpage': {}
            }
        });

        this.editor = editor;

        // Load Initial Content
        if (this.props.action.context.active_id) {
            this.loadContent();
        }

        // Add Save Command
        editor.Commands.add('save-db', {
            run: (editor, sender) => {
                sender && sender.set('active', 0);
                this.saveContent();
            }
        });

        // Add Save Button to Panel
        editor.Panels.addButton('options', {
            id: 'save-db',
            className: 'fa fa-floppy-o',
            command: 'save-db',
            attributes: { title: 'Save Contract' }
        });
    }

    customPlugin(editor) {
        const blockManager = editor.BlockManager;

        // 1. Injectable Fields
        const fields = [
            { id: 'partner_name', label: 'Partner Name', content: '{{ object.partner_id.name }}' },
            { id: 'partner_address', label: 'Partner Address', content: '{{ object.partner_id.contact_address }}' },
            { id: 'company_name', label: 'Company Name', content: '{{ company.name }}' },
            { id: 'total_amount', label: 'Total Amount', content: '{{ object.amount_total }}' },
        ];

        fields.forEach(field => {
            blockManager.add(field.id, {
                label: field.label,
                content: `<span class="injectable-field" data-field="${field.id}" style="background-color: #fce4ec; padding: 2px;">${field.content}</span>`,
                category: 'Dynamic Fields',
                attributes: { class: 'fa fa-tag' }
            });
        });

        // 2. Signature Blocks
        blockManager.add('signature_company', {
            label: 'Company Signature',
            content: '<div class="signature-box" style="text-align: center; margin: 10px;">{{ company_signature }}</div>',
            category: 'Signatures',
            attributes: { class: 'fa fa-pencil' }
        });

        blockManager.add('signature_partner', {
            label: 'Partner Signature',
            content: '<div class="signature-box" style="text-align: center; margin: 10px;">{% if subcontractor_signature %}<img src="{{ subcontractor_signature.image_data }}" style="max-height: 100px;" alt="Signature"/>{% else %}[Signature Sous-Traitant Manquante]{% endif %}</div>',
            category: 'Signatures',
            attributes: { class: 'fa fa-pencil-square-o' }
        });

        // 3. Dynamic Table (PO Lines)
        blockManager.add('po_lines_table', {
            label: 'Order Lines Table',
            content: `
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #eee;">
                            <th style="border: 1px solid #ddd; padding: 8px;">Description</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Qty</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Unit Price</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for line in object.order_line %}
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px;">{{ line.name }}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{{ line.product_qty }}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{{ line.price_unit }}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{{ line.price_subtotal }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            `,
            category: 'Dynamic Tables',
            attributes: { class: 'fa fa-table' }
        });
    }

    async loadContent() {
        // Fetch from PO
        const model = this.props.action.context.active_model;
        const resId = this.props.action.context.active_id;
        const fieldName = this.props.action.context.field_name || 'contract_template_html';

        if (model && resId) {
            const result = await this.orm.read(model, [resId], [fieldName]);
            if (result && result[0] && result[0][fieldName]) {
                this.editor.setComponents(result[0][fieldName]);
            }
            this.state.loading = false;
        }
    }

    async saveContent() {
        this.state.saving = true;
        const html = this.editor.getHtml() + `<style>${this.editor.getCss()}</style>`;

        try {
            await this.orm.call('purchase.order', 'write', [
                [this.props.action.context.active_id],
                { contract_template_html: html }
            ]);

            this.notification.add("Contract Saved Successfully", { type: "success" });
        } catch (e) {
            this.notification.add("Error saving contract", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

ContractEditor.template = "construction_contract.ContractEditor";
registry.category("actions").add("construction_contract.grapejs_editor", ContractEditor);
