/** @odoo-module **/

/**
 * ContractEditor — GrapeJS-powered contract builder with editable sidebar.
 *
 * TASK-006: The sidebar exposes key contract fields (parties, dates, amounts,
 * penalties) for quick editing.  Changes are batched and saved to the Odoo
 * record in one RPC call.  The Jinja2 template variables are automatically
 * kept in sync because they are derived from these same fields at PDF
 * generation time.
 */

import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";

/** Sidebar fields read from the contract record. */
const SIDEBAR_FIELDS = [
    'name', 'state', 'currency_id',
    'subcontractor_id', 'chantier_id',
    'total_amount_ht', 'total_amount_ttc', 'retention_rate',
    'master_name', 'master_address',
    'signatory_contractor', 'signatory_subcontractor',
    'start_date', 'end_date',
    'gpa_duration',
    'penalty_retard_jour', 'penalty_docs_delay', 'penalty_safety',
    'penalty_cleaning', 'penalty_justificatifs', 'penalty_prototypes',
];

export class ContractEditor extends Component {
    setup() {
        this.editorRef = useRef("editor");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            saving: false,
            savingSidebar: false,
            isDirty: false,
            // Header
            contractName: '',
            status: 'draft',
            statusLabel: 'Brouillon',
            // Parties
            subcontractor: '',
            chantier: '',
            chantierId: null,
            masterName: '',
            masterAddress: '',
            signatoryContractor: 'Direction BLG',
            signatorySubcontractor: '',
            // Dates
            startDate: '',
            endDate: '',
            // Montants
            amount: '',
            retentionRate: 5.0,
            gpaDuration: 12,
            // Pénalités
            penaltyRetardJour: 200,
            penaltyDocsDelay: 150,
            penaltySafety: 80,
            penaltyCleaning: 80,
            penaltyJustificatifs: 150,
            penaltyPrototypes: 50,
            // Lots
            lots: [],
        });

        /** Pending field changes to write in one RPC. */
        this._pendingWrites = {};

        this.resId = this.props.action.context.active_id;
        this.resModel = this.props.action.context.active_model || 'construction.contract';

        onMounted(async () => {
            await this.loadMetadata();
            await loadBundle("construction_contract.assets_template_editor");
            this.initializeEditor();
        });
    }

    // ================================================================
    // DATA LOADING
    // ================================================================

    async loadMetadata() {
        if (!this.resId) return;

        try {
            const result = await this.orm.read(
                this.resModel, [this.resId], SIDEBAR_FIELDS,
            );

            if (result && result[0]) {
                const c = result[0];
                this.state.contractName = c.name || 'Nouveau Contrat';
                this.state.subcontractor = c.subcontractor_id ? c.subcontractor_id[1] : '';
                this.state.chantier = c.chantier_id ? c.chantier_id[1] : '';
                this.state.chantierId = c.chantier_id ? c.chantier_id[0] : null;
                this.state.amount = this.formatCurrency(c.total_amount_ht || 0);
                this.state.status = c.state || 'draft';
                this.state.statusLabel = this.getStatusLabel(c.state);
                // Editable fields
                this.state.masterName = c.master_name || '';
                this.state.masterAddress = c.master_address || '';
                this.state.signatoryContractor = c.signatory_contractor || 'Direction BLG';
                this.state.signatorySubcontractor = c.signatory_subcontractor || '';
                this.state.startDate = c.start_date || '';
                this.state.endDate = c.end_date || '';
                this.state.retentionRate = c.retention_rate ?? 5.0;
                this.state.gpaDuration = c.gpa_duration ?? 12;
                this.state.penaltyRetardJour = c.penalty_retard_jour ?? 200;
                this.state.penaltyDocsDelay = c.penalty_docs_delay ?? 150;
                this.state.penaltySafety = c.penalty_safety ?? 80;
                this.state.penaltyCleaning = c.penalty_cleaning ?? 80;
                this.state.penaltyJustificatifs = c.penalty_justificatifs ?? 150;
                this.state.penaltyPrototypes = c.penalty_prototypes ?? 50;
            }

            // Load lots data
            await this.loadLots();
        } catch (e) {
            this.notification.add("Erreur chargement métadonnées", { type: "danger" });
        }
    }

    async loadLots() {
        if (!this.resId) return;
        try {
            const contract = await this.orm.read(
                this.resModel, [this.resId], ['lot_ids'],
            );
            if (contract && contract[0] && contract[0].lot_ids.length) {
                const lots = await this.orm.read(
                    'construction.lot',
                    contract[0].lot_ids,
                    ['name', 'code', 'price'],
                );
                this.state.lots = lots.map(l => ({
                    name: l.name || '',
                    code: l.code || '',
                    amount: this.formatCurrency(l.price || 0),
                }));
            }
        } catch (_) {
            // Non-blocking
        }
    }

    // ================================================================
    // SIDEBAR – Field Change & Save
    // ================================================================

    /**
     * Handle a sidebar field change.  Batches the value and marks dirty.
     *
     * @param {string} fieldName  Odoo field name (e.g. 'master_name')
     * @param {any}    value      New value
     */
    onFieldChange(fieldName, value) {
        this._pendingWrites[fieldName] = value;
        this.state.isDirty = true;

        // Update local state for immediate feedback
        const stateMap = {
            master_name: 'masterName',
            master_address: 'masterAddress',
            signatory_contractor: 'signatoryContractor',
            signatory_subcontractor: 'signatorySubcontractor',
            start_date: 'startDate',
            end_date: 'endDate',
            retention_rate: 'retentionRate',
            gpa_duration: 'gpaDuration',
            penalty_retard_jour: 'penaltyRetardJour',
            penalty_docs_delay: 'penaltyDocsDelay',
            penalty_safety: 'penaltySafety',
            penalty_cleaning: 'penaltyCleaning',
            penalty_justificatifs: 'penaltyJustificatifs',
            penalty_prototypes: 'penaltyPrototypes',
        };

        if (stateMap[fieldName]) {
            this.state[stateMap[fieldName]] = value;
        }
    }

    /**
     * Flush all pending sidebar writes to the backend in one RPC.
     */
    async onSaveSidebar() {
        if (!Object.keys(this._pendingWrites).length) return;

        this.state.savingSidebar = true;
        try {
            // Validate dates
            if (this._pendingWrites.start_date && this._pendingWrites.end_date) {
                if (this._pendingWrites.end_date < this._pendingWrites.start_date) {
                    this.notification.add(
                        "La date de fin doit être après la date de début.",
                        { type: "warning" },
                    );
                    this.state.savingSidebar = false;
                    return;
                }
            }
            // Validate retention rate
            if ('retention_rate' in this._pendingWrites) {
                const rate = this._pendingWrites.retention_rate;
                if (rate < 0 || rate > 20) {
                    this.notification.add(
                        "Le taux de retenue doit être entre 0% et 20%.",
                        { type: "warning" },
                    );
                    this.state.savingSidebar = false;
                    return;
                }
            }

            await this.orm.write(this.resModel, [this.resId], this._pendingWrites);
            this._pendingWrites = {};
            this.state.isDirty = false;
            this.notification.add("Champs sauvegardés ✓", { type: "success" });
        } catch (e) {
            const msg = e?.data?.message || e?.message || "Erreur de sauvegarde";
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.savingSidebar = false;
        }
    }

    // ================================================================
    // HELPERS
    // ================================================================

    formatCurrency(amount) {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR',
        }).format(amount);
    }

    getStatusLabel(state) {
        const labels = {
            draft: 'Brouillon',
            generated: 'Généré',
            sent: 'Envoyé',
            in_progress: 'En cours',
            signed: 'Signé',
            cancelled: 'Annulé',
            archived: 'Archivé',
        };
        return labels[state] || state;
    }

    // ================================================================
    // GRAPEJS EDITOR
    // ================================================================

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
                    modalImportLabel: '<div style="margin-bottom: 10px; font-size: 13px;">Collez votre template HTML/CSS</div>',
                    modalImportContent: '',
                },
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

        if (this.resId) {
            this.loadContent();
        }

        // Save command
        editor.Commands.add('save-db', {
            run: (_editor, sender) => {
                sender && sender.set('active', 0);
                this.saveContent();
            },
        });

        editor.Panels.addButton('options', {
            id: 'save-db',
            className: 'fa fa-floppy-o',
            command: 'save-db',
            attributes: { title: 'Sauvegarder le Contrat' },
        });
    }

    customPlugin(editor) {
        const bm = editor.BlockManager;

        // Dynamic Jinja2 fields
        const fields = [
            { id: 'partner_name', label: 'Nom Sous-Traitant', content: '{{partner_name}}' },
            { id: 'partner_address', label: 'Adresse S-T', content: '{{partner_street}} {{partner_city}}' },
            { id: 'project_ref', label: 'Réf. Projet', content: '{{project_reference}}' },
            { id: 'amount_total', label: 'Montant Total', content: '{{amount_total}}' },
            { id: 'signature_date', label: 'Date Signature', content: '{{date_signature}}' },
            { id: 'master_name', label: "Maître d'Ouvrage", content: '{{maitre_ouvrage_nom}}' },
            { id: 'bc_numero', label: 'N° Contrat', content: '{{bc_numero}}' },
            { id: 'chantier_nom', label: 'Nom Chantier', content: '{{chantier_nom}}' },
        ];

        fields.forEach(f => {
            bm.add(f.id, {
                label: f.label,
                content: `<span class="injectable-field" data-field="${f.id}" style="background-color: #fce4ec; padding: 2px;">${f.content}</span>`,
                category: 'Champs Dynamiques',
                attributes: { class: 'fa fa-tag' },
            });
        });

        // Penalties
        const penalties = [
            { id: 'penalty_delay', label: 'Pénalité Retard Doc', content: '{{penalty_docs_delay}}' },
            { id: 'penalty_safety', label: 'Pénalité Sécurité', content: '{{penalty_safety}}' },
            { id: 'penalty_cleaning', label: 'Pénalité Nettoyage', content: '{{penalty_cleaning}}' },
            { id: 'penalty_retard', label: 'Pénalité Retard/Jour', content: '{{penalite_retard_jour}}' },
        ];

        penalties.forEach(p => {
            bm.add(p.id, {
                label: p.label,
                content: `<span class="injectable-field" data-field="${p.id}" style="background-color: #e3f2fd; padding: 2px;">${p.content}</span>`,
                category: 'Pénalités',
                attributes: { class: 'fa fa-gavel' },
            });
        });

        // Signatures
        bm.add('signature_blg', {
            label: 'Signature BLG',
            content: '<div class="signature-box" style="text-align: center; margin: 10px;"><img src="{{signature_blg_image}}" style="max-height: 80px;" alt="Signature BLG"/></div>',
            category: 'Signatures',
            attributes: { class: 'fa fa-pencil' },
        });
        bm.add('signature_partner', {
            label: 'Signature Sous-Traitant',
            content: '<div class="signature-box" style="text-align: center; margin: 10px;"><img src="{{signature_partner_image}}" style="max-height: 80px;" alt="Signature ST"/></div>',
            category: 'Signatures',
            attributes: { class: 'fa fa-pencil-square-o' },
        });
    }

    // ================================================================
    // CONTENT LOAD / SAVE
    // ================================================================

    async loadContent() {
        try {
            const result = await this.orm.read(
                this.resModel, [this.resId], ['contract_template_html'],
            );
            if (result?.[0]?.contract_template_html) {
                this.editor.setComponents(result[0].contract_template_html);
            }
        } catch (_) {
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
            this.notification.add("Contrat sauvegardé ✓", { type: "success" });
        } catch (e) {
            const msg = e?.data?.message || e?.message || "Erreur de sauvegarde";
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // ================================================================
    // TOP-LEVEL ACTIONS
    // ================================================================

    async onGenerateAndSend() {
        this.state.saving = true;
        try {
            // Save sidebar fields first if dirty
            if (this.state.isDirty) {
                await this.onSaveSidebar();
            }
            // Save HTML content
            await this.saveContent();
            // Generate PDF + open send wizard
            const result = await this.orm.call(
                this.resModel,
                'action_generate_pdf_and_open_send_wizard',
                [[this.resId]],
            );
            if (result) {
                await this.actionService.doAction(result);
            }
        } catch (e) {
            const msg = e?.data?.message || e?.message || "Erreur de génération";
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    onClose() {
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
