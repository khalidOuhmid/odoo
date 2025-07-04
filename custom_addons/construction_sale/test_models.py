# -*- coding: utf-8 -*-
"""
Script de test pour valider les modèles Construction Sale
"""

def test_models(env):
    """Test rapide des modèles principaux"""
    
    print("🧪 Test des modèles Construction Sale...")
    
    models_to_test = [
        'construction.product.wizard',
        'construction.product.line',
        'construction.quick.product.wizard',
        'sale.order',  # Extension
        'blg.quick.product.wizard',
        'blg.product.selection.wizard',
        'blg.product.selection.line',
        'chantier',
        'blg.stage',
        'blg.chapter',
        'blg.lot.type'
    ]
    
    results = {}
    
    for model_name in models_to_test:
        try:
            model = env[model_name]
            count = model.search_count([])
            results[model_name] = f"✅ OK ({count} enregistrements)"
        except Exception as e:
            results[model_name] = f"❌ ERREUR: {str(e)}"
    
    print("\n📊 Résultats des tests :")
    for model, result in results.items():
        print(f"  {model}: {result}")
    
    # Test de création d'un wizard
    try:
        print("\n🆕 Test de création d'un wizard...")
        wizard = env['construction.product.wizard'].create({
            'sale_order_id': 1,  # ID fictif pour test
        })
        print("  ✅ Wizard créé avec succès")
        wizard.unlink()
        print("  ✅ Wizard supprimé avec succès")
    except Exception as e:
        print(f"  ❌ Erreur création wizard: {str(e)}")
    
    print("\n🎉 Test terminé !")


if __name__ == '__main__':
    # Pour utilisation en shell Odoo :
    # exec(open('test_models.py').read())
    # test_models(env)
    pass 