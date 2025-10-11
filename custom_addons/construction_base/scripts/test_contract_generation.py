# -*- coding: utf-8 -*-
"""
Script de test pour la génération de contrats
À exécuter dans la console Odoo pour tester
"""

def test_contract_generation(env):
    """Teste la génération de contrats avec des données existantes."""
    from datetime import datetime, timedelta
    
    print("🧪 === TEST GÉNÉRATION DE CONTRATS ===")
    
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
    
    # 3. Vérifier les sous-traitants
    subcontractors = env['res.partner'].search([
        ('supplier_rank', '>', 0),
        ('contact_type', '=', 'sous_traitant')
    ])
    print(f"👷 Sous-traitants disponibles: {len(subcontractors)}")
    
    if not subcontractors:
        print("❌ Aucun sous-traitant trouvé.")
        return False
    
    # Prendre le premier sous-traitant
    subcontractor = subcontractors[0]
    print(f"✅ Sous-traitant sélectionné: {subcontractor.name}")
    
    # 4. Vérifier les bons de commande
    purchase_orders = env['purchase.order'].search([
        ('chantier_id', '=', chantier.id),
        ('partner_id', '=', subcontractor.id),
        ('state', 'in', ['purchase', 'done'])
    ])
    print(f"🛒 Bons de commande trouvés: {len(purchase_orders)}")
    
    # 5. Vérifier les tâches de planning
    planning_tasks = env['construction.planning.task'].search([
        ('chantier_id', '=', chantier.id),
        ('lot_id', '=', lot.id)
    ])
    print(f"📅 Tâches de planning trouvées: {len(planning_tasks)}")
    
    # 6. Créer des données de test si nécessaire
    if not purchase_orders:
        print("🔧 Création d'un bon de commande de test...")
        purchase_order = create_test_purchase_order(env, chantier, subcontractor, lot)
        if purchase_order:
            print(f"✅ Bon de commande créé: {purchase_order.name}")
        else:
            print("❌ Échec de création du bon de commande")
            return False
    
    if not planning_tasks:
        print("🔧 Création de tâches de planning de test...")
        task = create_test_planning_task(env, chantier, subcontractor, lot)
        if task:
            print(f"✅ Tâche créée: {task.name}")
        else:
            print("❌ Échec de création de la tâche")
            return False
    
    # 7. Tester la génération de preview
    print("🔧 Test de génération de preview...")
    try:
        contract_service = env['construction.contract.service']
        
        contract_data = {
            'start_date': datetime.now().date(),
            'end_date': (datetime.now() + timedelta(days=30)).date(),
            'total_amount': 50000.0,
            'payment_terms': '30_days',
            'warranty_period': 12,
            'insurance_required': True,
            'notes': 'Test de génération de contrat',
            'urssaf_code': '43.34Z'
        }
        
        preview_html = contract_service.generate_preview_html(
            chantier,
            subcontractor,
            env['construction.lot'].browse([lot.id]),
            contract_data
        )
        
        print("✅ Preview généré avec succès!")
        print(f"📄 Taille du HTML: {len(preview_html)} caractères")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération: {e}")
        return False

def create_test_purchase_order(env, chantier, subcontractor, lot):
    """Crée un bon de commande de test."""
    try:
        # Créer un produit de test
        product = env['product.product'].create({
            'name': 'Produit Test Contrat',
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
            'name': 'Produit Test Contrat - 10 unités',
            'product_qty': 10,
            'price_unit': 100.0,
            'lot_id': lot.id
        })
        
        return purchase_order
        
    except Exception as e:
        print(f"❌ Erreur création bon de commande: {e}")
        return False

def create_test_planning_task(env, chantier, subcontractor, lot):
    """Crée une tâche de planning de test."""
    try:
        task = env['construction.planning.task'].create({
            'name': 'Tâche Test Contrat',
            'chantier_id': chantier.id,
            'lot_id': lot.id,
            'subcontractor_id': subcontractor.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_stop': datetime.now() + timedelta(days=10),
            'state': 'planned'
        })
        
        return task
        
    except Exception as e:
        print(f"❌ Erreur création tâche: {e}")
        return False

def debug_existing_data(env):
    """Débogue les données existantes."""
    print("🔍 === DÉBOGAGE DES DONNÉES EXISTANTES ===")
    
    # Chantiers
    chantiers = env['construction.chantier'].search([])
    print(f"📋 Chantiers: {len(chantiers)}")
    for chantier in chantiers:
        print(f"   - {chantier.name} (ID: {chantier.id}): {len(chantier.lots_ids)} lots")
    
    # Lots
    lots = env['construction.lot'].search([])
    print(f"📦 Lots: {len(lots)}")
    for lot in lots:
        print(f"   - {lot.name} (ID: {lot.id}) - Chantier: {lot.chantier_id.name if lot.chantier_id else 'Aucun'}")
    
    # Sous-traitants
    subcontractors = env['res.partner'].search([
        ('supplier_rank', '>', 0),
        ('contact_type', '=', 'sous_traitant')
    ])
    print(f"👷 Sous-traitants: {len(subcontractors)}")
    for sub in subcontractors:
        print(f"   - {sub.name} (ID: {sub.id})")
    
    # Bons de commande
    orders = env['purchase.order'].search([])
    print(f"🛒 Bons de commande: {len(orders)}")
    for order in orders:
        print(f"   - {order.name} (ID: {order.id}): {order.partner_id.name}, {order.state}")
        if hasattr(order, 'chantier_id') and order.chantier_id:
            print(f"     * Chantier: {order.chantier_id.name}")
        if hasattr(order, 'lot_ids') and order.lot_ids:
            print(f"     * Lots: {[lot.name for lot in order.lot_ids]}")
    
    # Tâches de planning
    tasks = env['construction.planning.task'].search([])
    print(f"📅 Tâches de planning: {len(tasks)}")
    for task in tasks:
        print(f"   - {task.name} (ID: {task.id}): lot={task.lot_id.name if task.lot_id else 'Aucun'}, chantier={task.chantier_id.name}")

# Instructions d'utilisation:
# 1. Ouvrir la console Odoo (Settings > Technical > Database Structure > Models)
# 2. Aller dans le modèle 'construction.chantier'
# 3. Exécuter: test_contract_generation(env)
# 4. Ou pour déboguer: debug_existing_data(env)
