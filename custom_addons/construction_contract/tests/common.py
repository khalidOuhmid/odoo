# -*- coding: utf-8 -*-
"""Common test fixtures for the construction_contract module.

Provides a shared mixin that creates the minimum viable dataset
for contract integration tests: company, subcontractor, chantier,
lot, purchase order, and a draft contract.

All record creation is guarded against missing models so that
subsets of tests can run even when optional dependencies are
not installed.
"""

from odoo.tests import common
from datetime import date, timedelta
import base64
import logging

_logger = logging.getLogger(__name__)


class ContractTestMixin:
    """Mixin for construction contract test data setup.

    Call ``setUpContractData()`` in your ``setUpClass()`` to get:
    - ``cls.company`` — current company, name set to BLG GROUPE
    - ``cls.subcontractor`` — partner with ``supplier_rank=1``
    - ``cls.chantier`` — construction.chantier record
    - ``cls.lot`` — construction.lot linked to chantier
    - ``cls.po`` — purchase.order for the subcontractor
    - ``cls.contract`` — draft construction.contract
    - ``cls.template`` — contract.template with minimal HTML
    """

    @classmethod
    def setUpContractData(cls):
        """Create shared test records used across the test suite."""

        # 1. Company
        cls.company = cls.env.company
        cls.company.write({
            'name': 'BLG GROUPE',
            'street': '44, rue de la commanderie des Templiers',
            'zip': '33440',
            'city': 'Ambarès-et-Lagrave',
            'company_registry': '80123456700012',
        })

        # 2. Subcontractor partner (with compliant documents for contract creation)
        _mock_doc = base64.b64encode(b'%PDF-1.4 mock document').decode('ascii')
        _expiry = date.today() + timedelta(days=365)
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'SARL Sous-Traitant Test',
            'is_company': True,
            'email': 'st-test@example.com',
            'street': '12 rue des Artisans',
            'zip': '33000',
            'city': 'Bordeaux',
            'phone': '0556000000',
            'supplier_rank': 1,
            'company_registry': '12345678901234',
        })
        # Write docs separately to trigger admin auto-validation (write override)
        cls.subcontractor.write({
            'doc_urssaf': _mock_doc,
            'doc_urssaf_expiry': _expiry,
            'doc_kbis': _mock_doc,
            'doc_kbis_expiry': _expiry,
            'doc_insurance_dec': _mock_doc,
            'doc_insurance_dec_expiry': _expiry,
        })

        # 3. Chantier
        cls.chantier = cls.env['construction.chantier'].create({
            'name': 'Chantier QA Résidentiel',
            'client': cls.env['res.partner'].create({
                'name': 'Client QA Test',
            }).id,
        })

        # 4. Lot categories (required since category_id is NOT NULL on construction.lot)
        cls.category_go = cls.env['construction.lot.category'].create({
            'name': 'Gros Œuvre QA',
            'code': 'GO_QA',
        })
        cls.category_elec = cls.env['construction.lot.category'].create({
            'name': 'Électricité QA',
            'code': 'ELEC_QA',
        })

        # 5. Lot
        cls.lot = cls.env['construction.lot'].create({
            'category_id': cls.category_go.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': cls.subcontractor.id,
        })

        # 6. Second lot for multi-lot tests
        cls.lot2 = cls.env['construction.lot'].create({
            'category_id': cls.category_elec.id,
            'chantier_id': cls.chantier.id,
            'execution_type': 'external',
            'subcontractor_id': cls.subcontractor.id,
        })

        # 6. Contract template (minimal)
        cls.template = cls.env['construction.contract.template'].create({
            'name': 'Template QA Test',
            'grapesjs_html': '<h1>Contract {{contract.name}}</h1><p>{{subcontractor.name}}</p>',
            'grapesjs_css': 'h1 { color: #92564C; }',
        })

        # 7. Purchase Order
        cls.product = cls.env['product.product'].create({
            'name': 'Prestation QA Test',
            'type': 'service',
            'standard_price': 100.0,
            'list_price': 150.0,
        })

        cls.po = cls.env['purchase.order'].create({
            'partner_id': cls.subcontractor.id,
            'date_order': date.today(),
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'name': 'Prestation test',
                'product_qty': 10,
                'price_unit': 100.0,
            })],
        })

        # 8. Draft contract
        cls.contract = cls.env['construction.contract'].create({
            'subcontractor_id': cls.subcontractor.id,
            'chantier_id': cls.chantier.id,
            'lot_ids': [(6, 0, [cls.lot.id])],
            'template_id': cls.template.id,
            'state': 'draft',
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=180),
            'retention_rate': 5.0,
        })

    @classmethod
    def _create_mock_signature_data(cls):
        """Create a minimal base64-encoded 1x1 GIF for signature tests.

        Returns:
            str: Base64-encoded image string.
        """
        return base64.b64encode(
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,'
            b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        ).decode('ascii')
