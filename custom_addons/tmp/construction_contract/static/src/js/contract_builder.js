/**
 * Contract Live Builder
 * Handles real-time preview and contract generation
 */

(function() {
    'use strict';

    class ContractLiveBuilder {
        constructor() {
            this.config = {};
            this.manualEdit = false;
            this.manualHtml = null;
            this.init();
        }

    init() {
        console.log("[ContractBuilder] Initializing...");
        
        // Get DOM elements
        this.$container = document.getElementById("contract-live-builder");
        if (!this.$container) {
            console.error("[ContractBuilder] Container #contract-live-builder not found!");
            return;
        }

        this.$iframe = document.getElementById("builder-preview-frame");
        this.$status = document.querySelector(".builder-status");
        this.$editBadge = document.querySelector(".builder-edit-state");
        
        // Decode config
        this._decodeConfig();
        console.log("[ContractBuilder] Config:", this.config);
        
        // Bind events
        this._bindEvents();
        
        // Initial preview after a short delay to ensure DOM is ready
        setTimeout(() => this._refreshPreview(), 100);
        
        console.log("[ContractBuilder] Initialized successfully");
    }

    _decodeConfig() {
        const raw = this.$container.dataset.config || "{}";
        try {
            this.config = JSON.parse(raw);
        } catch (err) {
            console.error("[ContractBuilder] Config parse error:", err);
            this.config = {};
        }
    }

    _bindEvents() {
        // Input changes
        const inputs = this.$container.querySelectorAll(".js-builder-input");
        inputs.forEach((input) => {
            input.addEventListener("change", () => {
                console.log("[ContractBuilder] Input changed:", input.name, input.value);
                if (!this.manualEdit) {
                    this._refreshPreview();
                }
            });
        });

        // Refresh button
        const refreshBtn = this.$container.querySelector(".js-builder-refresh");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", (ev) => {
                ev.preventDefault();
                if (this.manualEdit && this.manualHtml) {
                    if (!confirm("Refreshing will discard your manual edits. Continue?")) {
                        return;
                    }
                    this._toggleEditMode(false);
                }
                this._refreshPreview();
            });
        }

        // Edit toggle buttons
        const editBtns = this.$container.querySelectorAll(".js-builder-toggle-edit");
        editBtns.forEach((btn) => {
            btn.addEventListener("click", (ev) => {
                ev.preventDefault();
                const enable = btn.dataset.mode === "enable";
                this._toggleEditMode(enable);
            });
        });

        // Generate button
        const generateBtn = this.$container.querySelector(".js-builder-generate");
        if (generateBtn) {
            generateBtn.addEventListener("click", (ev) => {
                ev.preventDefault();
                this._generateContract();
            });
        }
        
        console.log("[ContractBuilder] Events bound successfully");
    }

    _getPayload() {
        const getSelectValue = (name) => {
            const el = this.$container.querySelector(`select[name='${name}']`);
            return el ? el.value : "";
        };
        
        const getInputValue = (name) => {
            const el = this.$container.querySelector(`input[name='${name}']`);
            return el ? el.value : "";
        };
        
        const getCheckboxValue = (name) => {
            const el = this.$container.querySelector(`input[name='${name}']`);
            return el ? el.checked : false;
        };
        
        const getMultiSelectValues = (name) => {
            const el = this.$container.querySelector(`select[name='${name}']`);
            if (!el) return [];
            return Array.from(el.selectedOptions).map(opt => Number(opt.value));
        };

        const payload = {
            chantier_id: Number(this.config.chantier_id),
            subcontractor_id: Number(getSelectValue('subcontractor_id')) || 0,
            template_id: Number(getSelectValue('template_id')) || 0,
            lot_ids: getMultiSelectValues('lot_ids'),
            start_date: getInputValue('start_date'),
            end_date: getInputValue('end_date'),
            contract_date: getInputValue('contract_date'),
            retention_rate: parseFloat(getInputValue('retention_rate')) || 0,
            generate_deliverables: getCheckboxValue('generate_deliverables'),
            send_immediately: getCheckboxValue('send_immediately'),
        };
        
        console.log("[ContractBuilder] Payload:", payload);
        return payload;
    }

    async _refreshPreview() {
        console.log("[ContractBuilder] Refreshing preview...");
        const payload = this._getPayload();
        
        // Validation with detailed logging
        const missing = [];
        if (!payload.subcontractor_id) {
            console.warn("[ContractBuilder] Missing subcontractor_id");
            missing.push("subcontractor");
        }
        if (!payload.lot_ids || payload.lot_ids.length === 0) {
            console.warn("[ContractBuilder] Missing lot_ids");
            missing.push("work packages");
        }
        if (!payload.template_id) {
            console.warn("[ContractBuilder] Missing template_id");
            missing.push("template");
        }
        
        if (missing.length > 0) {
            const msg = "Please select: " + missing.join(", ");
            console.log("[ContractBuilder] Validation failed:", msg);
            this._setStatus("warning", msg);
            this._showPlaceholder();
            return;
        }
        
        console.log("[ContractBuilder] Validation passed, calling render API...");
        this._setStatus("info", "Generating preview...");
        
        try {
            const result = await this._rpc(this.config.render_url, {payload: payload});
            console.log("[ContractBuilder] Render result:", result);
            
            if (result.status === "success") {
                console.log("[ContractBuilder] Preview HTML length:", result.html?.length);
                this._injectPreview(result.html);
                this._setStatus("success", "Preview updated successfully.");
            } else {
                console.error("[ContractBuilder] Render failed:", result.message);
                this._setStatus("danger", result.message || "Unable to generate preview.");
            }
        } catch (error) {
            console.error("[ContractBuilder] AJAX error:", error);
            this._setStatus("danger", "Server error while generating preview: " + error.message);
        }
    }

    _showPlaceholder() {
        const placeholderHtml = `
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body>
                <div style="display: flex; align-items: center; justify-content: center; min-height: 720px; padding: 40px; text-align: center; font-family: Arial, sans-serif;">
                    <div>
                        <div style="font-size: 48px; margin-bottom: 20px; opacity: 0.3;">📋</div>
                        <h3 style="color: #64748b; font-weight: 500; margin-bottom: 12px;">Contract Preview</h3>
                        <p style="color: #94a3b8; font-size: 14px;">Select a subcontractor, work packages, and a template to display the preview.</p>
                    </div>
                </div>
            </body>
            </html>
        `;
        this._injectPreview(placeholderHtml);
    }

    _injectPreview(htmlContent) {
        if (this.manualEdit) {
            console.log("[ContractBuilder] Manual edit mode active, skipping inject");
            return;
        }
        if (!this.$iframe) {
            console.error("[ContractBuilder] Iframe not found");
            return;
        }
        
        console.log("[ContractBuilder] Injecting preview HTML...");
        this.$iframe.srcdoc = htmlContent;
        this.manualHtml = null;
        this._toggleEditBadge(false);
    }

    _toggleEditMode(enable) {
        if (!this.$iframe) {
            this._setStatus("warning", "Please generate a preview first.");
            return;
        }
        
        const activateEdit = () => {
            const doc = this.$iframe.contentDocument || this.$iframe.contentWindow.document;
            if (!doc || !doc.body) {
                this._setStatus("warning", "Preview is not loaded yet.");
                return;
            }
            
            this.manualEdit = enable;
            if (enable) {
                doc.designMode = "on";
                doc.body.setAttribute("contenteditable", "true");
                doc.body.style.outline = "2px dashed #3b82f6";
                doc.body.style.outlineOffset = "4px";
                this._toggleEditBadge(true);
                this._toggleEditButtons(true);
                this._setStatus("success", "Edit mode enabled. Click in the preview to modify text.");
            } else {
                doc.designMode = "off";
                doc.body.setAttribute("contenteditable", "false");
                doc.body.style.outline = "";
                doc.body.style.outlineOffset = "";
                this.manualHtml = null;
                this._toggleEditBadge(false);
                this._toggleEditButtons(false);
                this._setStatus("info", "Edit mode disabled.");
            }
        };
        
        if (this.$iframe.contentDocument && this.$iframe.contentDocument.readyState === "complete") {
            activateEdit();
        } else {
            this.$iframe.addEventListener("load", activateEdit, { once: true });
        }
    }

    _toggleEditBadge(active) {
        if (!this.$editBadge) return;
        
        if (active) {
            this.$editBadge.classList.remove("d-none");
        } else {
            this.$editBadge.classList.add("d-none");
        }
    }

    _toggleEditButtons(editActive) {
        const enableBtn = this.$container.querySelector(".js-edit-enable");
        const disableBtn = this.$container.querySelector(".js-edit-disable");
        
        if (editActive) {
            enableBtn?.classList.add("d-none");
            disableBtn?.classList.remove("d-none");
        } else {
            enableBtn?.classList.remove("d-none");
            disableBtn?.classList.add("d-none");
        }
    }

    _captureManualHtml() {
        if (!this.$iframe || !this.$iframe.contentDocument) {
            return null;
        }
        const doc = this.$iframe.contentDocument;
        return "<!DOCTYPE html>\n" + doc.documentElement.outerHTML;
    }

    async _generateContract() {
        console.log("[ContractBuilder] Generating contract...");
        const payload = this._getPayload();
        
        if (this.manualEdit) {
            this.manualHtml = this._captureManualHtml();
        }
        if (this.manualHtml) {
            payload.manual_html = this.manualHtml;
        }
        
        this._setStatus("info", "Creating contract...");
        
        try {
            const result = await this._rpc(this.config.create_url, {payload: payload});
            console.log("[ContractBuilder] Create result:", result);
            
            if (result.status === "success") {
                this._setStatus("success", "Contract created.");
                if (result.redirect_url) {
                    console.log("[ContractBuilder] Redirecting to:", result.redirect_url);
                    window.location = result.redirect_url;
                }
            } else {
                console.error("[ContractBuilder] Create failed:", result.message);
                this._setStatus("danger", result.message || "Unable to create contract.");
            }
        } catch (error) {
            console.error("[ContractBuilder] Create error:", error);
            this._setStatus("danger", "Server error while creating contract: " + error.message);
        }
    }

    _setStatus(level, message, link) {
        if (!this.$status) {
            console.warn("[ContractBuilder] Status element not found");
            return;
        }
        
        const classes = {
            info: "alert-info",
            success: "alert-success",
            warning: "alert-warning",
            danger: "alert-danger",
        };
        
        const css = classes[level] || classes.info;
        const escapedMessage = this._escapeHtml(message);
        
        let html = `<div class="alert ${css}" role="alert">${escapedMessage}</div>`;
        if (link) {
            const safeLink = this._escapeHtml(link);
            html = `<div class="alert ${css}" role="alert"><a href="${safeLink}" class="text-decoration-underline">${escapedMessage}</a></div>`;
        }
        
        this.$status.innerHTML = html;
        console.log("[ContractBuilder] Status set:", level, message);
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    _rpc(url, params) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', url, true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        // Odoo JSON-RPC returns {result: ...} on success
                        if (response.result) {
                            resolve(response.result);
                        } else if (response.error) {
                            reject(new Error(response.error.data?.message || 'Server error'));
                        } else {
                            resolve(response);
                        }
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                } else {
                    reject(new Error('HTTP ' + xhr.status));
                }
            };
            
            xhr.onerror = function() {
                reject(new Error('Network error'));
            };
            
            xhr.send(JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params,
                id: Math.floor(Math.random() * 1000000000)
            }));
        });
    }
}

    // Initialize when DOM is ready
    function initBuilder() {
        console.log("[ContractBuilder] Checking for initialization...");
        if (document.getElementById("contract-live-builder")) {
            console.log("[ContractBuilder] Container found, creating instance...");
            window.contractBuilder = new ContractLiveBuilder();
        } else {
            console.log("[ContractBuilder] Container not found");
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initBuilder);
    } else {
        initBuilder();
    }

})();
