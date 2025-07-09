-- Script de nettoyage manuel pour construction_sale
-- À exécuter directement dans PostgreSQL en cas de problème

-- 1. Supprimer toutes les contraintes de clés étrangères problématiques
DO $$
DECLARE
    constraint_record RECORD;
    table_record RECORD;
BEGIN
    -- Supprimer les contraintes contenant sale_order_id
    FOR constraint_record IN 
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint 
        WHERE conname LIKE '%sale_order_id%'
           OR conname LIKE '%purchase_order%'
           OR conname LIKE '%lot_rel%'
    LOOP
        BEGIN
            EXECUTE 'ALTER TABLE ' || constraint_record.table_name || 
                   ' DROP CONSTRAINT IF EXISTS ' || constraint_record.conname;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'Impossible de supprimer la contrainte %: %', constraint_record.conname, SQLERRM;
        END;
    END LOOP;
    
    -- Supprimer les index problématiques
    FOR constraint_record IN 
        SELECT indexname, tablename
        FROM pg_indexes 
        WHERE indexname LIKE '%sale_order_id%'
           OR indexname LIKE '%lot_rel%'
           OR indexname LIKE '%purchase_order%'
    LOOP
        BEGIN
            EXECUTE 'DROP INDEX IF EXISTS ' || constraint_record.indexname;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'Impossible de supprimer l''index %: %', constraint_record.indexname, SQLERRM;
        END;
    END LOOP;
END $$;

-- 2. Supprimer les anciennes tables problématiques
DROP TABLE IF EXISTS purchase_order_lot CASCADE;
DROP TABLE IF EXISTS purchase_order_lot_line CASCADE;
DROP TABLE IF EXISTS auto_split_confirmation_wizard CASCADE;
DROP TABLE IF EXISTS auto_split_preview_line CASCADE;
DROP TABLE IF EXISTS split_quote_wizard CASCADE;
DROP TABLE IF EXISTS split_lot_line CASCADE;
DROP TABLE IF EXISTS construction_product_wizard CASCADE;
DROP TABLE IF EXISTS construction_product_line CASCADE;
DROP TABLE IF EXISTS construction_quick_product_wizard CASCADE;
DROP TABLE IF EXISTS quote_builder_wizard CASCADE;
DROP TABLE IF EXISTS product_selection_line CASCADE;
DROP TABLE IF EXISTS import_email_wizard CASCADE;
DROP TABLE IF EXISTS sale_order_lot_rel CASCADE;
DROP TABLE IF EXISTS product_lot_rel CASCADE;

-- 3. Nettoyer ir_model_data des anciens enregistrements
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
)
OR name LIKE '%construction_sale%'
   AND model = 'ir.actions.act_window';

-- 4. Nettoyer ir_model des anciens modèles
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

-- 5. Nettoyer ir_model_fields des anciens champs
DELETE FROM ir_model_fields 
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

-- 6. Nettoyer ir_model_access des anciens droits
DELETE FROM ir_model_access 
WHERE model_id IN (
    SELECT id FROM ir_model WHERE model IN (
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
    )
);

-- 7. Nettoyer les vues obsolètes
DELETE FROM ir_ui_view 
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

-- 8. Nettoyer les actions obsolètes
DELETE FROM ir_actions_act_window 
WHERE res_model IN (
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

-- 9. Nettoyer les modules installés si nécessaire
UPDATE ir_module_module 
SET state = 'uninstalled' 
WHERE name = 'construction_sale' 
  AND state IN ('installed', 'to upgrade', 'to remove');

COMMIT;

-- Message de confirmation
SELECT 'Nettoyage terminé. Vous pouvez maintenant réinstaller le module construction_sale.' AS message; 