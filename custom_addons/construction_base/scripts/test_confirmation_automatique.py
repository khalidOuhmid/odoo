# -*- coding: utf-8 -*-
"""
Script de test pour la confirmation automatique des bons de commande
À exécuter dans la console Odoo pour tester
"""

def test_confirmation_automatique(env):
    """Teste la confirmation automatique des bons de commande."""
    print("🔧 === TEST CONFIRMATION AUTOMATIQUE ===")
    
    # 1. Vérifier les bons de commande existants
    all_orders = env['purchase.order'].search([])
    print(f"🛒 Total bons de commande: {len(all_orders)}")
    
    draft_orders = env['purchase.order'].search([('state', '=', 'draft')])
    purchase_orders = env['purchase.order'].search([('state', '=', 'purchase')])
    sent_orders = env['purchase.order'].search([('state', '=', 'sent')])
    
    print(f"   - Brouillons: {len(draft_orders)}")
    print(f"   - Confirmés: {len(purchase_orders)}")
    print(f"   - Envoyés: {len(sent_orders)}")
    
    # 2. Afficher les détails des brouillons
    if draft_orders:
        print(f"\n📋 Bons de commande en brouillon:")
        for po in draft_orders:
            print(f"   - {po.name}: partenaire={po.partner_id.name}, lots={[l.name for l in po.lot_ids]}")
    
    # 3. Simuler la confirmation automatique
    print(f"\n🔧 === SIMULATION CONFIRMATION AUTOMATIQUE ===")
    
    # Prendre un chantier de test
    chantiers = env['construction.chantier'].search([])
    if not chantiers:
        print("❌ Aucun chantier trouvé!")
        return False
    
    chantier = chantiers[0]
    print(f"✅ Chantier de test: {chantier.name}")
    
    # Créer un contrat temporaire pour tester
    lots = chantier.lots_ids
    if not lots:
        print("❌ Aucun lot trouvé dans le chantier!")
        return False
    
    lot = lots[0]
    print(f"✅ Lot de test: {lot.name}")
    
    # Simuler la méthode de confirmation
    confirmed_count = simuler_confirmation_automatique(env, lot)
    
    print(f"\n🎉 === RÉSULTAT ===")
    print(f"   - Bons de commande confirmés: {confirmed_count}")
    
    # 4. Vérifier les nouveaux états
    draft_orders_apres = env['purchase.order'].search([('state', '=', 'draft')])
    purchase_orders_apres = env['purchase.order'].search([('state', '=', 'purchase')])
    
    print(f"   - Brouillons après: {len(draft_orders_apres)}")
    print(f"   - Confirmés après: {len(purchase_orders_apres)}")
    
    return True

def simuler_confirmation_automatique(env, lot):
    """Simule la confirmation automatique pour un lot."""
    confirmed_count = 0
    
    print(f"🔍 Recherche des bons de commande pour lot {lot.name}:")
    
    # Rechercher tous les bons de commande liés à ce lot
    purchase_orders = env['purchase.order'].search([
        ('lot_ids', 'in', [lot.id])
    ])
    
    # Ajouter ceux liés via les lignes de commande
    lines_with_lot = env['purchase.order.line'].search([
        ('lot_id', '=', lot.id)
    ])
    orders_via_lines = lines_with_lot.mapped('order_id')
    
    all_orders = purchase_orders | orders_via_lines
    
    print(f"   - Total bons de commande liés au lot: {len(all_orders)}")
    
    for order in all_orders:
        print(f"   - {order.name}: état actuel = {order.state}")
        
        if order.state == 'draft':
            try:
                order.button_confirm()
                confirmed_count += 1
                print(f"     ✅ Confirmé: {order.name}")
            except Exception as e:
                print(f"     ❌ Erreur confirmation {order.name}: {e}")
        elif order.state == 'sent':
            try:
                order.button_confirm()
                confirmed_count += 1
                print(f"     ✅ Confirmé: {order.name}")
            except Exception as e:
                print(f"     ❌ Erreur confirmation {order.name}: {e}")
        else:
            print(f"     ℹ️ Déjà confirmé: {order.name}")
    
    return confirmed_count

def creer_bon_commande_brouillon(env):
    """Crée un bon de commande en brouillon pour tester."""
    print("🔧 === CRÉATION BON DE COMMANDE BROUILLON ===")
    
    try:
        from datetime import datetime
        
        # Prendre un chantier et un lot
        chantiers = env['construction.chantier'].search([])
        if not chantiers:
            print("❌ Aucun chantier trouvé!")
            return False
        
        chantier = chantiers[0]
        lots = chantier.lots_ids
        if not lots:
            print("❌ Aucun lot trouvé!")
            return False
        
        lot = lots[0]
        
        # Prendre un sous-traitant
        subcontractors = env['res.partner'].search([
            ('supplier_rank', '>', 0)
        ])
        if not subcontractors:
            print("❌ Aucun sous-traitant trouvé!")
            return False
        
        subcontractor = subcontractors[0]
        
        # Créer un produit
        product = env['product.product'].create({
            'name': f'Produit Test Brouillon {lot.name}',
            'type': 'product',
            'list_price': 100.0
        })
        
        # Créer le bon de commande en brouillon
        purchase_order = env['purchase.order'].create({
            'partner_id': subcontractor.id,
            'chantier_id': chantier.id,
            'lot_ids': [(6, 0, [lot.id])],
            'state': 'draft',  # En brouillon
            'date_order': datetime.now(),
            'notes': 'Bon de commande de test en brouillon'
        })
        
        # Créer une ligne
        env['purchase.order.line'].create({
            'order_id': purchase_order.id,
            'product_id': product.id,
            'name': f'Produit Test Brouillon {lot.name} - 5 unités',
            'product_qty': 5,
            'price_unit': 100.0,
            'lot_id': lot.id
        })
        
        print(f"✅ Bon de commande créé en brouillon: {purchase_order.name}")
        print(f"   - Partenaire: {subcontractor.name}")
        print(f"   - Lot: {lot.name}")
        print(f"   - État: {purchase_order.state}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur création: {e}")
        return False

def verifier_etats_bons_commande(env):
    """Vérifie les états de tous les bons de commande."""
    print("🔍 === VÉRIFICATION ÉTATS BONS DE COMMANDE ===")
    
    all_orders = env['purchase.order'].search([])
    
    states_count = {}
    for order in all_orders:
        state = order.state
        if state not in states_count:
            states_count[state] = 0
        states_count[state] += 1
    
    print(f"📊 Répartition par état:")
    for state, count in states_count.items():
        print(f"   - {state}: {count}")
    
    # Afficher les détails des brouillons
    draft_orders = env['purchase.order'].search([('state', '=', 'draft')])
    if draft_orders:
        print(f"\n📋 Bons de commande en brouillon:")
        for po in draft_orders:
            print(f"   - {po.name}: partenaire={po.partner_id.name}, lots={[l.name for l in po.lot_ids]}")

# Instructions d'utilisation:
# 1. Ouvrir la console Odoo (Settings > Technical > Database Structure > Models)
# 2. Aller dans le modèle 'construction.chantier'
# 3. Exécuter: test_confirmation_automatique(env)
# 4. Ou: creer_bon_commande_brouillon(env) pour créer un test
# 5. Ou: verifier_etats_bons_commande(env) pour vérifier les états
