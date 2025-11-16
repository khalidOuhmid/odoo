"use strict";

odoo.define('construction_contract.pdf_viewer_controls', function (require) {
    const publicWidget = require('web.public.widget');

    publicWidget.registry.ContractPdfViewer = publicWidget.Widget.extend({
        selector: '.signature-portal-wrapper',

        start() {
            this.$iframe = this.$('#pdf-viewer');
            this.currentPageEl = this.el.querySelector('#current-page');
            this.totalPagesEl = this.el.querySelector('#total-pages');
            this.prevBtn = this.el.querySelector('#btn-prev-page');
            this.nextBtn = this.el.querySelector('#btn-next-page');
            if (this.prevBtn) {
                this.prevBtn.addEventListener('click', this._onPrevPage.bind(this));
            }
            if (this.nextBtn) {
                this.nextBtn.addEventListener('click', this._onNextPage.bind(this));
            }
            if (this.$iframe.length) {
                this.$iframe.on('load', this._onPdfLoaded.bind(this));
            }
            return this._super.apply(this, arguments);
        },

        _onPdfLoaded() {
            // Placeholder hook – real implementation would integrate pdf.js viewer.
        },

        _onPrevPage(ev) {
            ev.preventDefault();
        },

        _onNextPage(ev) {
            ev.preventDefault();
        },
    });
});

