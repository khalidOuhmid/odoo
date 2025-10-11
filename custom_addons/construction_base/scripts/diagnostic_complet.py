# -*- coding: utf-8 -*-
"""
Script de diagnostic complet pour identifier les problèmes de bons de commande
À exécuter dans la console Odoo pour diagnostiquer
"""

def diagnostic_complet(env):
    """Diagnostic complet pour identifier les problèmes."""
    from datetime import datetime, timedelta
    
    print("🔍 === DIAGNOSTIC COMPLET ===")
    
    # 1. Vérifier les chantiers
    chantiers = env['construction.chantier'].search([])
    print(f"📋 Chantiers disponibles: {len(chantiers)}")
    
    if not chantiers:
        print("❌ Aucun chantier trouvé!")
        return False
    
    # Prendre le premier chantier
    chantier = chantiers[0]
    print(f"✅ Chantier sélectionné: {chantier.name} (ID: {chantier.id})")
    
    # 2. Vérifier les lots
    lots = chantier.lots_ids
    print(f"📦 Lots du chantier: {len(lots)}")
    
    if not lots:
        print("❌ Aucun lot trouvé dans le chantier!")
        return False
    
    # Prendre le premier lot
    lot = lots[0]
    print(f"✅ Lot sélectionné: {lot.name} (ID: {lot.id})")
    
    # 3. Vérifier les sous-traitants
    subcontractors = env['res.partner'].search([
        ('supplier_rank', '>', 0),
        ('contact_type', '=', 'sous_traitant')
    ])
    print(f"👷 Sous-traitants disponibles: {len(subcontractors)}")
    
    if not subcontractors:
        print("❌ Aucun sous-traitant trouvé!")
        return False
    
    # Prendre le premier sous-traitant
    subcontractor = subcontractors[0]
    print(f"✅ Sous-traitant sélectionné: {subcontractor.name} (ID: {subcontractor.id})")
    
    # 4. DIAGNOSTIC DÉTAILLÉ DES BONS DE COMMANDE
    print(f"\n🔍 === DIAGNOSTIC BONS DE COMMANDE POUR LOT {lot.name} ===")
    
    # 4.1 Tous les bons de commande existants
    all_orders = env['purchase.order'].search([])
    print(f"🛒 Total bons de commande dans la base: {len(all_orders)}")
    
    # 4.2 Bons de commande avec ce lot dans lot_ids
    orders_via_lot_ids = env['purchase.order'].search([
        ('lot_ids', 'in', [lot.id])
    ])
    print(f"   - Bons de commande avec lot {lot.name} dans lot_ids: {len(orders_via_lot_ids)}")
    for po in orders_via_lot_ids:
        print(f"     * {po.name} (ID: {po.id}): partenaire={po.partner_id.name}, état={po.state}, chantier={po.chantier_id.name if po.chantier_id else 'Aucun'}")
    
    # 4.3 Bons de commande avec ce lot dans les lignes
    lines_with_lot = env['purchase.order.line'].search([
        ('lot_id', '=', lot.id)
    ])
    orders_via_lines = lines_with_lot.mapped('order_id')
    print(f"   - Bons de commande avec lot {lot.name} dans lignes: {len(orders_via_lines)}")
    for po in orders_via_lines:
        print(f"     * {po.name} (ID: {po.id}): partenaire={po.partner_id.name}, état={po.state}, chantier={po.chantier_id.name if po.chantier_id else 'Aucun'}")
    
    # 4.4 Bons de commande du chantier
    orders_chantier = env['purchase.order'].search([
        ('chantier_id', '=', chantier.id)
    ])
    print(f"   - Bons de commande du chantier {chantier.name}: {len(orders_chantier)}")
    for po in orders_chantier:
        print(f"     * {po.name} (ID: {po.id}): partenaire={po.partner_id.name}, état={po.state}, lots={[l.name for l in po.lot_ids]}")
    
    # 4.5 Bons de commande du sous-traitant
    orders_subcontractor = env['purchase.order'].search([
        ('partner_id', '=', subcontractor.id)
    ])
    print(f"   - Bons de commande du sous-traitant {subcontractor.name}: {len(orders_subcontractor)}")
    for po in orders_subcontractor:
        print(f"     * {po.name} (ID: {po.id}): chantier={po.chantier_id.name if po.chantier_id else 'Aucun'}, état={po.state}, lots={[l.name for l in po.lot_ids]}")
    
    # 4.6 Bons de commande confirmés (purchase/done)
    orders_confirmed = env['purchase.order'].search([
        ('state', 'in', ['purchase', 'done'])
    ])
    print(f"   - Bons de commande confirmés (purchase/done): {len(orders_confirmed)}")
    
    # 4.7 Bons de commande en draft
    orders_draft = env['purchase.order'].search([
        ('state', '=', 'draft')
    ])
    print(f"   - Bons de commande en draft: {len(orders_draft)}")
    
    # 5. CRÉER UN BON DE COMMANDE DE TEST SI NÉCESSAIRE
    if not orders_via_lot_ids and not orders_via_lines:
        print(f"\n🔧 === CRÉATION D'UN BON DE COMMANDE DE TEST ===")
        success = create_test_purchase_order_complete(env, chantier, lot, subcontractor)
        if success:
            print("✅ Bon de commande de test créé avec succès!")
            return True
        else:
            print("❌ Échec de création du bon de commande de test!")
            return False
    
    return True

