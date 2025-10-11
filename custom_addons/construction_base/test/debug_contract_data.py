# -*- coding: utf-8 -*-
"""
Script de débogage pour vérifier les données de contrats
"""

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class DebugContractData(models.TransientModel):
    _name = 'debug.contract.data'
    _description = 'Débogage des données de contrats'

    def debug_contract_data(self, chantier_id, subcontractor_id, lot_ids):
        """Débogue les données pour un contrat spécifique."""
        _logger.info("🔍 === DÉBOGAGE DES DONNÉES DE CONTRAT ===")
        
        chantier = self.env['construction.chantier'].browse(chantier_id)
        subcontractor = self.env['res.partner'].browse(subcontractor_id)
        lots = self.env['construction.lot'].browse(lot_ids)
        
        _logger.info(f"📋 Chantier: {chantier.name} (ID: {chantier.id})")
        _logger.info(f"👷 Sous-traitant: {subcontractor.name} (ID: {subcontractor.id})")
        _logger.info(f"📦 Lots: {[lot.name for lot in lots]}")
        
        # Vérifier les bons de commande
        self._debug_purchase_orders(chantier, subcontractor, lots)
        
        # Vérifier les tâches de planning
        self._debug_planning_tasks(chantier, lots)
        
        return True
    
    def _debug_purchase_orders(self, chantier, subcontractor, lots):
        """Débogue les bons de commande."""
        _logger.info("🛒 === DÉBOGAGE BONS DE COMMANDE ===")
        
        # Rechercher tous les bons de commande du chantier
        all_orders = self.env['purchase.order'].search([
            ('chantier_id', '=', chantier.id)
        ])
        _logger.info(f"   - Total bons de commande du chantier: {len(all_orders)}")
        
        for order in all_orders:
            _logger.info(f"   - Commande {order.name}:")
            _logger.info(f"     * Partenaire: {order.partner_id.name}")
            _logger.info(f"     * État: {order.state}")
            _logger.info(f"     * Lots: {[lot.name for lot in order.lot_ids]}")
            _logger.info(f"     * Lignes: {len(order.order_line)}")
            
            # Vérifier les lignes de commande
            for line in order.order_line:
                _logger.info(f"     * Ligne: {line.product_id.name if line.product_id else line.name}")
                _logger.info(f"       - Lot: {line.lot_id.name if line.lot_id else 'Aucun'}")
        
        # Rechercher les bons de commande du sous-traitant
        subcontractor_orders = self.env['purchase.order'].search([
            ('partner_id', '=', subcontractor.id),
            ('chantier_id', '=', chantier.id)
        ])
        _logger.info(f"   - Bons de commande du sous-traitant: {len(subcontractor_orders)}")
        
        # Rechercher les lignes de commande avec les lots spécifiques
        for lot in lots:
            _logger.info(f"   - Recherche pour lot {lot.name}:")
            
            # Via lot_ids
            orders_with_lot = all_orders.filtered(lambda po: lot in po.lot_ids)
            _logger.info(f"     * Commandes avec lot dans lot_ids: {len(orders_with_lot)}")
            
            # Via lignes de commande
            lines_with_lot = self.env['purchase.order.line'].search([
                ('lot_id', '=', lot.id),
                ('order_id.chantier_id', '=', chantier.id)
            ])
            _logger.info(f"     * Lignes de commande avec lot: {len(lines_with_lot)}")
            
            for line in lines_with_lot:
                _logger.info(f"       - Ligne {line.order_id.name}: {line.product_id.name if line.product_id else line.name}")
    
    def _debug_planning_tasks(self, chantier, lots):
        """Débogue les tâches de planning."""
        _logger.info("📅 === DÉBOGAGE TÂCHES DE PLANNING ===")
        
        # Rechercher toutes les tâches du chantier
        all_tasks = self.env['construction.planning.task'].search([
            ('chantier_id', '=', chantier.id)
        ])
        _logger.info(f"   - Total tâches du chantier: {len(all_tasks)}")
        
        for task in all_tasks:
            _logger.info(f"   - Tâche {task.name}:")
            _logger.info(f"     * Lot: {task.lot_id.name if task.lot_id else 'Aucun'}")
            _logger.info(f"     * Sous-traitant: {task.subcontractor_id.name if task.subcontractor_id else 'Aucun'}")
            _logger.info(f"     * État: {task.state}")
            _logger.info(f"     * Dates: {task.date_start} - {task.date_stop}")
        
        # Rechercher les tâches pour chaque lot
        for lot in lots:
            _logger.info(f"   - Recherche tâches pour lot {lot.name}:")
            
            lot_tasks = self.env['construction.planning.task'].search([
                ('lot_id', '=', lot.id),
                ('chantier_id', '=', chantier.id)
            ])
            _logger.info(f"     * Tâches trouvées: {len(lot_tasks)}")
            
            for task in lot_tasks:
                _logger.info(f"       - {task.name} ({task.state})")
    
    def debug_all_data(self):
        """Débogue toutes les données du système."""
        _logger.info("🔍 === DÉBOGAGE COMPLET DU SYSTÈME ===")
        
        # Vérifier les chantiers
        chantiers = self.env['construction.chantier'].search([])
        _logger.info(f"📋 Chantiers: {len(chantiers)}")
        for chantier in chantiers:
            _logger.info(f"   - {chantier.name}: {len(chantier.lots_ids)} lots")
        
        # Vérifier les lots
        lots = self.env['construction.lot'].search([])
        _logger.info(f"📦 Lots: {len(lots)}")
        for lot in lots:
            _logger.info(f"   - {lot.name} (chantier: {lot.chantier_id.name})")
        
        # Vérifier les bons de commande
        orders = self.env['purchase.order'].search([])
        _logger.info(f"🛒 Bons de commande: {len(orders)}")
        for order in orders:
            _logger.info(f"   - {order.name}: {order.partner_id.name}, {order.state}")
        
        # Vérifier les tâches de planning
        tasks = self.env['construction.planning.task'].search([])
        _logger.info(f"📅 Tâches de planning: {len(tasks)}")
        for task in tasks:
            _logger.info(f"   - {task.name}: lot={task.lot_id.name if task.lot_id else 'Aucun'}")
        
        return True
    
    def create_test_data(self):
        """Crée des données de test pour le débogage."""
        _logger.info("🔧 === CRÉATION DE DONNÉES DE TEST ===")
        
        from datetime import datetime, timedelta
        
        # Créer un chantier de test
        chantier = self.env['construction.chantier'].create({
            'name': 'Chantier Test Debug',
            'client': self.env['res.partner'].create({
                'name': 'Client Test Debug',
                'email': 'client.debug@test.com'
            }).id,
            'address': '456 Rue Debug, 33000 Bordeaux',
            'date_start_contract': datetime.now().date(),
            'date_end_contract': (datetime.now() + timedelta(days=90)).date(),
            'total_cost': 75000.0,
        })
        
        # Créer un sous-traitant
        subcontractor = self.env['res.partner'].create({
            'name': 'Sous-traitant Test Debug',
            'email': 'sous-traitant.debug@test.com',
            'supplier_rank': 1,
            'contact_type': 'sous_traitant'
        })
        
        # Créer un lot
        lot = self.env['construction.lot'].create({
            'name': 'Lot Test Debug - Électricité',
            'chantier_id': chantier.id,
            'price': 25000.0,
            'urssaf_code': '43.21A - Travaux d\'installation électrique dans tous locaux',
            'description': 'Installation électrique complète',
            'subcontractor_ids': [(6, 0, [subcontractor.id])]
        })
        
        # Créer des tâches de planning
        task1 = self.env['construction.planning.task'].create({
            'name': 'Installation tableau électrique',
            'chantier_id': chantier.id,
            'lot_id': lot.id,
            'subcontractor_id': subcontractor.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_stop': datetime.now() + timedelta(days=7),
            'state': 'planned'
        })
        
        task2 = self.env['construction.planning.task'].create({
            'name': 'Pose des prises et interrupteurs',
            'chantier_id': chantier.id,
            'lot_id': lot.id,
            'subcontractor_id': subcontractor.id,
            'date_start': datetime.now() + timedelta(days=8),
            'date_stop': datetime.now() + timedelta(days=20),
            'state': 'planned'
        })
        
        # Créer un bon de commande
        purchase_order = self.env['purchase.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': chantier.id,
            'lot_ids': [(6, 0, [lot.id])],
            'state': 'purchase',
            'date_order': datetime.now()
        })
        
        # Créer des produits
        product1 = self.env['product.product'].create({
            'name': 'Tableau électrique',
            'type': 'product',
            'list_price': 500.0
        })
        
        product2 = self.env['product.product'].create({
            'name': 'Prises électriques',
            'type': 'product',
            'list_price': 15.0
        })
        
        # Créer des lignes de commande
        self.env['purchase.order.line'].create({
            'order_id': purchase_order.id,
            'product_id': product1.id,
            'name': 'Tableau électrique 12 modules',
            'product_qty': 1,
            'price_unit': 500.0,
            'lot_id': lot.id
        })
        
        self.env['purchase.order.line'].create({
            'order_id': purchase_order.id,
            'product_id': product2.id,
            'name': 'Prises électriques 16A',
            'product_qty': 20,
            'price_unit': 15.0,
            'lot_id': lot.id
        })
        
        _logger.info(f"✅ Données de test créées:")
        _logger.info(f"   - Chantier: {chantier.name}")
        _logger.info(f"   - Sous-traitant: {subcontractor.name}")
        _logger.info(f"   - Lot: {lot.name}")
        _logger.info(f"   - Tâches: {len([task1, task2])}")
        _logger.info(f"   - Bon de commande: {purchase_order.name}")
        
        return {
            'chantier_id': chantier.id,
            'subcontractor_id': subcontractor.id,
            'lot_ids': [lot.id]
        }
