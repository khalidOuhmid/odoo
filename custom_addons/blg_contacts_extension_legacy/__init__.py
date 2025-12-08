# -*- coding: utf-8 -*-

from . import controllers
from . import models


# Support both new (env) and old (cr, registry) signatures
def _post_init_migrate_lots(env_or_cr, registry=None):
    """
    Post-installation hook to migrate lot data.

    Compatible avec les deux signatures :
    1. Odoo 18 : (_post_init_hook(env))
    2. Anciennes versions : (_post_init_hook(cr, registry))
    """
    # Déterminer le curseur de base de données selon la signature utilisée
    if registry is None:  # Nouvelle signature → env uniquement
        env = env_or_cr
        cr = env.cr
    else:  # Ancienne signature → cr, registry
        cr = env_or_cr
    
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        _logger.info("Starting lot data migration process...")
        
        # Check if we have the old table
        cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'blg_contacts_extension_lot' 
                AND table_schema = 'public'
            )
        """)
        
        has_old_table = cr.fetchone()[0] if cr.rowcount > 0 else False
        
        # Check if we have the new lot table
        cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'lot' 
                AND table_schema = 'public'
            )
        """)
        
        has_new_table = cr.fetchone()[0] if cr.rowcount > 0 else False
        
        if has_old_table and has_new_table:
            _logger.info("Both old and new lot tables found, proceeding with migration...")
            
            # First, ensure we don't create duplicates
            cr.execute("""
                INSERT INTO lot (name, code, color, create_date, write_date)
                SELECT 
                    old_lot.name, 
                    old_lot.code, 
                    0 as color,
                    COALESCE(old_lot.create_date, NOW()),
                    COALESCE(old_lot.write_date, NOW())
                FROM blg_contacts_extension_lot old_lot
                WHERE NOT EXISTS (
                    SELECT 1 FROM lot 
                    WHERE lot.name = old_lot.name 
                    OR (lot.code = old_lot.code AND lot.code IS NOT NULL)
                )
            """)
            
            migrated_count = cr.rowcount
            _logger.info(f"Migrated {migrated_count} lot records to new structure")
            
            # Update partner relationships if the relation table exists
            cr.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'partner_lot_rel' 
                    AND table_schema = 'public'
                )
            """)
            
            has_relation_table = cr.fetchone()[0] if cr.rowcount > 0 else False
            
            if has_relation_table:
                cr.execute("""
                    UPDATE partner_lot_rel 
                    SET lot_id = (
                        SELECT lot.id FROM lot 
                        JOIN blg_contacts_extension_lot old_lot ON lot.name = old_lot.name
                        WHERE old_lot.id = partner_lot_rel.lot_id
                    )
                    WHERE EXISTS (
                        SELECT 1 FROM blg_contacts_extension_lot 
                        WHERE id = partner_lot_rel.lot_id
                    )
                    AND EXISTS (
                        SELECT 1 FROM lot 
                        JOIN blg_contacts_extension_lot old_lot ON lot.name = old_lot.name
                        WHERE old_lot.id = partner_lot_rel.lot_id
                    )
                """)
                
                updated_relations = cr.rowcount
                _logger.info(f"Updated {updated_relations} partner-lot relationships")
            
            _logger.info("Lot data migration completed successfully")
            
        elif has_old_table:
            _logger.warning("Old lot table found but new lot table doesn't exist. Migration skipped.")
        else:
            _logger.info("No old lot data found, migration not needed")
            
    except Exception as e:
        _logger.warning("Lot data migration failed: %s", str(e))
        _logger.info("This is normal for new installations or if migration was already completed")
