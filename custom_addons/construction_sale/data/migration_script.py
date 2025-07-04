# -*- coding: utf-8 -*-
"""
Script de migration pour corriger les problèmes de données
Construction Sale - Version 2.0
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(env):
    """
    Migration des données pour éviter les conflits
    """
    _logger.info("🚀 Début de la migration Construction Sale 2.0")
    
    try:
        # 1. Nettoyer les modèles Many2many conflictuels
        _clean_many2many_conflicts(env)
        
        # 2. Vérifier les catégories de produits
        _ensure_product_categories(env)
        
        # 3. Mettre à jour les droits d'accès
        _update_access_rights(env)
        
        _logger.info("✅ Migration Construction Sale 2.0 terminée avec succès")
        
    except Exception as e:
        _logger.error(f"❌ Erreur lors de la migration: {str(e)}")
        raise


def _clean_many2many_conflicts(env):
    """Nettoie les conflits de tables Many2many"""
    _logger.info("🧹 Nettoyage des conflits Many2many...")
    
    # Supprimer les tables conflictuelles si elles existent
    conflicting_tables = [
        'blg_wizard_product_rel',
        'blg_wizard_selected_product_rel', 
        'blg_wizard_available_product_rel',
        'blg_wizard_products_rel',
        'blg_wizard_chantier_lot_rel',
        'blg_lot_type_product_rel',
        'blg_create_quote_wizard_lot_rel'
    ]
    
    for table in conflicting_tables:
        try:
            env.cr.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            _logger.info(f"  ✓ Table {table} supprimée")
        except Exception as e:
            _logger.warning(f"  ⚠️ Impossible de supprimer {table}: {str(e)}")


def _ensure_product_categories(env):
    """S'assure que les catégories de produits existent"""
    _logger.info("📂 Vérification des catégories de produits...")
    
    # Catégorie principale Construction
    main_category = env['product.category'].search([('name', '=', 'Construction')], limit=1)
    if not main_category:
        main_category = env['product.category'].create({
            'name': 'Construction',
            'property_cost_method': 'standard',
        })
        _logger.info("  ✓ Catégorie 'Construction' créée")
    
    # Sous-catégories
    subcategories = [
        ('Démolition', 'DEM'),
        ('Maçonnerie', 'MAC'),
        ('Plomberie CVC', 'CVC'),
        ('Électricité', 'ELE'),
        ('Menuiserie extérieure', 'MEX'),
        ('Menuiserie intérieure', 'MIN'),
        ('Peinture & finition', 'PEI'),
        ('Sol souple et parquet', 'SOL'),
        ('Carrelage & faïence', 'CAR'),
    ]
    
    for name, code in subcategories:
        category = env['product.category'].search([
            ('name', '=', name),
            ('parent_id', '=', main_category.id)
        ], limit=1)
        
        if not category:
            env['product.category'].create({
                'name': name,
                'parent_id': main_category.id,
                'property_cost_method': 'standard',
            })
            _logger.info(f"  ✓ Sous-catégorie '{name}' créée")


def _update_access_rights(env):
    """Met à jour les droits d'accès"""
    _logger.info("🔐 Mise à jour des droits d'accès...")
    
    # S'assurer que les groupes de base existent
    group_user = env.ref('base.group_user', raise_if_not_found=False)
    if not group_user:
        _logger.warning("  ⚠️ Groupe 'base.group_user' non trouvé")
        return
    
    # Modèles à vérifier
    models_to_check = [
        'construction.product.wizard',
        'construction.product.line', 
        'construction.quick.product.wizard',
        'blg.quick.product.wizard',
        'blg.product.selection.wizard',
        'blg.create.quote.wizard',
        'blg.lot.navigation.wizard',
        'blg.product.selection.line',
        'chantier',
        'blg.stage',
        'blg.chapter',
        'blg.lot.type'
    ]
    
    for model_name in models_to_check:
        try:
            # Vérifier si le modèle existe
            model = env.get(model_name)
            if model:
                _logger.info(f"  ✓ Modèle '{model_name}' disponible")
            else:
                _logger.warning(f"  ⚠️ Modèle '{model_name}' non trouvé")
        except Exception as e:
            _logger.warning(f"  ⚠️ Erreur avec modèle '{model_name}': {str(e)}")


# Point d'entrée pour l'appel depuis Odoo
def migrate_construction_sale(env):
    """Point d'entrée principal pour la migration"""
    migrate(env) 