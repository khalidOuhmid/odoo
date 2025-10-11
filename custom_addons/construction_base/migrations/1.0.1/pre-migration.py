# -*- coding: utf-8 -*-

def migrate(cr, version):
    """
    Pré-migration pour s'assurer que les champs de dates internes existent
    """
    # Vérifier si les colonnes existent déjà
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'construction_chantier' 
        AND column_name IN ('date_start_internal', 'date_end_internal')
    """)
    
    existing_columns = [row[0] for row in cr.fetchall()]
    
    # Ajouter les colonnes manquantes
    if 'date_start_internal' not in existing_columns:
        cr.execute("""
            ALTER TABLE construction_chantier 
            ADD COLUMN date_start_internal date
        """)
        print("Colonne date_start_internal ajoutée")
    
    if 'date_end_internal' not in existing_columns:
        cr.execute("""
            ALTER TABLE construction_chantier 
            ADD COLUMN date_end_internal date
        """)
        print("Colonne date_end_internal ajoutée")
    
    # Vérifier si la colonne duration_actual existe
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'construction_chantier' 
        AND column_name = 'duration_actual'
    """)
    
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE construction_chantier 
            ADD COLUMN duration_actual integer DEFAULT 0
        """)
        print("Colonne duration_actual ajoutée")
