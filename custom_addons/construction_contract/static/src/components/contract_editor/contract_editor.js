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
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            saving: false,
            // Contract metadata for sidebar
            contractName: '',
            subcontractor: '',
            chantier: '',
            chantierId: null,
            amount: '',
            status: 'draft',
            statusLabel: 'Brouillon',
        });

        // Context from the action
        this.resId = this.props.action.context.active_id;
        this.resModel = this.props.action.context.active_model || 'construction.contract';

        onMounted(async () => {
            await this.loadMetadata();
            await loadBundle("construction_contract.assets_template_editor");
            this.initializeEditor();
        });
    }

    async loadMetadata() {
        /**
         * Load contract metadata for sidebar display.
         */
        if (!this.resId) return;

        try {
            const result = await this.orm.read(this.resModel, [this.resId], [
                'name', 'subcontractor_id', 'chantier_id', 'total_amount_ht', 'state', 'currency_id'
            ]);

            if (result && result[0]) {
                const contract = result[0];
                this.state.contractName = contract.name || 'Nouveau Contrat';
                this.state.subcontractor = contract.subcontractor_id ? contract.subcontractor_id[1] : '';
                this.state.chantier = contract.chantier_id ? contract.chantier_id[1] : '';
                this.state.chantierId = contract.chantier_id ? contract.chantier_id[0] : null;
                this.state.amount = this.formatCurrency(contract.total_amount_ht || 0);
                this.state.status = contract.state || 'draft';
                this.state.statusLabel = this.getStatusLabel(contract.state);
            }
        } catch (e) {
            console.error("Error loading contract metadata:", e);
        }
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR'
        }).format(amount);
    }

    getStatusLabel(state) {
        const labels = {
            'draft': 'Brouillon',
            'generated': 'Généré',
            'sent': 'Envoyé',
            'signed': 'Signé',
            'validated': 'Validé',
            'cancelled': 'Annulé',
        };
        return labels[state] || state;
    }

    initializeEditor() {
        const editor = grapesjs.init({
            container: this.editorRef.el,
            height: '100%',
            width: '100%',
            fromElement: false,
            storageManager: false,
            plugins: ['gjs-preset-webpage', this.customPlugin.bind(this)],
            pluginsOpts: {
                'gjs-preset-webpage': {
                    modalImportTitle: 'Import Template',
                    modalImportLabel: '<div style="margin-bottom: 10px; font-size: 13px;">Paste here your HTML/CSS template</div>',
                    modalImportContent: '',
                }
            },
            colorPicker: {
                appendTo: 'parent',
                palette: [
                    { name: 'BLG Bordeaux', color: '#92564C' },
                    { name: 'BLG Gris Foncé', color: '#978A86' },
                    { name: 'BLG Gris Moyen', color: '#AEADAB' },
                    { name: 'BLG Beige', color: '#D4C5BC' },
                    { name: 'BLG Blanc', color: '#FFFFFF' },
                ],
            },
            allowScripts: 0,
        });

        this.editor = editor;

        // Load Initial Content
        if (this.resId) {
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
            attributes: { title: 'Sauvegarder le Contrat' }
        });
    }

    customPlugin(editor) {
        const blockManager = editor.BlockManager;

        // Injectable Fields
        const fields = [
            { id: 'partner_name', label: 'Nom Sous-Traitant', content: '{{partner_name}}' },
            { id: 'partner_address', label: 'Adresse Sous-Traitant', content: '{{partner_street}} {{partner_zip}} {{partner_city}}' },
            { id: 'project_ref', label: 'Réf. Projet', content: '{{project_reference}}' },
            { id: 'amount_total', label: 'Montant Total', content: '{{amount_total}}' },
            { id: 'signature_date', label: 'Date Signature', content: '{{signature_date}}' },
            { id: 'master_name', label: 'Maître d\'Ouvrage', content: '{{master_name}}' },
        ];

        fields.forEach(field => {
            blockManager.add(field.id, {
                label: field.label,
                content: `<span class="injectable-field" data-field="${field.id}" style="background-color: #fce4ec; padding: 2px;">${field.content}</span>`,
                category: 'Champs Dynamiques',
                attributes: { class: 'fa fa-tag' }
            });
        });

        // Penalties
        const penalties = [
            { id: 'penalty_delay', label: 'Pénalité Retard Doc', content: '{{penalty_docs_delay}}' },
            { id: 'penalty_safety', label: 'Pénalité Sécurité', content: '{{penalty_safety}}' },
            { id: 'penalty_cleaning', label: 'Pénalité Nettoyage', content: '{{penalty_cleaning}}' },
        ];

        penalties.forEach(p => {
            blockManager.add(p.id, {
                label: p.label,
                content: `<span class="injectable-field" data-field="${p.id}" style="background-color: #e3f2fd; padding: 2px;">${p.content}</span>`,
                category: 'Pénalités',
                attributes: { class: 'fa fa-gavel' }
            });
        });

        // Signatures
        blockManager.add('signature_blg', {
            label: 'Signature BLG',
            content: '<div class="signature-box" style="text-align: center; margin: 10px;"><img src="{{signature_blg_image}}" style="max-height: 80px;" alt="Signature BLG"/></div>',
            category: 'Signatures',
            attributes: { class: 'fa fa-pencil' }
        });

        blockManager.add('signature_partner', {
            label: 'Signature Sous-Traitant',
            content: '<div class="signature-box" style="text-align: center; margin: 10px;"><img src="{{signature_partner_image}}" style="max-height: 80px;" alt="Signature Sous-Traitant"/></div>',
            category: 'Signatures',
            attributes: { class: 'fa fa-pencil-square-o' }
        });
    }

    async loadContent() {
        const fieldName = 'contract_template_html';
        try {
            const result = await this.orm.read(this.resModel, [this.resId], [fieldName]);
            if (result && result[0] && result[0][fieldName]) {
                this.editor.setComponents(result[0][fieldName]);
            }
        } catch (e) {
            this.notification.add("Erreur chargement contenu", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async saveContent() {
        this.state.saving = true;
        const html = this.editor.getHtml();
        const css = this.editor.getCss();

        const fullContent = `<style>${css}</style>\n<div id="contract_root" class="contract-container">${html}</div>`;

        try {
            await this.orm.write(this.resModel, [this.resId], {
                contract_template_html: fullContent,
            });
            this.notification.add("Contrat sauvegardé avec succès", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification.add("Erreur lors de la sauvegarde", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    async onGenerateAndSend() {
        /**
         * Save current content, generate PDF, then open send wizard.
         */
        this.state.saving = true;

        try {
            // 1. Save content first
            await this.saveContent();

            // 2. Call generate PDF and send method on backend
            const result = await this.orm.call(this.resModel, 'action_generate_pdf_and_open_send_wizard', [[this.resId]]);

            // 3. Execute returned action (should open wizard)
            if (result) {
                await this.actionService.doAction(result);
            }
        } catch (e) {
            console.error("Generate and send error:", e);
            this.notification.add("Erreur lors de la génération", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onClose() {
        /**
         * Return to the chantier form view.
         */
        if (this.state.chantierId) {
            this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'construction.chantier',
                res_id: this.state.chantierId,
                views: [[false, 'form']],
                target: 'current',
            });
        } else {
            this.actionService.doAction({ type: 'ir.actions.act_window_close' });
        }
    }
}

ContractEditor.template = "construction_contract.ContractEditor";
registry.category("actions").add("construction_contract.grapejs_editor", ContractEditor);