def create_test_purchase_order_complete(env, chantier, lot, subcontractor):
    """Crée un bon de commande de test complet."""
    try:
        from datetime import datetime
        
        print(f"🔧 Création d'un bon de commande de test...")
        
        # 1. Créer un produit de test
        product = env['product.product'].create({
            'name': f'Produit Test {lot.name}',
            'type': 'product',
            'list_price': 100.0,
            'standard_price': 80.0
        })
        print(f"   ✅ Produit créé: {product.name}")
        
        # 2. Créer le bon de commande
        purchase_order = env['purchase.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': chantier.id,
            'lot_ids': [(6, 0, [lot.id])],
            'state': 'purchase',  # Directement confirmé
            'date_order': datetime.now(),
            'notes': f'Bon de commande de test pour lot {lot.name}'
        })
        print(f"   ✅ Bon de commande créé: {purchase_order.name}")
        
        # 3. Créer une ligne de commande
        line = env['purchase.order.line'].create({
            'order_id': purchase_order.id,
            'product_id': product.id,
            'name': f'Produit Test {lot.name} - 10 unités',
            'product_qty': 10,
            'price_unit': 100.0,
            'lot_id': lot.id,
            'product_uom': product.uom_po_id.id
        })
        print(f"   ✅ Ligne de commande créée: {line.name}")
        
        # 4. Vérifier que tout est bien lié
        print(f"\n🔍 === VÉRIFICATION DES LIENS ===")
        print(f"   - Bon de commande: {purchase_order.name}")
        print(f"   - Partenaire: {purchase_order.partner_id.name}")
        print(f"   - Chantier: {purchase_order.chantier_id.name}")
        print(f"   - État: {purchase_order.state}")
        print(f"   - Lots dans lot_ids: {[l.name for l in purchase_order.lot_ids]}")
        print(f"   - Lignes: {len(purchase_order.order_line)}")
        
        for line in purchase_order.order_line:
            print(f"     * Ligne: {line.name}")
            print(f"       - Lot: {line.lot_id.name if line.lot_id else 'Aucun'}")
            print(f"       - Produit: {line.product_id.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_recherche_lot_specifique(env, lot_name=None):
    """Test de recherche pour un lot spécifique."""
    print("🔍 === TEST RECHERCHE LOT SPÉCIFIQUE ===")
    
    # Si aucun nom de lot spécifié, prendre le premier disponible
    if not lot_name:
        lots = env['construction.lot'].search([])
        if not lots:
            print("❌ Aucun lot trouvé!")
            return False
        lot = lots[0]
        lot_name = lot.name
    else:
        lot = env['construction.lot'].search([('name', '=', lot_name)])
        if not lot:
            print(f"❌ Lot '{lot_name}' non trouvé!")
            return False
        lot = lot[0]
    
    print(f"🔍 Recherche pour lot: {lot.name} (ID: {lot.id})")
    
    # Recherche via lot_ids
    orders_via_lot_ids = env['purchase.order'].search([
        ('lot_ids', 'in', [lot.id])
    ])
    print(f"   - Bons de commande avec lot dans lot_ids: {len(orders_via_lot_ids)}")
    
    # Recherche via lignes
    lines_with_lot = env['purchase.order.line'].search([
        ('lot_id', '=', lot.id)
    ])
    orders_via_lines = lines_with_lot.mapped('order_id')
    print(f"   - Bons de commande avec lot dans lignes: {len(orders_via_lines)}")
    
    # Combiner
    all_orders = orders_via_lot_ids | orders_via_lines
    print(f"   - Total bons de commande liés au lot: {len(all_orders)}")
    
    for po in all_orders:
        print(f"     * {po.name} (ID: {po.id}): partenaire={po.partner_id.name}, état={po.state}")
    
    return len(all_orders) > 0

def forcer_creation_donnees_test(env):
    """Force la création de données de test complètes."""
    print("🔧 === CRÉATION FORCÉE DE DONNÉES DE TEST ===")
    
    try:
        from datetime import datetime
        
        # 1. Créer un chantier de test
        chantier = env['construction.chantier'].create({
            'name': 'Chantier Test Diagnostic',
            'client': env['res.partner'].create({
                'name': 'Client Test Diagnostic',
                'email': 'client.test@diagnostic.com'
            }).id,
            'address': '123 Rue Test, 33000 Bordeaux',
            'date_start_contract': datetime.now().date(),
            'date_end_contract': (datetime.now() + timedelta(days=90)).date(),
            'total_cost': 100000.0,
        })
        print(f"✅ Chantier créé: {chantier.name}")
        
        # 2. Créer un lot de test
        lot = env['construction.lot'].create({
            'name': 'Lot Test Diagnostic',
            'chantier_id': chantier.id,
            'price': 50000.0,
            'urssaf_code': '43.34Z - Travaux de peinture et vitrerie',
            'description': 'Lot de test pour diagnostic'
        })
        print(f"✅ Lot créé: {lot.name}")
        
        # 3. Créer un sous-traitant de test
        subcontractor = env['res.partner'].create({
            'name': 'Sous-traitant Test Diagnostic',
            'email': 'sous-traitant.test@diagnostic.com',
            'supplier_rank': 1,
            'contact_type': 'sous_traitant'
        })
        print(f"✅ Sous-traitant créé: {subcontractor.name}")
        
        # 4. Créer un produit de test
        product = env['product.product'].create({
            'name': 'Produit Test Diagnostic',
            'type': 'product',
            'list_price': 100.0,
            'standard_price': 80.0
        })
        print(f"✅ Produit créé: {product.name}")
        
        # 5. Créer un bon de commande de test
        purchase_order = env['purchase.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': chantier.id,
            'lot_ids': [(6, 0, [lot.id])],
            'state': 'purchase',
            'date_order': datetime.now(),
            'notes': 'Bon de commande de test pour diagnostic'
        })
        print(f"✅ Bon de commande créé: {purchase_order.name}")
        
        # 6. Créer une ligne de commande
        line = env['purchase.order.line'].create({
            'order_id': purchase_order.id,
            'product_id': product.id,
            'name': 'Produit Test Diagnostic - 10 unités',
            'product_qty': 10,
            'price_unit': 100.0,
            'lot_id': lot.id,
            'product_uom': product.uom_po_id.id
        })
        print(f"✅ Ligne de commande créée")
        
        # 7. Créer une tâche de planning
        task = env['construction.planning.task'].create({
            'name': 'Tâche Test Diagnostic',
            'chantier_id': chantier.id,
            'lot_id': lot.id,
            'subcontractor_id': subcontractor.id,
            'date_start': datetime.now() + timedelta(days=1),
            'date_stop': datetime.now() + timedelta(days=10),
            'state': 'planned'
        })
        print(f"✅ Tâche de planning créée: {task.name}")
        
        print(f"\n🎉 === DONNÉES DE TEST CRÉÉES AVEC SUCCÈS ===")
        print(f"   - Chantier: {chantier.name} (ID: {chantier.id})")
        print(f"   - Lot: {lot.name} (ID: {lot.id})")
        print(f"   - Sous-traitant: {subcontractor.name} (ID: {subcontractor.id})")
        print(f"   - Bon de commande: {purchase_order.name} (ID: {purchase_order.id})")
        print(f"   - Tâche: {task.name} (ID: {task.id})")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création des données de test: {e}")
        import traceback
        traceback.print_exc()
        return False

# Instructions d'utilisation:
# 1. Ouvrir la console Odoo (Settings > Technical > Database Structure > Models)
# 2. Aller dans le modèle 'construction.chantier'
# 3. Exécuter: diagnostic_complet(env)
# 4. Ou: test_recherche_lot_specifique(env, "Nom du lot")
# 5. Ou: forcer_creation_donnees_test(env)
