/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { Component, useState, useRef, onMounted, App, xml } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

/**
 * ContractSignatureViewer
 *
 * Composant Owl 2 pour le portail de signature de contrat.
 * Monté par ContractSignaturePortal (publicWidget) dans le contexte
 * web.assets_frontend (pages publiques/portail).
 *
 * NOTE: en Odoo 18, getTemplate() de @web/core/templates alimente un
 * registre compilé à la volée dans le bundle BACKEND uniquement.
 * Dans le bundle FRONTEND (public), le template doit être fourni via
 * le tag xml`` d'@odoo/owl (template inline compilé par Owl lui-même),
 * ce qui garantit que l'App peut être montée sans dépendance au registre
 * backend.
 */

const PORTAL_SIGNATURE_TEMPLATE = xml/* xml */`
    <div class="o_portal_contract_container row">

        <!-- LEFT COLUMN: Contract Viewer -->
        <div class="col-lg-8 col-12 mb-4">
            <div class="card h-100 shadow-sm border-0">
                <div class="card-header bg-white border-bottom-0 pt-4 pb-0">
                    <h4 class="mb-0 text-primary">
                        <i class="fa fa-file-text-o mr-2"/> Contenu du Contrat
                    </h4>
                    <p class="text-muted small mt-2">
                        <t t-if="!state.hasReachedEnd">
                            <i class="fa fa-info-circle text-warning"/> Veuillez faire défiler le document jusqu'en bas pour débloquer la signature.
                        </t>
                        <t t-else="">
                            <i class="fa fa-check-circle text-success"/> Lecture terminée. Vous pouvez procéder à la signature.
                        </t>
                    </p>

                    <!-- Progress Bar -->
                    <div class="progress mb-3" style="height: 8px; border-radius: 10px;">
                        <div class="progress-bar bg-success" role="progressbar"
                             t-att-style="'width: ' + state.scrollProgress + '%'"
                             t-att-aria-valuenow="state.scrollProgress"
                             aria-valuemin="0" aria-valuemax="100"/>
                    </div>
                </div>

                <div class="card-body p-0">
                    <!-- Scrollable Window for HTML -->
                    <div t-ref="contentContainer"
                         class="contract-scroll-window p-4"
                         style="max-height: 600px; overflow-y: auto; background-color: #f8f9fa; border-top: 1px solid #eee; border-bottom: 1px solid #eee;"
                         t-on-scroll="onScroll">
                         <!-- Inject HTML Payload directly -->
                         <div class="bg-white p-4 shadow-sm" style="min-height: 1000px;" t-out="props.contractHtml"/>
                    </div>
                </div>
            </div>
        </div>

        <!-- RIGHT COLUMN: Signature Panel -->
        <div class="col-lg-4 col-12 mb-4">
            <div class="card shadow-sm border-0 h-100" t-att-class="state.hasReachedEnd ? 'border-success' : ''">
                <div class="card-header bg-white pt-4 pb-0 border-bottom-0">
                    <h4 class="mb-0" t-att-class="state.hasReachedEnd ? 'text-success' : 'text-muted'">
                        <i class="fa fa-pencil mr-2"/> Signature
                    </h4>
                </div>

                <div class="card-body d-flex flex-column">

                    <t t-if="state.error">
                        <div class="alert alert-danger p-2 small">
                            <i class="fa fa-exclamation-triangle mr-1"/> <t t-esc="state.error"/>
                        </div>
                    </t>

                    <!-- Signature Canvas Box -->
                    <div class="signature-box-wrapper flex-grow-1 d-flex flex-column align-items-center justify-content-center"
                         style="position: relative; border: 2px dashed #ddd; border-radius: 8px; background: #fff; min-height: 250px; transition: all 0.3s;"
                         t-att-style="state.hasReachedEnd ? 'border-color: #28a745;' : 'opacity: 0.6; pointer-events: none;'">

                        <canvas t-ref="signatureCanvas" style="width: 100%; height: 250px; cursor: crosshair; touch-action: none;"></canvas>

                        <t t-if="!state.hasReachedEnd">
                            <div class="position-absolute d-flex flex-column align-items-center text-muted" style="pointer-events: none;">
                                <i class="fa fa-lock fa-3x mb-2"/>
                                <span class="font-weight-bold">Signature Verrouillée</span>
                                <small>Lisez le contrat entier</small>
                            </div>
                        </t>
                        <t t-elif="!state.signatureData">
                            <div class="position-absolute d-flex flex-column align-items-center text-muted" style="pointer-events: none; opacity: 0.5;">
                                <i class="fa fa-pencil fa-2x mb-1"/>
                                <span>Signez ici</span>
                            </div>
                        </t>
                    </div>

                    <!-- Controls -->
                    <div class="mt-3">
                        <button class="btn btn-outline-secondary btn-block mb-2"
                                t-on-click="clearSignature"
                                t-att-disabled="!state.hasReachedEnd or !state.signatureData or state.isSigning">
                            <i class="fa fa-eraser mr-1"/> Effacer
                        </button>

                        <button class="btn btn-success btn-block btn-lg"
                                t-on-click="submitSignature"
                                t-att-disabled="!state.hasReachedEnd or !state.signatureData or state.isSigning">
                            <t t-if="state.isSigning">
                                <i class="fa fa-spinner fa-spin mr-1"/> Signature en cours...
                            </t>
                            <t t-else="">
                                <i class="fa fa-check-circle mr-1"/> Valider et Signer
                            </t>
                        </button>
                    </div>

                </div>
            </div>
        </div>
    </div>
`;

export class ContractSignatureViewer extends Component {
    static template = PORTAL_SIGNATURE_TEMPLATE;

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

publicWidget.registry.ContractSignaturePortal = publicWidget.Widget.extend({
    selector: '.o_portal_contract_signature_app',

    start: function () {
        // Ne pas utiliser async/await : dans le framework publicWidget legacy,
        // this._super est remis à null par le framework après l'appel synchrone.
        // Capturer _super immédiatement, avant tout await.
        const _superStart = this._super.bind(this);

        const props = {
            contractId: this.$el.data('contractId'),
            accessToken: this.$el.data('accessToken'),
        };

        const htmlPayloadEl = document.getElementById('contract-html-payload');
        props.contractHtml = htmlPayloadEl ? htmlPayloadEl.innerHTML : "";

        // Template inline (xml``) — pas besoin de registre externe.
        this.app = new App(ContractSignatureViewer, { props });

        return this.app.mount(this.el).then(() => _superStart());
    },

    destroy: function () {
        if (this.app) {
            this.app.destroy();
        }
        this._super.apply(this, arguments);
    }
});
