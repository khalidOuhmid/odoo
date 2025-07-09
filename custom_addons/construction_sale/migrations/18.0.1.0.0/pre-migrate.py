#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration script pour construction_sale 18.0.1.0.0
Nettoie les anciennes tables et relations problématiques
"""


def migrate(cr, version):
    """
    Nettoie les anciennes tables et relations qui causent des conflits
    """
    # Liste des anciennes tables à supprimer
    old_tables = [
        'purchase_order_lot',
        'purchase_order_lot_line',
        'auto_split_confirmation_wizard',
        'auto_split_preview_line',
        'split_quote_wizard',
        'split_lot_line',
        'construction_product_wizard',
        'construction_product_line',
        'construction_quick_product_wizard',
        'quote_builder_wizard',
        'product_selection_line',
        'import_email_wizard',
        'sale_order_lot_rel',  # Ancienne table de relation
        'product_lot_rel',     # Ancienne table de relation
    ]
    
    # Supprimer les tables si elles existent
    for table in old_tables:
        cr.execute(f"""
            DROP TABLE IF EXISTS {table} CASCADE;
        """)
    
    # Supprimer les anciennes contraintes de clés étrangères problématiques
    cr.execute("""
        DO $$
        DECLARE
            constraint_record RECORD;
        BEGIN
            FOR constraint_record IN 
                SELECT conname, conrelid::regclass AS table_name
                FROM pg_constraint 
                WHERE conname LIKE '%sale_order_id%'
                   OR conname LIKE '%lot_id%'
                   OR conname LIKE '%purchase_order%'
            LOOP
                BEGIN
                    EXECUTE 'ALTER TABLE ' || constraint_record.table_name || 
                           ' DROP CONSTRAINT IF EXISTS ' || constraint_record.conname;
                EXCEPTION
                    WHEN OTHERS THEN
                        -- Ignorer les erreurs si la contrainte n'existe pas
                        NULL;
                END;
            END LOOP;
        END $$;
    """)
    
    # Nettoyer les enregistrements dans ir_model_data pour les anciens modèles
    cr.execute("""
        DELETE FROM ir_model_data 
        WHERE model IN (
            'purchase.order.lot',
            'purchase.order.lot.line',
            'auto.split.confirmation.wizard',
            'auto.split.preview.line',
            'split.quote.wizard',
            'split.lot.line',
            'construction.product.wizard',
            'construction.product.line',
            'construction.quick.product.wizard',
            'quote.builder.wizard',
            'product.selection.line',
            'import.email.wizard'
        );
    """)
    
    # Nettoyer les anciens modèles dans ir_model
    cr.execute("""
        DELETE FROM ir_model 
        WHERE model IN (
            'purchase.order.lot',
            'purchase.order.lot.line',
            'auto.split.confirmation.wizard',
            'auto.split.preview.line',
            'split.quote.wizard',
            'split.lot.line',
            'construction.product.wizard',
            'construction.product.line',
            'construction.quick.product.wizard',
            'quote.builder.wizard',
            'product.selection.line',
            'import.email.wizard'
        );
    """)
    
    print("Migration terminée : anciennes tables et contraintes supprimées") 