"use strict";

odoo.define('construction_contract.page_validator', function (require) {
    const ajax = require('web.ajax');
    const publicWidget = require('web.public.widget');

    publicWidget.registry.ContractPageValidator = publicWidget.Widget.extend({
        selector: '.signature-portal-wrapper',
        events: {
            'click #btn-validate-page': '_onValidatePage',
        },

        start() {
            this.contractId = this.$el.data('contract-id');
            this.accessToken = this.$el.data('access-token');
            return this._super.apply(this, arguments);
        },

        _onValidatePage(ev) {
            ev.preventDefault();
            if (!this.contractId || !this.accessToken) {
                return;
            }
            ajax.jsonRpc('/contract/page/validate', 'call', {
                contract_id: parseInt(this.contractId, 10),
                access_token: this.accessToken,
            });
        },
    });
});

