# -*- coding: utf-8 -*-
"""
Script de test spécifique pour la recherche de bons de commande par lot
À exécuter dans la console Odoo pour tester
"""

def test_lot_purchase_orders(env):
    """Teste la recherche de bons de commande par lot."""
    from datetime import datetime, timedelta
    
    print("🧪 === TEST RECHERCHE BONS DE COMMANDE PAR LOT ===")
    
    # 1. Vérifier les données existantes
    chantiers = env['construction.chantier'].search([])
    print(f"📋 Chantiers disponibles: {len(chantiers)}")
    
    if not chantiers:
        print("❌ Aucun chantier trouvé. Créez d'abord un chantier.")
        return False
    
    # Prendre le premier chantier
    chantier = chantiers[0]
    print(f"✅ Chantier sélectionné: {chantier.name}")
    
    # 2. Vérifier les lots
    lots = chantier.lots_ids
    print(f"📦 Lots du chantier: {len(lots)}")
    
    if not lots:
        print("❌ Aucun lot trouvé dans le chantier.")
        return False
    
    # Prendre le premier lot
    lot = lots[0]
    print(f"✅ Lot sélectionné: {lot.name}")
    
    # 3. Tester la recherche de bons de commande par lot
    print(f"🔍 Test de recherche pour lot {lot.name}:")
    
    # Méthode 1: Via lot_ids
    orders_via_lot_ids = env['purchase.order'].search([
        ('lot_ids', 'in', [lot.id]),
        ('state', 'in', ['purchase', 'done'])
    ])
    print(f"   - Bons de commande avec lot {lot.name} dans lot_ids: {len(orders_via_lot_ids)}")
    for po in orders_via_lot_ids:
        print(f"     * {po.name} (ID: {po.id}): partenaire={po.partner_id.name}, chantier={po.chantier_id.name if po.chantier_id else 'Aucun'}")
    
    # Méthode 2: Via lignes de commande
    lines_with_lot = env['purchase.order.line'].search([
        ('lot_id', '=', lot.id),
        ('order_id.state', 'in', ['purchase', 'done'])
    ])
    orders_via_lines = lines_with_lot.mapped('order_id')
    print(f"   - Bons de commande avec lot {lot.name} dans lignes: {len(orders_via_lines)}")
    for po in orders_via_lines:
        print(f"     * {po.name} (ID: {po.id}): partenaire={po.partner_id.name}, chantier={po.chantier_id.name if po.chantier_id else 'Aucun'}")
    
    # Combiner les deux méthodes
    all_lot_orders = orders_via_lot_ids | orders_via_lines
    print(f"   - Total bons de commande liés au lot {lot.name}: {len(all_lot_orders)}")
    
    if all_lot_orders:
        print("✅ Bons de commande trouvés pour le lot!")
        return True
    else:
        print("❌ Aucun bon de commande trouvé pour le lot.")
        print("🔧 Création d'un bon de commande de test...")
        return create_test_purchase_order_for_lot(env, chantier, lot)

def create_test_purchase_order_for_lot(env, chantier, lot):
    """Crée un bon de commande de test pour un lot spécifique."""
    try:
        # Créer un sous-traitant de test
        subcontractor = env['res.partner'].create({
            'name': f'Sous-traitant Test {lot.name}',
            'email': f'sous-traitant.{lot.name.lower().replace(" ", "_")}@test.com',
            'supplier_rank': 1,
            'contact_type': 'sous_traitant'
        })
        
        # Créer un produit de test
        product = env['product.product'].create({
            'name': f'Produit Test {lot.name}',
            'type': 'product',
            'list_price': 100.0
        })
        
        # Créer le bon de commande
        purchase_order = env['purchase.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': chantier.id,
            'lot_ids': [(6, 0, [lot.id])],
            'state': 'purchase',
            'date_order': datetime.now()
        })
        
        # Créer une ligne de commande
        env['purchase.order.line'].create({
            'order_id': purchase_order.id,
            'product_id': product.id,
            'name': f'Produit Test {lot.name} - 10 unités',
            'product_qty': 10,
            'price_unit': 100.0,
            'lot_id': lot.id
        })
        
        print(f"✅ Bon de commande créé: {purchase_order.name}")
        print(f"   - Partenaire: {subcontractor.name}")
        print(f"   - Lot: {lot.name}")
        print(f"   - État: {purchase_order.state}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur création bon de commande: {e}")
        return False

def debug_all_purchase_orders(env):
    """Débogue tous les bons de commande existants."""
    print("🔍 === DÉBOGAGE TOUS LES BONS DE COMMANDE ===")
    
    # Tous les bons de commande
    all_orders = env['purchase.order'].search([])
    print(f"🛒 Total bons de commande: {len(all_orders)}")
    
    for order in all_orders:
        print(f"   - {order.name} (ID: {order.id}):")
        print(f"     * Partenaire: {order.partner_id.name}")
        print(f"     * État: {order.state}")
        print(f"     * Chantier: {order.chantier_id.name if order.chantier_id else 'Aucun'}")
        print(f"     * Lots dans lot_ids: {[lot.name for lot in order.lot_ids]}")
        print(f"     * Lignes: {len(order.order_line)}")
        
        # Vérifier les lignes de commande
        for line in order.order_line:
            print(f"       * Ligne: {line.product_id.name if line.product_id else line.name}")
            print(f"         - Lot: {line.lot_id.name if line.lot_id else 'Aucun'}")

def debug_all_lots(env):
    """Débogue tous les lots existants."""
    print("🔍 === DÉBOGAGE TOUS LES LOTS ===")
    
    # Tous les lots
    all_lots = env['construction.lot'].search([])
    print(f"📦 Total lots: {len(all_lots)}")
    
    for lot in all_lots:
        print(f"   - {lot.name} (ID: {lot.id}):")
        print(f"     * Chantier: {lot.chantier_id.name if lot.chantier_id else 'Aucun'}")
        print(f"     * Prix: {lot.price}")
        print(f"     * Code URSSAF: {lot.urssaf_code}")
        
        # Vérifier les bons de commande liés à ce lot
        orders_via_lot_ids = env['purchase.order'].search([
            ('lot_ids', 'in', [lot.id])
        ])
        print(f"     * Bons de commande avec lot dans lot_ids: {len(orders_via_lot_ids)}")
        
        lines_with_lot = env['purchase.order.line'].search([
            ('lot_id', '=', lot.id)
        ])
        print(f"     * Lignes de commande avec lot: {len(lines_with_lot)}")

# Instructions d'utilisation:
# 1. Ouvrir la console Odoo (Settings > Technical > Database Structure > Models)
# 2. Aller dans le modèle 'construction.chantier'
# 3. Exécuter: test_lot_purchase_orders(env)
# 4. Ou pour déboguer: debug_all_purchase_orders(env) ou debug_all_lots(env)
