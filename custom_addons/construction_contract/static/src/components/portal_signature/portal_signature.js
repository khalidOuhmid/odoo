/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { Component, useState, useRef, onMounted, App } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

export class ContractSignatureViewer extends Component {
    setup() {
        this.state = useState({
            hasReachedEnd: false,
            isSigning: false,
            signatureData: null,
            error: null,
            scrollProgress: 0,
        });
        this.contentRef = useRef("contentContainer");
        this.canvasRef = useRef("signatureCanvas");
        this.ctx = null;
        this.isDrawing = false;

        onMounted(() => {
            this._initCanvas();
            // Timeout to allow DOM layout to settle before checking scroll
            setTimeout(() => this._checkScroll(), 300);
        });
    }

    onScroll(ev) {
        this._checkScroll();
    }

    _checkScroll() {
        const el = this.contentRef.el;
        if (!el) return;

        const scrollableHeight = el.scrollHeight - el.clientHeight;
        if (scrollableHeight <= 0) {
            this.state.scrollProgress = 100;
            this.state.hasReachedEnd = true;
            return;
        }

        const currentScroll = el.scrollTop;
        const progress = Math.min(100, Math.round((currentScroll / scrollableHeight) * 100));
        this.state.scrollProgress = progress;

        // 10px tolerance
        if (currentScroll + el.clientHeight >= el.scrollHeight - 10) {
            this.state.hasReachedEnd = true;
            this.state.scrollProgress = 100;
        }
    }

    _initCanvas() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;

        // Setup high-DPI canvas
        const rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width || 600;
        canvas.height = 250; // Fixed height for signature

        this.ctx = canvas.getContext("2d");
        this.ctx.lineWidth = 3;
        this.ctx.lineCap = "round";
        this.ctx.strokeStyle = "#000000";

        // Mouse Events
        canvas.addEventListener("mousedown", this.startDrawing.bind(this));
        canvas.addEventListener("mousemove", this.draw.bind(this));
        canvas.addEventListener("mouseup", this.stopDrawing.bind(this));
        canvas.addEventListener("mouseout", this.stopDrawing.bind(this));

        // Touch Events
        canvas.addEventListener("touchstart", this.handleTouch.bind(this), { passive: false });
        canvas.addEventListener("touchmove", this.handleTouch.bind(this), { passive: false });
        canvas.addEventListener("touchend", this.stopDrawing.bind(this));
    }

    handleTouch(ev) {
        if (!this.state.hasReachedEnd) return; // Prevent interaction if locked
        ev.preventDefault();
        const touch = ev.touches[0];

        if (ev.type === "touchend") {
            this.stopDrawing();
            return;
        }

        const mouseEvent = new MouseEvent(
            ev.type === "touchstart" ? "mousedown" : "mousemove",
            {
                clientX: touch.clientX,
                clientY: touch.clientY
            }
        );
        this.canvasRef.el.dispatchEvent(mouseEvent);
    }

    startDrawing(ev) {
        if (!this.state.hasReachedEnd) return;
        this.isDrawing = true;
        this.draw(ev);
    }

    draw(ev) {
        if (!this.isDrawing) return;
        const rect = this.canvasRef.el.getBoundingClientRect();
        const x = ev.clientX - rect.left;
        const y = ev.clientY - rect.top;

        this.ctx.lineTo(x, y);
        this.ctx.stroke();
        this.ctx.beginPath();
        this.ctx.moveTo(x, y);

        this.state.signatureData = this.canvasRef.el.toDataURL("image/png");
    }

    stopDrawing() {
        this.isDrawing = false;
        if (this.ctx) this.ctx.beginPath();
    }

    clearSignature() {
        const canvas = this.canvasRef.el;
        if (canvas && this.ctx) {
            this.ctx.clearRect(0, 0, canvas.width, canvas.height);
            this.state.signatureData = null;
        }
    }

    async submitSignature() {
        if (!this.state.signatureData) {
            this.state.error = "Veuillez dessiner votre signature dans le cadre prévu.";
            return;
        }

        this.state.isSigning = true;
        this.state.error = null;

        try {
            // Cut "data:image/png;base64," prefix for server
            const base64Data = this.state.signatureData.split(',')[1];

            const result = await rpc("/my/contract/" + this.props.contractId + "/save_signature", {
                access_token: this.props.accessToken,
                signature_data: base64Data,
            });

            if (result.status === 'success' && result.redirect_url) {
                window.location.href = result.redirect_url;
            } else {
                this.state.error = result.message || "Une erreur est survenue lors de la signature.";
                this.state.isSigning = false;
            }
        } catch (e) {
            this.state.error = "Erreur réseau. Veuillez réessayer.";
            this.state.isSigning = false;
            console.error(e);
        }
    }
}

ContractSignatureViewer.template = "construction_contract.PortalSignatureOWL";

publicWidget.registry.ContractSignaturePortal = publicWidget.Widget.extend({
    selector: '.o_portal_contract_signature_app',

    start: async function () {
        const props = {
            contractId: this.$el.data('contractId'),
            accessToken: this.$el.data('accessToken'),
        };

        const htmlPayloadEl = document.getElementById('contract-html-payload');
        props.contractHtml = htmlPayloadEl ? htmlPayloadEl.innerHTML : "";

        this.app = new App(ContractSignatureViewer, {
            templates: odoo.publicTemplates || undefined, // For Odoo 16/17+ dynamic templating in portal
            env: this.env || owl.Component.env || {},
            props: props,
        });

        await this.app.mount(this.el);
        return this._super.apply(this, arguments);
    },
    destroy: function () {
        if (this.app) {
            this.app.destroy();
        }
        this._super.apply(this, arguments);
    }
});
