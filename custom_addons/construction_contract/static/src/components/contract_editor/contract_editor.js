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
        });

        // Context from the action
        this.resId = this.props.action.context.active_id;
        this.resModel = this.props.action.context.active_model || 'construction.contract';

        onMounted(async () => {
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
            // Disable default panels to build custom ones if needed, 
            // but for now keeping defaults and adding ours.
            plugins: ['gjs-preset-webpage', this.customPlugin.bind(this)],
            pluginsOpts: {
                'gjs-preset-webpage': {
                    modalImportTitle: 'Import Template',
                    modalImportLabel: '<div style="margin-bottom: 10px; font-size: 13px;">Paste here your HTML/CSS template</div>',
                    modalImportContent: '',
                }
            },
            // BLG Palette Configuration
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
            // Prevent some dangerous edits if needed
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

        // Add Close Button
        editor.Panels.addButton('options', {
            id: 'close-editor',
            className: 'fa fa-times',
            command: () => this.actionService.doAction({ type: 'ir.actions.act_window_close' }),
            attributes: { title: 'Fermer' }
        });
    }

    customPlugin(editor) {
        const blockManager = editor.BlockManager;

        // 1. Injectable Fields (Matching _get_contract_data_context keys)
        // Only {{variable}} allowed via simplified blocks
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

        // 2. Penalties
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

        // 3. Signature Blocks
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
                // Ensure CSS is injected if it was separated? 
                // In our model we store full HTML including <style>, so setComponents should handle it if passed as string.
                // However, GrapesJS setComponents expects Body content usually. 
                // If the stored content is a full HTML page, we might need to parse.
                // But for now, let's assume the stored content is what we want.
            }
        } catch (e) {
            this.notification.add("Erreur chargement contenu", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async saveContent() {
        this.state.saving = true;
        // Get HTML and CSS
        // Note: We want to store the Full Page Logic if possible, or just the body + css style.
        // Since we generate a full HTML doc in backend, we should respect that structure.
        // GrapesJS `getHtml()` returns BODY innerHTML. `getCss()` returns CSS.
        // We will construct a wrapper similar to the template if we want to preserve <head>.
        // BUT, our `action_generate_contract_html` generates a WHOLE HTML doc.
        // If we save only body+css, we might lose the <head> scripts/meta if strictly relying on GrapesJS export.

        // Strategy: We store the HTML as GrapesJS gives it (Body + Style block). 
        // When generating PDF (WeasyPrint), `contract_template_html` will be the source. 
        // WeasyPrint handles a string with <style> blocks inside body fine.

        const html = this.editor.getHtml();
        const css = this.editor.getCss();

        // We wrap it to ensure styles are applied
        const fullContent = `<style>${css}</style>\n<div id="contract_root" class="contract-container">${html}</div>`;

        try {
            await this.orm.write(this.resModel, [this.resId], {
                contract_template_html: fullContent,
                // Optional: Update status or hash?
            });

            this.notification.add("Contrat sauvegardé avec succès", { type: "success" });
        } catch (e) {
            console.error(e);
            this.notification.add("Erreur lors de la sauvegarde", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

ContractEditor.template = "construction_contract.ContractEditor";
registry.category("actions").add("construction_contract.grapejs_editor", ContractEditor);
