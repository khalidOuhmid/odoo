# -*- coding: utf-8 -*-
"""
Migration script pour ajouter le champ 'type' aux tâches de planning existantes
et créer les séquences pour les noms automatiques
"""

def migrate(cr, version):
    """Ajoute le champ 'type' avec la valeur par défaut 'task' aux enregistrements existants"""
    
    # Ajouter le champ 'type' avec la valeur par défaut 'task'
    cr.execute("""
        ALTER TABLE construction_planning_task 
        ADD COLUMN IF NOT EXISTS type VARCHAR DEFAULT 'task'
    """)
    
    # Mettre à jour tous les enregistrements existants qui n'ont pas de type
    cr.execute("""
        UPDATE construction_planning_task 
        SET type = 'task' 
        WHERE type IS NULL OR type = ''
    """)
    
    # Ajouter le champ subcontractor_type aux partenaires
    # Vérifier d'abord si la colonne existe
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'res_partner' AND column_name = 'subcontractor_type'
    """)
    
    if not cr.fetchone():
        # La colonne n'existe pas, l'ajouter
        cr.execute("""
            ALTER TABLE res_partner 
            ADD COLUMN subcontractor_type VARCHAR DEFAULT 'external'
        """)
        print("✅ Colonne subcontractor_type ajoutée à res_partner")
    else:
        print("ℹ️ Colonne subcontractor_type existe déjà")
    
    # Mettre à jour les partenaires existants
    # Par défaut, tous les sous-traitants existants sont considérés comme externes
    cr.execute("""
        UPDATE res_partner 
        SET subcontractor_type = 'external' 
        WHERE subcontractor_type IS NULL OR subcontractor_type = ''
    """)
    
    # Nettoyer les anciennes contraintes de clé étrangère problématiques
    try:
        # Supprimer les contraintes qui référencent sale_order_id
        cr.execute("""
            SELECT conname 
            FROM pg_constraint 
            WHERE conname LIKE '%sale_order_id%' 
            AND contype = 'f'
        """)
        
        constraints_to_drop = cr.fetchall()
        for (constraint_name,) in constraints_to_drop:
            cr.execute(f"ALTER TABLE sale_order DROP CONSTRAINT IF EXISTS {constraint_name}")
            print(f"🗑️ Contrainte supprimée : {constraint_name}")
            
    except Exception as e:
        print(f"⚠️ Erreur lors du nettoyage des contraintes : {e}")
    
    # Supprimer les anciennes tables de relation si elles existent
    old_tables = [
        'sale_order_lot_rel',
        'sale_order_lot_selection_rel',
        'sale_order_construction_lot_rel'
    ]
    
    for table_name in old_tables:
        try:
            cr.execute(f"DROP TABLE IF EXISTS {table_name}")
            print(f"🗑️ Table supprimée : {table_name}")
        except Exception as e:
            print(f"⚠️ Erreur lors de la suppression de {table_name} : {e}")
    
    # Créer les séquences pour les noms automatiques
    sequences_data = [
        {
            'name': 'Séquence Devis Construction',
            'code': 'construction.devis.sequence',
            'prefix': '',
            'padding': 4,
            'number_next': 1,
            'number_increment': 1,
        },
        {
            'name': 'Séquence Bon de Commande Construction',
            'code': 'construction.purchase.order.sequence',
            'prefix': '',
            'padding': 4,
            'number_next': 1,
            'number_increment': 1,
        }
    ]
    
    for seq_data in sequences_data:
        # Vérifier si la séquence existe déjà
        cr.execute("""
            SELECT id FROM ir_sequence 
            WHERE code = %s
        """, (seq_data['code'],))
        
        if not cr.fetchone():
            # Créer la séquence
            cr.execute("""
                INSERT INTO ir_sequence (name, code, prefix, padding, number_next, number_increment, active)
                VALUES (%s, %s, %s, %s, %s, %s, true)
            """, (
                seq_data['name'],
                seq_data['code'],
                seq_data['prefix'],
                seq_data['padding'],
                seq_data['number_next'],
                seq_data['number_increment']
            ))
    
    print("✅ Migration terminée : champ 'type' ajouté aux tâches de planning, séquences créées et champ subcontractor_type ajouté")