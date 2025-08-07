# -*- coding: utf-8 -*-
"""
Service de génération de contrats -
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
import base64
from datetime import datetime

from odoo.tools import file_path

_logger = logging.getLogger(__name__)


class ContractService(models.AbstractModel):
    _name = 'construction.contract.service'
    _description = 'Service de génération de contrats'

    def generate_contract(self, chantier, subcontractor, lot_ids, contract_data):
        """Génère un contrat de sous-traitance complet."""
        if not all([chantier, subcontractor, lot_ids]):
            raise ValidationError(_("Données manquantes pour la génération du contrat."))

        contract_vals = self._prepare_contract_vals(chantier, subcontractor, lot_ids, contract_data)
        contract = self.env['construction.subcontractor.contract'].create(contract_vals)

        pdf_content = self._generate_pdf_with_full_template(contract)

        access_token = contract._generate_access_token()
        portal_url = self._create_portal_link(contract, access_token)

        contract.write({
            'contract_pdf': base64.b64encode(pdf_content),
            'filename': f"Contrat_{subcontractor.name}_{datetime.now().strftime('%Y%m%d')}.pdf",
            'portal_url': portal_url,
            'access_token': access_token
        })

        return contract

    def generate_preview_html(self, chantier, subcontractor, lot_ids, contract_data):
        """Génère l'aperçu HTML complet avec annexes et signatures."""
        temp_contract = self._create_temp_contract_object(chantier, subcontractor, lot_ids, contract_data)
        
        # Récupérer les images BLG en base64
        blg_images = self._get_blg_images_base64()
        
        # Générer le contrat principal
        contract_html = self.env['ir.qweb']._render('construction_base.contrat_sous_traitance_template', {
            'docs': [temp_contract],
            'env': self.env,
            'context': self.env.context,
            'company': temp_contract.company_id,
            'fields': self.env['ir.fields.converter'],
            'blg_logo': blg_images['logo'],
            'blg_signature': blg_images['signature'],
        })
        
        # Générer les annexes disponibles
        annexes_html = self._generate_annexes_html(temp_contract, blg_images)
        
        # Générer la page de signatures de preview (sans signature sous-traitant)
        signatures_html = self._generate_preview_signatures_page(temp_contract, blg_images)
        
        # Utiliser le template existant pour preview
        html_body = self.env['ir.qweb']._render('construction_base.contrat_sous_traitance_template', {
            'docs': [temp_contract],
            'env': self.env,
            'context': self.env.context,
            'company': temp_contract.company_id,
            'fields': self.env['ir.fields.converter'],
            'blg_logo': blg_images['logo'],
            'blg_signature': blg_images['signature'],
        })
        
        # Entourer dans un HTML complet pour le preview avec headers et footers
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Aperçu Contrat de sous-traitance</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #2c3e50;
            background-color: #ffffff;
        }}
        .page {{
            min-height: 800px;
            max-width: 800px;
            margin: 0 auto;
        }}
        
        /* ===== HIÉRARCHIE DES TITRES ===== */
        h1 {{
            font-size: 28px;
            color: #20B2AA;
            text-align: center;
            margin: 30px 0 25px 0;
            padding: 15px 0;
            border-top: 3px solid #20B2AA;
            border-bottom: 3px solid #20B2AA;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        
        h2 {{
            font-size: 20px;
            color: #1a7a7a;
            margin: 35px 0 20px 0;
            padding: 12px 0 8px 0;
            border-bottom: 2px solid #20B2AA;
            font-weight: 600;
        }}
        h2::before {{
            content: ">";
            color: #20B2AA;
            margin-right: 10px;
            font-size: 16px;
        }}
        
        h3 {{
            font-size: 16px;
            color: #20B2AA;
            margin: 25px 0 15px 0;
            padding: 8px 0 5px 0;
            border-bottom: 1px solid #20B2AA;
            font-weight: 600;
        }}
        h3::before {{
            content: "-";
            color: #20B2AA;
            margin-right: 8px;
            font-size: 12px;
        }}
        
        /* ===== TABLEAUX ===== */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        th {{
            background: linear-gradient(135deg, #20B2AA 0%, #1a9999 100%);
            color: white;
            font-weight: 600;
            padding: 15px 12px;
            text-align: left;
            font-size: 13px;
            letter-spacing: 0.5px;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: top;
        }}
        
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        
        p {{
            margin: 12px 0;
            line-height: 1.6;
            text-align: justify;
        }}
        
        .highlight-box {{
            background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
            border: 2px solid #20B2AA;
            border-radius: 10px;
            padding: 25px;
            margin: 25px 0;
            text-align: center;
            box-shadow: 0 4px 12px rgba(32, 178, 170, 0.1);
        }}
        
        /* Styles pour headers et footers */
        .header-container {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10px;
            border-bottom: 1px solid #333;
            padding-bottom: 5px;
        }}
        .header-logo {{
            height: 50px;
            max-width: 100%;
        }}
        .header-title {{
            color: #333;
            font-size: 22px;
            font-weight: bold;
            margin: 0;
        }}
        .header-subtitle {{
            color: #666;
            margin: 5px 0 0 0;
            font-size: 12px;
        }}
        .footer-container {{
            width: 100%;
            text-align: center;
            padding: 5px 0;
            font-size: 10px;
            color: #666;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""
        return html_content

    def _prepare_contract_vals(self, chantier, subcontractor, lot_ids, contract_data):
        """Prépare les valeurs pour créer le contrat."""
        # Préparer le code URSSAF avec description complète
        urssaf_code = contract_data.get('urssaf_code', '43.34Z')
        urssaf_descriptions = {
            '41.20Z': '41.20Z - Construction de bâtiments résidentiels et non résidentiels',
            '42.11Z': '42.11Z - Construction de routes et autoroutes',
            '43.11Z': '43.11Z - Travaux de démolition',
            '43.12A': '43.12A - Travaux de terrassement courants et travaux préparatoires',
            '43.21A': '43.21A - Travaux d\'installation électrique dans tous locaux',
            '43.21B': '43.21B - Travaux d\'installation électrique sur la voie publique',
            '43.22A': '43.22A - Travaux d\'installation d\'eau et de gaz en tous locaux',
            '43.22B': '43.22B - Travaux d\'installation d\'équipements thermiques et de climatisation',
            '43.29A': '43.29A - Travaux d\'isolation',
            '43.31Z': '43.31Z - Travaux de plâtrerie',
            '43.32A': '43.32A - Travaux de menuiserie bois et PVC',
            '43.32B': '43.32B - Travaux de menuiserie métallique et serrurerie',
            '43.33Z': '43.33Z - Travaux de revêtement des sols et des murs',
            '43.34Z': '43.34Z - Travaux de peinture et vitrerie',
            '43.91A': '43.91A - Travaux de charpente',
            '43.91B': '43.91B - Travaux de couverture par éléments',
            '43.99A': '43.99A - Travaux d\'étanchéification',
            '43.99B': '43.99B - Travaux de montage de structures métalliques',
            '43.99C': '43.99C - Travaux de maçonnerie générale et gros œuvre de bâtiment',
            '43.99D': '43.99D - Autres travaux de construction spécialisés',
            '81.22Z': '81.22Z - Autres activités de nettoyage des bâtiments et nettoyage industriel',
            '81.30Z': '81.30Z - Services d\'aménagement paysager',
        }
        urssaf_code_full = urssaf_descriptions.get(urssaf_code, f"{urssaf_code} - Travaux de peinture et vitrerie")
        
        return {
            'name': f'Contrat {subcontractor.name} - {chantier.name}',
            'contract_number': self._generate_contract_number(),
            'chantier_id': chantier.id,
            'subcontractor_id': subcontractor.id,
            'lot_ids': [(6, 0, lot_ids.ids)],
            'start_date': contract_data.get('start_date', fields.Date.today()),
            'end_date': contract_data.get('end_date'),
            'total_amount': contract_data.get('total_amount', 0.0),
            'payment_terms': contract_data.get('payment_terms', '30_days'),
            'warranty_period': contract_data.get('warranty_period', 12),
            'insurance_required': contract_data.get('insurance_required', True),
            'notes': contract_data.get('notes', ''),
            'urssaf_code': urssaf_code_full,
            'state': 'draft',
            'company_id': self.env.company.id,
        }

    def _generate_contract_number(self):
        """Génère un numéro de contrat unique."""
        return self.env['ir.sequence'].next_by_code('construction.contract') or 'CT-DEFAULT'

    def _generate_pdf_with_full_template(self, contract):
        """Génère le PDF complet avec contrat + documents annexes (CCTP, plannings) + signatures."""
        try:
            # Récupérer les images BLG en base64
            blg_images = self._get_blg_images_base64()
            
            # Générer le contrat principal avec template QWeb
            contract_html = self.env['ir.qweb']._render('construction_base.contrat_sous_traitance_template', {
                'docs': [contract],
                'env': self.env,
                'context': self.env.context,
                'company': contract.company_id,
                'fields': self.env['ir.fields.converter'],
                'to_text': lambda b: b.decode('utf-8') if isinstance(b, bytes) else b,
                'blg_logo': blg_images['logo'],
                'blg_signature': blg_images['signature'],
            })
            
            # Préparer les données pour les annexes
            annexes_data = []
            for lot in contract.lot_ids:
                if hasattr(lot, 'document_cctp') and lot.document_cctp:
                    annexes_data.append({
                        'title': f"CCTP - {lot.name}",
                        'subtitle': "Cahier des Clauses Techniques Particulières",
                        'document_type': "CCTP",
                        'lot_name': lot.name,
                    })
                
                if hasattr(lot, 'document_general_planning') and lot.document_general_planning:
                    annexes_data.append({
                        'title': f"Planning Général - {lot.name}",
                        'subtitle': "Planning global du chantier",
                        'document_type': "Planning Général",
                        'lot_name': lot.name,
                    })
                
                if hasattr(lot, 'document_subcontractor_planning') and lot.document_subcontractor_planning:
                    annexes_data.append({
                        'title': f"Planning Sous-traitant - {lot.name}",
                        'subtitle': "Planning spécifique aux interventions",
                        'document_type': "Planning Sous-traitant",
                        'lot_name': lot.name,
                    })
            
            # Utiliser le template existant
            html_body = self.env['ir.qweb']._render('construction_base.contrat_sous_traitance_template', {
                'docs': [contract],
                'env': self.env,
                'context': self.env.context,
                'company': contract.company_id,
                'fields': self.env['ir.fields.converter'],
                'to_text': lambda b: b.decode('utf-8') if isinstance(b, bytes) else b,
                'blg_logo': blg_images['logo'],
                'blg_signature': blg_images['signature'],
            })
            
            # Générer les annexes HTML
            annexes_html = self._generate_annexes_html(contract, blg_images)
            
            # Générer la page de signatures finale
            signatures_html = self._generate_final_signatures_page(contract, blg_images)
            
            # Créer un HTML complet avec le contenu du template + annexes + signatures
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrat de sous-traitance</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #2c3e50;
            background-color: #ffffff;
        }}
        .page {{
            min-height: 800px;
            max-width: 800px;
            margin: 0 auto;
        }}
        
        /* ===== HIÉRARCHIE DES TITRES ===== */
        h1 {{
            font-size: 28px;
            color: #20B2AA;
            text-align: center;
            margin: 30px 0 25px 0;
            padding: 15px 0;
            border-top: 3px solid #20B2AA;
            border-bottom: 3px solid #20B2AA;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        
        h2 {{
            font-size: 20px;
            color: #1a7a7a;
            margin: 35px 0 20px 0;
            padding: 12px 0 8px 0;
            border-bottom: 2px solid #20B2AA;
            font-weight: 600;
            position: relative;
        }}
        h2::before {{
            content: ">";
            color: #20B2AA;
            margin-right: 10px;
            font-size: 16px;
        }}
        
        h3 {{
            font-size: 16px;
            color: #20B2AA;
            margin: 25px 0 15px 0;
            padding: 8px 0 5px 0;
            border-bottom: 1px solid #20B2AA;
            font-weight: 600;
        }}
        h3::before {{
            content: "-";
            color: #20B2AA;
            margin-right: 8px;
            font-size: 12px;
        }}
        
        .highlight-box {{
            background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
            border: 2px solid #20B2AA;
            border-radius: 10px;
            padding: 25px;
            margin: 25px 0;
            text-align: center;
            box-shadow: 0 4px 12px rgba(32, 178, 170, 0.1);
        }}
        
        /* ===== TABLEAUX ===== */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        th {{
            background: linear-gradient(135deg, #20B2AA 0%, #1a9999 100%);
            color: white;
            font-weight: 600;
            padding: 15px 12px;
            text-align: left;
            font-size: 13px;
            letter-spacing: 0.5px;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: top;
        }}
        
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        
        p {{
            margin: 12px 0;
            line-height: 1.6;
            text-align: justify;
        }}
    </style>
</head>
<body>
{html_body}
{annexes_html}
{signatures_html}
</body>
</html>"""
            
            # Nettoyer complètement le HTML pour éliminer toute référence externe SAUF les data URI
            import re
            # Supprimer toutes les images qui pourraient pointer vers des URLs (mais garder data:)
            html_content = re.sub(r'<img[^>]*src=["\'](?!data:)[^"\']*["\'][^>]*>', '', html_content)
            # Supprimer tous les liens href
            html_content = re.sub(r'href=["\'][^"\']*["\']', '', html_content)
            # Supprimer toute référence à des ressources externes dans CSS
            html_content = re.sub(r'url\((?!data:)[^)]*\)', '', html_content)
            
            # Générer les headers et footers directement dans le service
            header_html = self._generate_header_html(blg_images['logo'])
            footer_html = self._generate_footer_html()
            
            # Créer des fichiers temporaires pour header et footer
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as header_file:
                header_file.write(header_html)
                header_path = header_file.name
                
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as footer_file:
                footer_file.write(footer_html)
                footer_path = footer_file.name
            
            # Générer le PDF avec wkhtmltopdf et options optimisées pour le layout
            command = [
                'wkhtmltopdf',
                '--page-size', 'A4',
                '--orientation', 'Portrait',
                '--margin-top', '25mm',  # Espace pour le header
                '--margin-right', '8mm', 
                '--margin-bottom', '15mm',  # Espace pour le footer
                '--margin-left', '8mm',
                '--header-html', header_path,
                '--footer-html', footer_path,
                '--encoding', 'UTF-8',
                '--disable-external-links',
                '--disable-internal-links',
                '--disable-javascript',
                '--disable-plugins',
                '--enable-local-file-access',  # Pour les images data URI
                '--print-media-type',
                '--no-pdf-compression',  # Meilleure qualité
                '--image-quality', '100',  # Qualité maximale des images
                '--disable-smart-shrinking',  # Désactiver le shrinking automatique
                '--minimum-font-size', '8',
                '--zoom', '1.0',  # Zoom par défaut
                '--dpi', '96',  # DPI standard pour éviter les problèmes de scaling
                '--viewport-size', '1024x768',  # Taille de viewport fixe
                '--quiet',
                '-', '-'
            ]
            
            import subprocess
            try:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                pdf_content, error = process.communicate(input=html_content.encode('utf-8'))
                
                if process.returncode == 0:
                    return pdf_content
                else:
                    _logger.error(f"Erreur wkhtmltopdf: {error.decode()}")
                    raise Exception(f"wkhtmltopdf failed: {error.decode()}")
            finally:
                # Nettoyer les fichiers temporaires
                try:
                    if os.path.exists(header_path):
                        os.unlink(header_path)
                    if os.path.exists(footer_path):
                        os.unlink(footer_path)
                except Exception as e:
                    _logger.warning(f"Impossible de nettoyer les fichiers temporaires: {e}")
                
        except Exception as e:
            _logger.error(f"Erreur génération PDF: {e}")
            raise ValidationError(_("Impossible de générer le PDF du contrat. Erreur: %s") % str(e))

    def _create_temp_contract_object(self, chantier, subcontractor, lot_ids, contract_data):
        """Crée un objet temporaire pour la prévisualisation qui imite un vrai recordset."""
        
        class TempContract:
            def __init__(self, env, **data):
                self.env = env
                self.id = 0
                self._name = 'construction.subcontractor.contract'
                self.name = f"Aperçu Contrat {data['subcontractor'].name} - {data['chantier'].name}"
                self.contract_number = "PREVIEW-001"  # Numéro temporaire pour l'aperçu
                self.chantier_id = data['chantier']
                self.subcontractor_id = data['subcontractor']
                self.company_id = env.company
                self.lot_ids = data['lot_ids']
                self.total_amount = float(data.get('total_amount', 0.0))
                self.currency_id = env.company.currency_id
                self.start_date = data.get('start_date')
                self.create_date = fields.Datetime.now()
                self.signature_image = None  # Pas de signature pour l'aperçu
                
                # Champs de signature électronique (vides pour l'aperçu)
                self.signature_hash = None
                self.signature_timestamp = None
                self.signature_ip = None
                self.user_agent = None
                self.signature_certificate = None
                self.contract_hash_before_signature = None
                self.contract_hash_after_signature = None
                
                # Code URSSAF pour la prévisualisation
                urssaf_code = data.get('urssaf_code', '43.34Z')
                urssaf_descriptions = {
                    '41.20Z': '41.20Z - Construction de bâtiments résidentiels et non résidentiels',
                    '42.11Z': '42.11Z - Construction de routes et autoroutes',
                    '43.11Z': '43.11Z - Travaux de démolition',
                    '43.12A': '43.12A - Travaux de terrassement courants et travaux préparatoires',
                    '43.21A': '43.21A - Travaux d\'installation électrique dans tous locaux',
                    '43.21B': '43.21B - Travaux d\'installation électrique sur la voie publique',
                    '43.22A': '43.22A - Travaux d\'installation d\'eau et de gaz en tous locaux',
                    '43.22B': '43.22B - Travaux d\'installation d\'équipements thermiques et de climatisation',
                    '43.29A': '43.29A - Travaux d\'isolation',
                    '43.31Z': '43.31Z - Travaux de plâtrerie',
                    '43.32A': '43.32A - Travaux de menuiserie bois et PVC',
                    '43.32B': '43.32B - Travaux de menuiserie métallique et serrurerie',
                    '43.33Z': '43.33Z - Travaux de revêtement des sols et des murs',
                    '43.34Z': '43.34Z - Travaux de peinture et vitrerie',
                    '43.91A': '43.91A - Travaux de charpente',
                    '43.91B': '43.91B - Travaux de couverture par éléments',
                    '43.99A': '43.99A - Travaux d\'étanchéification',
                    '43.99B': '43.99B - Travaux de montage de structures métalliques',
                    '43.99C': '43.99C - Travaux de maçonnerie générale et gros œuvre de bâtiment',
                    '43.99D': '43.99D - Autres travaux de construction spécialisés',
                    '81.22Z': '81.22Z - Autres activités de nettoyage des bâtiments et nettoyage industriel',
                    '81.30Z': '81.30Z - Services d\'aménagement paysager',
                }
                self.urssaf_code = urssaf_descriptions.get(urssaf_code, f"{urssaf_code} - Travaux de peinture et vitrerie")

            def with_context(self, *args, **kwargs):
                # Méthode factice pour la compatibilité avec les templates
                return self

            def __bool__(self):
                # S'assurer que l'objet est considéré comme "vrai" dans les conditions
                return True

        return TempContract(self.env, 
            chantier=chantier, subcontractor=subcontractor, lot_ids=lot_ids, **contract_data
        )

    def _create_portal_link(self, contract, access_token):
        """Crée le lien sécurisé vers le portail."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/portal/contract/{contract.id}/sign?access_token={access_token}"
    
    def _get_blg_images_base64(self):
        """Récupère les images BLG en base64 pour éviter les erreurs réseau."""
        import os
        import base64
        
        try:
            # Méthode 1: Utiliser tools.config pour obtenir le chemin des addons
            try:
                from odoo.tools import config
                addons_path = config['addons_path'].split(',')[0] if config.get('addons_path') else None
                if addons_path:
                    addon_path = os.path.join(addons_path, 'construction_base')
                else:
                    raise Exception("addons_path non trouvé")
            except:
                # Méthode 2: Déduction depuis le chemin du fichier actuel
                current_file = os.path.abspath(__file__)
                addon_path = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))

            logo_path = file_path('construction_base/static/src/img/blg_logo.png')
            signature_path = file_path('construction_base/static/src/img/blg_signature.png')
            
            _logger.info(f"Chemin addon: {addon_path}")
            _logger.info(f"Logo existe: {os.path.exists(logo_path)}")
            _logger.info(f"Signature existe: {os.path.exists(signature_path)}")
            
            # Logo BLG
            with open(logo_path, 'rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            # Signature BLG  
            with open(signature_path, 'rb') as f:
                signature_b64 = base64.b64encode(f.read()).decode('utf-8')
                
            _logger.info(f"✅ Images BLG chargées: logo={len(logo_b64)} chars, signature={len(signature_b64)} chars")
                
            return {
                'logo': f"data:image/png;base64,{logo_b64}",
                'signature': f"data:image/png;base64,{signature_b64}"
            }
        except Exception as e:
            _logger.error(f"❌ Impossible de charger les images BLG: {e}")
            _logger.error(f"Chemin testé - addon: {addon_path if 'addon_path' in locals() else 'N/A'}")
            _logger.error(f"Chemin testé - logo: {logo_path if 'logo_path' in locals() else 'N/A'}")
            return {
                'logo': '',
                'signature': ''
            }
    
    def _generate_annexes_html(self, contract, blg_images):
        """Génère le HTML pour les documents annexes (CCTP, plannings)."""
        annexes_html = ""
        
        for lot in contract.lot_ids:
            _logger.info(f"🔍 Vérification documents pour lot: {lot.name}")
            
            # CCTP
            if hasattr(lot, 'document_cctp') and lot.document_cctp:
                _logger.info(f"📋 CCTP trouvé pour lot {lot.name}")
                annexes_html += self._create_document_page(
                    title=f"CCTP - {lot.name}",
                    subtitle="Cahier des Clauses Techniques Particulières",
                    document_type="CCTP",
                    lot_name=lot.name,
                    blg_images=blg_images
                )
            
            # Planning général
            if hasattr(lot, 'document_general_planning') and lot.document_general_planning:
                _logger.info(f"📅 Planning général trouvé pour lot {lot.name}")
                annexes_html += self._create_document_page(
                    title=f"Planning Général - {lot.name}",
                    subtitle="Planning global du chantier",
                    document_type="Planning Général",
                    lot_name=lot.name,
                    blg_images=blg_images
                )
            
            # Planning sous-traitant
            if hasattr(lot, 'document_subcontractor_planning') and lot.document_subcontractor_planning:
                _logger.info(f"👷 Planning sous-traitant trouvé pour lot {lot.name}")
                annexes_html += self._create_document_page(
                    title=f"Planning Sous-traitant - {lot.name}",
                    subtitle="Planning spécifique aux interventions",
                    document_type="Planning Sous-traitant",
                    lot_name=lot.name,
                    blg_images=blg_images
                )
        
        return annexes_html
    
    def _create_document_page(self, title, subtitle, document_type, lot_name, blg_images):
        """Crée une page HTML pour un document annexe."""
        return f"""
        <!-- Saut de page pour annexe -->
        <div style="page-break-before: always;"></div>
        <div class="page">
            <!-- En-tête avec logos pour annexe -->
            <div style="display: flex; align-items: center; justify-content: center; padding: 20px 0; border-bottom: 2px solid #20B2AA; margin-bottom: 30px;">
                <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 60px; margin-right: 30px;"/>
                <div style="text-align: center;">
                    <h1 style="color: #20B2AA; font-size: 28px; font-weight: bold; margin: 0;">{title}</h1>
                    <p style="color: #666; margin: 5px 0 0 0; font-size: 14px;">{subtitle}</p>
                </div>
                <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 60px; margin-left: 30px;"/>
            </div>
            
            <!-- Contenu de la page annexe -->
            <div style="text-align: center; padding: 50px 0;">
                <div style="background-color: #f0f8ff; border: 2px solid #20B2AA; border-radius: 10px; padding: 40px; margin: 20px 0;">
                    <h2 style="color: #20B2AA; margin-bottom: 20px;">📄 {document_type}</h2>
                    <h3 style="color: #333; margin-bottom: 15px;">Lot : {lot_name}</h3>
                    <p style="color: #666; font-size: 16px; margin-bottom: 20px;">
                        Ce document fait partie intégrante du contrat de sous-traitance.
                    </p>
                    <p style="color: #20B2AA; font-weight: bold; font-size: 14px;">
                        Document technique joint au contrat
                    </p>
                </div>
                
                <div style="margin-top: 40px; color: #666; font-size: 12px;">
                    <p>Ce document est consultable dans sa version complète via les annexes numériques.</p>
                    <p>Pour toute question technique, merci de vous référer au document original.</p>
                </div>
            </div>
        </div>
        """
    
    def _generate_final_signatures_page(self, contract, blg_images):
        """Génère une page finale dédiée aux signatures avec récapitulatif."""
        formatted_date = contract.create_date.strftime('%d/%m/%Y') if contract.create_date else fields.Date.today().strftime('%d/%m/%Y')
        
        return f"""
        <!-- Saut de page pour signatures finales -->
        <div style="page-break-before: always;"></div>
        <div class="page">
            
            <h2>Signatures du Contrat</h2>
            
            <!-- Signatures principales -->
            <div style="margin-bottom: 40px;">
                <h3 style="color: #20B2AA; text-align: center; margin-bottom: 30px;">✍️ Signatures des parties contractantes</h3>
                
                <!-- Signatures côte à côte -->
                <div style="display: flex; justify-content: space-around; align-items: flex-start; gap: 50px;">
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #20B2AA; font-weight: bold; margin-bottom: 15px; font-size: 18px;">Contractant général</p>
                        <p style="margin-bottom: 15px; font-weight: bold;">{contract.company_id.name or 'B.L.G GROUPE'}</p>
                        <div style="height: 120px; border: 2px solid #20B2AA; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; background-color: #f8f9fa;">
                            <img src="{blg_images['signature']}" alt="Signature et tampon BLG GROUPE" style="max-height: 100px; max-width: 200px;"/>
                        </div>
                        <p style="color: #666; font-size: 12px; margin-bottom: 5px;">(Signature et cachet commercial)</p>
                        <p style="color: #20B2AA; font-weight: bold;">Lu et approuvé</p>
                    </div>
                    
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #20B2AA; font-weight: bold; margin-bottom: 15px; font-size: 18px;">L'entreprise sous-traitante</p>
                        <p style="margin-bottom: 15px; font-weight: bold;">{contract.subcontractor_id.name or 'Non défini'}</p>
                        <div style="height: 120px; border: 2px solid #20B2AA; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; background-color: #f8f9fa;">
                            {f'<img src="data:image/png;base64,{contract.signature_image.decode("utf-8") if isinstance(contract.signature_image, bytes) else contract.signature_image}" alt="Signature sous-traitant" style="max-height: 100px; max-width: 200px;"/>' if contract.signature_image else '<p style="color: #999; font-style: italic;">Signature à apposer</p>'}
                        </div>
                        <p style="color: #666; font-size: 12px; margin-bottom: 5px;">(Signature et cachet de l'entreprise)</p>
                        <p style="color: #20B2AA; font-weight: bold;">Lu et approuvé</p>
                    </div>
                </div>
            </div>
            
            <!-- Mentions légales finales -->
            <div style="border-top: 1px solid #dee2e6; padding-top: 20px; font-size: 12px; color: #666;">
                <p style="text-align: center; margin-bottom: 10px;">
                    <strong>Ce contrat a été établi en deux exemplaires, chaque partie en conservant un.</strong>
                </p>
                <p style="text-align: center; margin-bottom: 10px;">
                    Fait à Bordeaux, le {formatted_date}
                </p>
                <p style="text-align: center; font-style: italic;">
                    Document contractuel - BLG GROUPE - Tous droits réservés
                </p>
            </div>
        </div>
        """
    
    def _generate_preview_signatures_page(self, contract, blg_images):
        """Génère la page de signatures pour la preview (sans signature sous-traitant)."""
        formatted_date = fields.Date.today().strftime('%d/%m/%Y')
        
        return f"""
        <!-- Saut de page pour signatures de preview -->
        <div style="page-break-before: always;"></div>
        <div class="page">
            
            <h2>Signatures du Contrat</h2>
            
            <!-- Note pour preview -->
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 20px; margin-bottom: 30px;">
                <div style="display: flex; align-items: center;">
                    <span style="font-size: 24px; margin-right: 15px;">ℹ️</span>
                    <div>
                        <h4 style="color: #856404; margin: 0 0 10px 0;">Aperçu du contrat</h4>
                        <p style="color: #856404; margin: 0; font-size: 14px;">
                            Ceci est un aperçu. La signature du sous-traitant sera collectée lors de la signature électronique finale.
                        </p>
                    </div>
                </div>
            </div>
            
            <!-- Signatures pour preview -->
            <div style="margin-bottom: 40px;">
                <h3 style="color: #20B2AA; text-align: center; margin-bottom: 30px;">✍️ Signatures des parties contractantes</h3>
                
                <!-- Signatures côte à côte -->
                <div style="display: flex; justify-content: space-around; align-items: flex-start; gap: 50px;">
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #20B2AA; font-weight: bold; margin-bottom: 15px; font-size: 18px;">Contractant général</p>
                        <p style="margin-bottom: 15px; font-weight: bold;">{contract.company_id.name or 'B.L.G GROUPE'}</p>
                        <div style="height: 120px; border: 2px solid #20B2AA; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; background-color: #f8f9fa;">
                            <img src="{blg_images['signature']}" alt="Signature et tampon BLG GROUPE" style="max-height: 100px; max-width: 200px;"/>
                        </div>
                        <p style="color: #666; font-size: 12px; margin-bottom: 5px;">(Signature et cachet commercial)</p>
                        <p style="color: #20B2AA; font-weight: bold;">Lu et approuvé</p>
                    </div>
                    
                    <div style="text-align: center; flex: 1;">
                        <p style="color: #20B2AA; font-weight: bold; margin-bottom: 15px; font-size: 18px;">L'entreprise sous-traitante</p>
                        <p style="margin-bottom: 15px; font-weight: bold;">{contract.subcontractor_id.name or 'Non défini'}</p>
                        <div style="height: 120px; border: 2px dashed #ccc; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 15px; background-color: #f9f9f9;">
                            <div style="text-align: center; color: #999;">
                                <p style="margin: 0; font-size: 14px; font-style: italic;">🖋️ Signature à apposer</p>
                                <p style="margin: 5px 0 0 0; font-size: 12px;">lors de la signature électronique</p>
                            </div>
                        </div>
                        <p style="color: #666; font-size: 12px; margin-bottom: 5px;">(Signature et cachet de l'entreprise)</p>
                        <p style="color: #20B2AA; font-weight: bold;">Lu et approuvé</p>
                    </div>
                </div>
            </div>
        </div>
        """

    def _generate_header_html(self, blg_logo):
        """Génère le HTML pour le header de toutes les pages."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
        }}
        .header-container {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10px;
            border-bottom: 1px solid #333;
            padding-bottom: 5px;
        }}
        .header-logo {{
            height: 50px;
            max-width: 100%;
        }}
        .header-title {{
            color: #333;
            font-size: 22px;
            font-weight: bold;
            margin: 0;
        }}
        .header-subtitle {{
            color: #666;
            margin: 5px 0 0 0;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <table class="header-container">
        <tr>
            <td style="width: 15%; text-align: left; vertical-align: middle;">
                <img src="{blg_logo}" alt="Logo BLG GROUPE" class="header-logo"/>
            </td>
            <td style="width: 70%; text-align: center; vertical-align: middle;">
                <h1 class="header-title">Contrat de sous-traitance</h1>
                <p class="header-subtitle">BLG GROUPE - Document contractuel</p>
            </td>
            <td style="width: 15%; text-align: right; vertical-align: middle;">
                <img src="{blg_logo}" alt="Logo BLG GROUPE" class="header-logo"/>
            </td>
        </tr>
    </table>
</body>
</html>"""

    def _generate_footer_html(self):
        """Génère le HTML pour le footer avec numérotation automatique."""
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10px;
            color: #666;
        }
        .footer-container {
            width: 100%;
            text-align: center;
            padding: 5px 0;
        }
        .page-number {
            font-size: 10px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="footer-container">
        <span class="page-number">Page <span class="page"></span> de <span class="topage"></span></span>
    </div>
</body>
</html>"""

    def test_header_footer_generation(self):
        """Méthode de test pour vérifier la génération des headers et footers."""
        try:
            # Récupérer les images BLG
            blg_images = self._get_blg_images_base64()
            
            # Générer header et footer
            header_html = self._generate_header_html(blg_images['logo'])
            footer_html = self._generate_footer_html()
            
            _logger.info("✅ Headers et footers générés avec succès")
            _logger.info(f"Header HTML length: {len(header_html)}")
            _logger.info(f"Footer HTML length: {len(footer_html)}")
            
            return {
                'header_html': header_html,
                'footer_html': footer_html,
                'success': True
            }
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération des headers/footers: {e}")
            return {
                'success': False,
                'error': str(e)
            }
