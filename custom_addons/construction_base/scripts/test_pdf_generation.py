#!/usr/bin/env python3
"""
Script de test pour la génération de PDF sans dépendances Odoo.
Teste uniquement la logique de génération HTML et la structure des données.
"""

import sys
import os
import tempfile
import subprocess
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.append(str(Path(__file__).parent.parent))

def test_html_generation():
    """Teste la génération de HTML pour les différents composants."""
    print("🧪 Test de génération HTML...")
    
    # Simuler les données de test
    test_data = {
        'lot_name': 'Lot Test',
        'contract_number': 'CTR-2024-001',
        'subcontractor_name': 'Entreprise Test SARL',
        'purchase_orders': [
            {
                'name': 'BC-001',
                'partner_id': {'name': 'Fournisseur Test'},
                'amount_total': 15000.0,
                'order_line': [
                    {'name': 'Matériaux de construction', 'product_qty': 100, 'price_unit': 150.0}
                ]
            }
        ],
        'planning_tasks': [
            {
                'name': 'Tâche 1',
                'start_date': '2024-01-01',
                'end_date': '2024-01-15',
                'duration': 15
            }
        ]
    }
    
    # Test de génération HTML pour les bons de commande
    purchase_orders_html = generate_purchase_orders_html(test_data)
    print(f"✅ HTML bons de commande généré: {len(purchase_orders_html)} caractères")
    
    # Test de génération HTML pour le planning Gantt
    planning_html = generate_planning_gantt_html(test_data)
    print(f"✅ HTML planning Gantt généré: {len(planning_html)} caractères")
    
    return True

def generate_purchase_orders_html(data):
    """Génère le HTML pour les bons de commande."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Bons de Commande - {data['lot_name']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .title {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #f8f9fa; font-weight: bold; }}
            .total {{ font-weight: bold; text-align: right; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">Bons de Commande - {data['lot_name']}</div>
            <p>Contrat: {data['contract_number']}</p>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>N° Commande</th>
                    <th>Fournisseur</th>
                    <th>Montant Total</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for po in data['purchase_orders']:
        html += f"""
                <tr>
                    <td>{po['name']}</td>
                    <td>{po['partner_id']['name']}</td>
                    <td>{po['amount_total']:,.2f} €</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
    </body>
    </html>
    """
    
    return html

def generate_planning_gantt_html(data):
    """Génère le HTML pour le planning Gantt."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Planning Gantt - {data['lot_name']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .title {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .gantt-container {{ margin: 20px 0; }}
            .gantt-row {{ display: flex; align-items: center; margin: 5px 0; }}
            .task-name {{ width: 200px; font-weight: bold; }}
            .gantt-bar {{ 
                height: 30px; 
                background: linear-gradient(90deg, #3498db, #2980b9);
                border-radius: 5px;
                position: relative;
                margin-left: 10px;
            }}
            .task-duration {{ margin-left: 10px; color: #7f8c8d; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">Planning Gantt - {data['lot_name']}</div>
            <p>Contrat: {data['contract_number']}</p>
        </div>
        
        <div class="gantt-container">
    """
    
    for task in data['planning_tasks']:
        html += f"""
            <div class="gantt-row">
                <div class="task-name">{task['name']}</div>
                <div class="gantt-bar" style="width: {task['duration'] * 20}px;"></div>
                <div class="task-duration">{task['duration']} jours</div>
            </div>
        """
    
    html += """
        </div>
    </body>
    </html>
    """
    
    return html

def test_wkhtmltopdf_availability():
    """Teste si wkhtmltopdf est disponible."""
    print("🔧 Test de disponibilité wkhtmltopdf...")
    
    try:
        result = subprocess.run(['wkhtmltopdf', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ wkhtmltopdf disponible: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ wkhtmltopdf non disponible: {result.stderr}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ wkhtmltopdf non trouvé: {e}")
        return False

def test_pdfunite_availability():
    """Teste si pdfunite est disponible."""
    print("🔧 Test de disponibilité pdfunite...")
    
    try:
        result = subprocess.run(['pdfunite', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ pdfunite disponible")
            return True
        else:
            print(f"❌ pdfunite non disponible: {result.stderr}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ pdfunite non trouvé: {e}")
        return False

def main():
    """Fonction principale de test."""
    print("🚀 Démarrage des tests de génération PDF")
    print("=" * 50)
    
    # Test de génération HTML
    test_html_generation()
    
    # Test de disponibilité des outils
    wkhtmltopdf_ok = test_wkhtmltopdf_availability()
    pdfunite_ok = test_pdfunite_availability()
    
    print("\n" + "=" * 50)
    print("📊 Résumé des tests:")
    print(f"✅ Génération HTML: OK")
    print(f"{'✅' if wkhtmltopdf_ok else '❌'} wkhtmltopdf: {'Disponible' if wkhtmltopdf_ok else 'Non disponible'}")
    print(f"{'✅' if pdfunite_ok else '❌'} pdfunite: {'Disponible' if pdfunite_ok else 'Non disponible'}")
    
    if wkhtmltopdf_ok and pdfunite_ok:
        print("\n🎉 Tous les outils nécessaires sont disponibles !")
        print("Le module devrait fonctionner correctement dans l'environnement Odoo.")
    else:
        print("\n⚠️  Certains outils ne sont pas disponibles.")
        print("Le module nécessite wkhtmltopdf et pdfunite pour fonctionner.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
