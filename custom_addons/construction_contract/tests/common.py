# -*- coding: utf-8 -*-
from odoo.tests import common
from datetime import date, timedelta
import base64

class ContractTestMixin(object):
    """
    Mixin to setup the common dataset for construction contract tests.
    Used by both TransactionCase and HttpCase.
    """

    @classmethod
    def setUpContractData(cls):
        # 1. Company BLG
        cls.company = cls.env.company
        cls.company.write({
            'name': 'BLG GROUPE',
            'street': '44, rue de la commanderie des Templiers',
            'zip': '33440',
            'city': 'Ambarès et Lagrave',
            'logo': base64.b64encode(b'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'), # Mock 1x1 GIF
        })

        # 2. Subcontractor
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'SARL SOUS-TRAITANT',
            'is_company': True,
            'is_subcontractor': True,
            'email': 'sous-traitant@example.com',
            'street': '12 rue des Artisans',
            'zip': '33000',
            'city': 'Bordeaux',
            'phone': '0600000000',
            'siret': '12345678900001',
        })

        # 3. Chantier (Construction Project)
        # Check if model exists (dependency construction_core)
        if 'construction.chantier' in cls.env:
            cls.chantier = cls.env['construction.chantier'].create({
                'name': 'Chantier Test Residential',
                'code': 'CHANTIER-001',
                'address_id': cls.env['res.partner'].create({
                    'name': 'Adresse Chantier',
                    'street': '5 avenue des Chenes',
                    'zip': '33000',
                    'city': 'Bordeaux',
                }).id
            })
        else:
            # Fallback for mock environment if core not fully loaded logic matches
            # But the requirement says "1 chantier (construction.project) avec adresse."
            # The actual model name in prev files was 'construction.chantier'.
            pass

        # 4. Lot (Work Package)
        # Check if model exists
        if 'construction.lot' in cls.env:
            cls.lot = cls.env['construction.lot'].create({
                'name': 'Lot 01 - Gros Oeuvre',
                'chantier_id': cls.chantier.id,
                'description': 'Travaux de gros oeuvre et vrd',
            })
            
            # 4.1. Documents d'essai
            # Creating dummy attachments linked to the lot
            for doc_name in ['planning_chantier.pdf', 'planning_lot.pdf', 'cctp.pdf', 'bon_commande.pdf']:
                cls.env['ir.attachment'].create({
                    'name': doc_name,
                    'type': 'binary',
                    'datas': base64.b64encode(b'%PDF-1.4...mock content...'),
                    'res_model': 'construction.lot',
                    'res_id': cls.lot.id,
                    'mimetype': 'application/pdf',
                })

        # 5. Purchase Order (linked to lot)
        cls.po = cls.env['purchase.order'].create({
            'partner_id': cls.subcontractor.id,
            'name': 'PO-TEST-001',
            'date_order': date.today(),
            'amount_total': 10000.0,
            # If construction_purchase module links logs/chantier
            # 'chantier_id': cls.chantier.id, # Assuming field exists
        })
        
        # 6. Construction Contract (Draft)
        cls.contract = cls.env['construction.contract'].create({
            'name': 'New Contract', # Will be recomputed
            'subcontractor_id': cls.subcontractor.id,
            'chantier_id': cls.chantier.id,
            'lot_ids': [(6, 0, [cls.lot.id])],
            'purchase_order_ids': [(6, 0, [cls.po.id])],
            'state': 'draft',
        })
