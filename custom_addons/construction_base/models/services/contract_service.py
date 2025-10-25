# -*- coding: utf-8 -*-
"""
Service de génération de contrats -
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
import base64
from datetime import datetime, timedelta
import os
import tempfile

from odoo.tools import file_path

_logger = logging.getLogger(__name__)


class ContractService(models.AbstractModel):
    _name = 'construction.contract.service'
    _description = 'Service de génération de contrats'

    def generate_contract(self, chantier, subcontractor, lot_ids, contract_data):
        """Génère un contrat de sous-traitance complet pour un ou plusieurs lots."""
        if not all([chantier, subcontractor, lot_ids]):
            raise ValidationError(_("Données manquantes pour la génération du contrat."))

        # Vérifier que tous les lots appartiennent au même sous-traitant
        if isinstance(lot_ids, (list, tuple)):
            lots = self.env['construction.lot'].browse(lot_ids)
        else:
            lots = lot_ids
            
        for lot in lots:
            if subcontractor not in lot.subcontractor_ids:
                raise ValidationError(_("Le lot '%s' n'est pas assigné au sous-traitant '%s'.") % (lot.name, subcontractor.name))

        contract_vals = self._prepare_contract_vals(chantier, subcontractor, lots, contract_data)
        contract = self.env['construction.subcontractor.contract'].create(contract_vals)

        pdf_content = self._generate_pdf_with_full_template(contract)

        access_token = contract._generate_access_token()
        portal_url = self._create_portal_link(contract, access_token)

        # Nom du fichier adapté pour les contrats groupés
        lot_names = "_".join([lot.name.replace(" ", "_") for lot in lots])
        filename = f"Contrat_{subcontractor.name}_{lot_names}_{datetime.now().strftime('%Y%m%d')}.pdf"

        contract.write({
            'contract_pdf': base64.b64encode(pdf_content),
            'filename': filename,
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

    def _prepare_contract_vals(self, chantier, subcontractor, lots, contract_data):
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
        
        # Nom du contrat adapté pour les lots multiples
        if len(lots) > 1:
            lot_names = ", ".join([lot.name for lot in lots])
            contract_name = f'Contrat groupé {subcontractor.name} - {chantier.name} ({lot_names})'
        else:
            contract_name = f'Contrat {subcontractor.name} - {chantier.name} - {lots[0].name}'
        
        return {
            'name': contract_name,
            'contract_number': self._generate_contract_number(),
            'chantier_id': chantier.id,
            'subcontractor_id': subcontractor.id,
            'lot_ids': [(6, 0, lots.ids)],
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
            
            # ===== GÉNÉRATION DU CONTRAT PRINCIPAL =====
            _logger.info(f"📄 Génération du contrat principal pour {contract.contract_number}")
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
            
            # Générer le PDF du contrat principal
            contract_pdf = self._generate_single_pdf(contract_html, "Contrat principal")
            
            # ===== GÉNÉRATION DES PDF D'ANNEXES =====
            annex_pdfs = []
            
            # ===== CONSOLIDATION DES BONS DE COMMANDE POUR TOUS LES LOTS =====
            if len(contract.lot_ids) > 1:
                # Pour les contrats groupés, consolider tous les bons de commande
                consolidated_purchase_orders_pdf = self._generate_consolidated_purchase_orders_pdf(contract, blg_images)
                if consolidated_purchase_orders_pdf:
                    annex_pdfs.append(consolidated_purchase_orders_pdf)
            else:
                # Pour un seul lot, utiliser la méthode existante
                lot = contract.lot_ids[0]
                purchase_orders_pdf = self._generate_purchase_orders_pdf(lot, contract, blg_images)
                if purchase_orders_pdf:
                    annex_pdfs.append(purchase_orders_pdf)
            
            # ===== GÉNÉRATION DES ANNEXES PAR LOT =====
            for lot in contract.lot_ids:
                _logger.info(f"🔍 Génération des annexes pour lot: {lot.name}")
                
                # CCTP et autres documents existants
                if hasattr(lot, 'document_cctp') and lot.document_cctp:
                    annex_pdfs.append(self._generate_document_annex_pdf(lot, "CCTP", blg_images))
                
                if hasattr(lot, 'document_general_planning') and lot.document_general_planning:
                    annex_pdfs.append(self._generate_document_annex_pdf(lot, "Planning Général", blg_images))
                
                if hasattr(lot, 'document_subcontractor_planning') and lot.document_subcontractor_planning:
                    annex_pdfs.append(self._generate_document_annex_pdf(lot, "Planning Sous-traitant", blg_images))
                
                # Planning Gantt en PDF (un par lot)
                planning_gantt_pdf = self._generate_planning_gantt_pdf(lot, contract, blg_images)
                if planning_gantt_pdf:
                    annex_pdfs.append(planning_gantt_pdf)
            
            # ===== GÉNÉRATION DE LA PAGE DE SIGNATURES =====
            signatures_html = self._generate_final_signatures_page(contract, blg_images)
            signatures_pdf = self._generate_single_pdf(signatures_html, "Signatures")
            
            # ===== FUSION DES PDF =====
            all_pdfs = [contract_pdf] + annex_pdfs + [signatures_pdf]
            final_pdf = self._merge_pdfs(all_pdfs)
            
            _logger.info(f"✅ PDF final généré avec succès pour contrat {contract.contract_number}")
            return final_pdf
            
        except Exception as e:
            _logger.error(f"❌ Erreur génération PDF: {e}")
            raise ValidationError(_("Impossible de générer le PDF du contrat. Erreur: %s") % str(e))

    def _generate_single_pdf(self, html_content, title):
        """Génère un PDF unique à partir d'un contenu HTML."""
        try:
            # Nettoyer complètement le HTML pour éliminer toute référence externe SAUF les data URI
            import re
            # Supprimer toutes les images qui pourraient pointer vers des URLs (mais garder data:)
            html_content = re.sub(r'<img[^>]*src=["\'](?!data:)[^"\']*["\'][^>]*>', '', html_content)
            # Supprimer tous les liens href
            html_content = re.sub(r'href=["\'][^"\']*["\']', '', html_content)
            # Supprimer toute référence à des ressources externes dans CSS
            html_content = re.sub(r'url\((?!data:)[^)]*\)', '', html_content)
            
            # Générer le PDF avec wkhtmltopdf et options optimisées pour le layout
            command = [
                'wkhtmltopdf',
                '--page-size', 'A4',
                '--orientation', 'Portrait',
                '--margin-top', '25mm',  # Espace pour le header
                '--margin-right', '8mm', 
                '--margin-bottom', '15mm',  # Espace pour le footer
                '--margin-left', '8mm',
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
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pdf_content, error = process.communicate(input=html_content.encode('utf-8'))
            
            if process.returncode == 0:
                _logger.info(f"✅ PDF {title} généré avec succès")
                return pdf_content
            else:
                _logger.error(f"❌ Erreur wkhtmltopdf: {error.decode()}")
                raise Exception(f"wkhtmltopdf failed: {error.decode()}")
                
        except Exception as e:
            _logger.error(f"❌ Erreur génération PDF: {e}")
            raise ValidationError(_("Impossible de générer le PDF. Erreur: %s") % str(e))

    def _merge_pdfs(self, pdf_list):
        """Fusionne plusieurs PDF en un seul."""
        try:
            # Créer des fichiers temporaires pour chaque PDF
            temp_files = []
            for i, pdf_content in enumerate(pdf_list):
                with tempfile.NamedTemporaryFile(mode='w+b', suffix='.pdf', delete=False) as temp_file:
                    temp_file.write(pdf_content)
                    temp_files.append(temp_file.name)
            
            # Créer un fichier temporaire pour le PDF final
            with tempfile.NamedTemporaryFile(mode='w+b', suffix='.pdf', delete=False) as final_file:
                final_path = final_file.name
            
            # Fusionner les PDF avec pdfunite
            command = ['pdfunite'] + temp_files + [final_path]
            
            import subprocess
            try:
                subprocess.run(command, check=True)
                _logger.info("✅ PDF fusionnés avec succès")
                
                # Lire le PDF final
                with open(final_path, 'rb') as f:
                    final_pdf_content = f.read()
                
                return final_pdf_content
            finally:
                # Nettoyer tous les fichiers temporaires
                for temp_file in temp_files + [final_path]:
                    try:
                        os.unlink(temp_file)
                    except Exception as e:
                        _logger.warning(f"Impossible de nettoyer le fichier temporaire: {e}")
                
        except Exception as e:
            _logger.error(f"❌ Erreur fusion PDF: {e}")
            raise ValidationError(_("Impossible de fusionner les PDF. Erreur: %s") % str(e))

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
    


    def _generate_order_lines_table_formal(self, order_lines):
        """Génère le tableau HTML des lignes de commande avec style formel."""
        if not order_lines:
            return "<p style='color: #666; font-style: italic; text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 8px;'>Aucune ligne de commande trouvée</p>"
        
        lines_html = ""
        for line in order_lines:
            lines_html += f"""
            <tr style="border-bottom: 1px solid #e9ecef; transition: background-color 0.3s;">
                <td style="padding: 12px; vertical-align: top; font-weight: 500;">{line.name}</td>
                <td style="padding: 12px; text-align: center; font-weight: bold;">{line.product_qty}</td>
                <td style="padding: 12px; text-align: center;">{line.product_uom.name if line.product_uom else 'Unité'}</td>
                <td style="padding: 12px; text-align: right; font-weight: bold;">{line.price_unit:,.2f} €</td>
                <td style="padding: 12px; text-align: right; font-weight: bold; color: #20B2AA;">{line.price_subtotal:,.2f} €</td>
            </tr>
            """
        
        return f"""
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <thead>
                <tr style="background: linear-gradient(135deg, #20B2AA 0%, #1a9999 100%); color: white;">
                    <th style="padding: 15px; text-align: left; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Description</th>
                    <th style="padding: 15px; text-align: center; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Quantité</th>
                    <th style="padding: 15px; text-align: center; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Unité</th>
                    <th style="padding: 15px; text-align: right; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Prix unitaire</th>
                    <th style="padding: 15px; text-align: right; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Total HT</th>
                </tr>
            </thead>
            <tbody>
                {lines_html}
            </tbody>
        </table>
        """

    def _create_empty_purchase_orders_page(self, lot, contract, blg_images):
        """Crée une page d'information quand aucun bon de commande n'est trouvé."""
        return f"""
        <!-- Saut de page pour bons de commande -->
        <div style="page-break-before: always;"></div>
        <div class="page">
            <!-- En-tête avec logos -->
            <div style="display: flex; align-items: center; justify-content: center; padding: 20px 0; border-bottom: 2px solid #20B2AA; margin-bottom: 30px;">
                <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 60px; margin-right: 30px;"/>
                <div style="text-align: center;">
                    <h1 style="color: #20B2AA; font-size: 28px; font-weight: bold; margin: 0;">🛒 Bons de commande - {lot.name}</h1>
                    <p style="color: #666; margin: 5px 0 0 0; font-size: 14px;">Détail des commandes et prestations</p>
                </div>
                <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 60px; margin-left: 30px;"/>
            </div>
            
            <!-- Message d'information -->
            <div style="text-align: center; padding: 50px 0;">
                <div style="background-color: #fff3cd; border: 2px solid #ffeaa7; border-radius: 10px; padding: 40px; margin: 20px 0;">
                    <h2 style="color: #856404; margin-bottom: 20px;">📋 Bons de commande</h2>
                    <h3 style="color: #333; margin-bottom: 15px;">Lot : {lot.name}</h3>
                    <p style="color: #856404; font-size: 16px; margin-bottom: 20px;">
                        Les bons de commande seront établis lors de la phase d'exécution des travaux.
                    </p>
                    <p style="color: #856404; font-weight: bold; font-size: 14px;">
                        Commandes à définir selon les spécifications techniques
                    </p>
                </div>
                
                <div style="margin-top: 40px; color: #666; font-size: 12px;">
                    <p>Les détails des commandes seront communiqués avant le démarrage des travaux.</p>
                    <p>Chaque commande fera l'objet d'une validation préalable avec le sous-traitant.</p>
                </div>
            </div>
        </div>
        """

    def _generate_order_lines_table(self, order_lines):
        """Génère le tableau HTML des lignes de commande."""
        if not order_lines:
            return "<p style='color: #666; font-style: italic;'>Aucune ligne de commande trouvée</p>"
        
        lines_html = ""
        for line in order_lines:
            lines_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 8px; vertical-align: top;">{line.name}</td>
                <td style="padding: 8px; text-align: center;">{line.product_qty}</td>
                <td style="padding: 8px; text-align: center;">{line.product_uom.name if line.product_uom else 'Unité'}</td>
                <td style="padding: 8px; text-align: right;">{line.price_unit:,.2f} €</td>
                <td style="padding: 8px; text-align: right; font-weight: bold;">{line.price_subtotal:,.2f} €</td>
            </tr>
            """
        
        return f"""
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 12px;">
            <thead>
                <tr style="background-color: #20B2AA; color: white;">
                    <th style="padding: 10px; text-align: left;">Description</th>
                    <th style="padding: 10px; text-align: center;">Qté</th>
                    <th style="padding: 10px; text-align: center;">Unité</th>
                    <th style="padding: 10px; text-align: right;">Prix unitaire</th>
                    <th style="padding: 10px; text-align: right;">Total</th>
                </tr>
            </thead>
            <tbody>
                {lines_html}
            </tbody>
        </table>
        """

    def _create_planning_gantt_page(self, lot, contract, blg_images):
        """Crée une page HTML avec le planning Gantt du lot en utilisant archiereport."""
        try:
            # ===== RÉCUPÉRATION DES VRAIES TÂCHES DE PLANNING =====
            _logger.info(f"📅 === DÉBOGAGE PLANNING GANTT POUR LOT {lot.name} ===")
            
            # Rechercher les tâches de planning pour ce lot
            planning_tasks = self.env['construction.planning.task'].search([
                ('lot_id', '=', lot.id),
                ('chantier_id', '=', contract.chantier_id.id)
            ], order='date_start asc')
            
            _logger.info(f"📅 Tâches de planning trouvées pour lot {lot.name}: {len(planning_tasks)}")
            
            # Si aucune tâche trouvée, créer une page d'information
            if not planning_tasks:
                return self._create_empty_planning_page(lot, contract, blg_images)
            
            # ===== GÉNÉRATION DU RENDU GANTT AVEC ARCHIEREPORT =====
            try:
                # Utiliser archiereport pour générer le Gantt
                gantt_html = self._generate_gantt_with_archiereport(planning_tasks, lot, contract)
                _logger.info(f"📅 Rendu Gantt généré avec succès pour lot {lot.name}")
            except Exception as e:
                _logger.warning(f"📅 Erreur génération Gantt avec archiereport: {e}, fallback sur tableau")
                gantt_html = self._generate_planning_tasks_table_formal(planning_tasks)
            
            # Calculer la durée totale
            if planning_tasks:
                start_date = min(task.date_start for task in planning_tasks if task.date_start)
                end_date = max(task.date_stop for task in planning_tasks if task.date_stop)
                duration = (end_date.date() - start_date.date()).days if start_date and end_date else 0
            else:
                start_date = end_date = None
                duration = 0
            
            return f"""
            <!-- Saut de page pour planning Gantt -->
            <div style="page-break-before: always;"></div>
            <div class="page">
                <!-- En-tête avec logos -->
                <div style="display: flex; align-items: center; justify-content: center; padding: 25px 0; border-bottom: 3px solid #20B2AA; margin-bottom: 35px;">
                    <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 70px; margin-right: 40px;"/>
                    <div style="text-align: center;">
                        <h1 style="color: #20B2AA; font-size: 32px; font-weight: bold; margin: 0; text-transform: uppercase; letter-spacing: 2px;">📅 Planning Gantt</h1>
                        <h2 style="color: #1a7a7a; font-size: 20px; margin: 10px 0 0 0;">Lot : {lot.name}</h2>
                        <p style="color: #666; margin: 5px 0 0 0; font-size: 16px;">Planification contractuelle des tâches et calendrier</p>
                    </div>
                    <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 70px; margin-left: 40px;"/>
                </div>
                
                <!-- Informations du planning -->
                <div style="background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%); border-left: 5px solid #20B2AA; padding: 20px; margin-bottom: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(32, 178, 170, 0.1);">
                    <h3 style="color: #20B2AA; margin: 0 0 15px 0; font-size: 20px; font-weight: bold;">📋 Informations contractuelles du planning</h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div>
                            <p style="margin: 8px 0; font-weight: bold;"><strong>🏗️ Chantier :</strong> {contract.chantier_id.name}</p>
                            <p style="margin: 8px 0; font-weight: bold;"><strong>📦 Lot :</strong> {lot.name}</p>
                        </div>
                        <div>
                            <p style="margin: 8px 0; font-weight: bold;"><strong>👷 Sous-traitant :</strong> {contract.subcontractor_id.name}</p>
                            <p style="margin: 8px 0; font-weight: bold;"><strong>📊 Nombre de tâches :</strong> {len(planning_tasks)}</p>
                        </div>
                    </div>
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #20B2AA;">
                        <p style="margin: 8px 0; font-weight: bold;"><strong>📅 Période contractuelle :</strong> 
                            {start_date.strftime('%d/%m/%Y') if start_date else 'Non définie'} 
                            - {end_date.strftime('%d/%m/%Y') if end_date else 'Non définie'} 
                            ({duration} jours)
                        </p>
                    </div>
                </div>
                
                <!-- Rendu Gantt -->
                <div style="margin-bottom: 35px;">
                    <h3 style="color: #20B2AA; border-bottom: 3px solid #20B2AA; padding-bottom: 12px; font-size: 22px; font-weight: bold; margin-bottom: 25px;">📈 Planning contractuel - Diagramme de Gantt</h3>
                    {gantt_html}
                </div>
                
                <!-- Légende des statuts -->
                <div style="border: 3px solid #20B2AA; border-radius: 15px; padding: 25px; background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%); margin-bottom: 35px; box-shadow: 0 4px 12px rgba(32, 178, 170, 0.15);">
                    <h3 style="color: #20B2AA; text-align: center; margin: 0 0 20px 0; font-size: 24px; font-weight: bold;">🔖 Légende des statuts contractuels</h3>
                    <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 25px;">
                        <div style="text-align: center; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <span style="background-color: #6c757d; color: white; padding: 8px 15px; border-radius: 20px; font-size: 13px; font-weight: bold; display: block; margin-bottom: 8px;">Brouillon</span>
                            <p style="margin: 0; font-size: 12px; color: #666;">Tâche en préparation</p>
                        </div>
                        <div style="text-align: center; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <span style="background-color: #17a2b8; color: white; padding: 8px 15px; border-radius: 20px; font-size: 13px; font-weight: bold; display: block; margin-bottom: 8px;">Planifiée</span>
                            <p style="margin: 0; font-size: 12px; color: #666;">Tâche programmée</p>
                        </div>
                        <div style="text-align: center; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <span style="background-color: #ffc107; color: black; padding: 8px 15px; border-radius: 20px; font-size: 13px; font-weight: bold; display: block; margin-bottom: 8px;">En cours</span>
                            <p style="margin: 0; font-size: 12px; color: #666;">Tâche en exécution</p>
                        </div>
                        <div style="text-align: center; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <span style="background-color: #28a745; color: white; padding: 8px 15px; border-radius: 20px; font-size: 13px; font-weight: bold; display: block; margin-bottom: 8px;">Terminée</span>
                            <p style="margin: 0; font-size: 12px; color: #666;">Tâche achevée</p>
                        </div>
                        <div style="text-align: center; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <span style="background-color: #dc3545; color: white; padding: 8px 15px; border-radius: 20px; font-size: 13px; font-weight: bold; display: block; margin-bottom: 8px;">Annulée</span>
                            <p style="margin: 0; font-size: 12px; color: #666;">Tâche supprimée</p>
                        </div>
                    </div>
                </div>
                
                <!-- Notes planning -->
                <div style="border-top: 2px solid #20B2AA; padding-top: 20px; font-size: 12px; color: #666; text-align: center; background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
                    <p style="margin: 8px 0; font-weight: bold;">Ce planning est contractuel et peut être ajusté selon les contraintes du chantier.</p>
                    <p style="margin: 8px 0;">Les dates de début et fin peuvent être modifiées en accord avec toutes les parties contractantes.</p>
                    <p style="margin: 8px 0; font-style: italic;">Document contractuel - BLG GROUPE - Tous droits réservés</p>
                </div>
            </div>
            """
            
        except Exception as e:
            _logger.error(f"❌ Erreur lors de la génération du planning Gantt pour {lot.name}: {e}")
            return self._create_empty_planning_page(lot, contract, blg_images)

    def _generate_gantt_with_archiereport(self, planning_tasks, lot, contract):
        """Génère un rendu Gantt avec archiereport."""
        try:
            # Préparer les données pour le Gantt
            gantt_data = []
            for task in planning_tasks:
                # Calculer la durée en jours
                duration = 0
                if task.date_start and task.date_stop:
                    duration = (task.date_stop.date() - task.date_start.date()).days
                
                # Couleur selon le statut
                status_colors = {
                    'draft': '#6c757d',
                    'planned': '#17a2b8',
                    'in_progress': '#ffc107',
                    'done': '#28a745',
                    'cancelled': '#dc3545'
                }
                color = status_colors.get(task.state, '#6c757d')
                
                gantt_data.append({
                    'id': task.id,
                    'name': task.name,
                    'start': task.date_start.strftime('%Y-%m-%d') if task.date_start else '',
                    'end': task.date_stop.strftime('%Y-%m-%d') if task.date_stop else '',
                    'duration': duration,
                    'color': color,
                    'subcontractor': task.subcontractor_id.name if task.subcontractor_id else 'Non assigné',
                    'state': task.state,
                    'description': task.description or ''
                })
            
            # Générer le HTML du Gantt avec CSS personnalisé
            gantt_html = self._render_gantt_html(gantt_data, lot, contract)
            
            return gantt_html
            
        except Exception as e:
            _logger.error(f"❌ Erreur génération Gantt avec archiereport: {e}")
            raise e

    def _render_gantt_html(self, gantt_data, lot, contract):
        """Rend le HTML du diagramme de Gantt."""
        if not gantt_data:
            return "<p style='color: #666; font-style: italic; text-align: center; padding: 40px; background-color: #f8f9fa; border-radius: 8px;'>Aucune tâche de planning disponible</p>"
        
        # Calculer les dates min/max pour l'échelle
        start_dates = [task['start'] for task in gantt_data if task['start']]
        end_dates = [task['end'] for task in gantt_data if task['end']]
        
        if not start_dates or not end_dates:
            return "<p style='color: #666; font-style: italic; text-align: center; padding: 40px; background-color: #f8f9fa; border-radius: 8px;'>Dates de planning non définies</p>"
        
        min_date = min(start_dates)
        max_date = max(end_dates)
        
        # Convertir en objets date pour calculer la durée totale
        from datetime import datetime
        min_date_obj = datetime.strptime(min_date, '%Y-%m-%d').date()
        max_date_obj = datetime.strptime(max_date, '%Y-%m-%d').date()
        total_days = (max_date_obj - min_date_obj).days + 1
        
        # Générer l'échelle temporelle
        timeline_html = self._generate_timeline_html(min_date_obj, max_date_obj)
        
        # Générer les barres de tâches
        tasks_html = ""
        for task in gantt_data:
            if task['start'] and task['end']:
                start_date = datetime.strptime(task['start'], '%Y-%m-%d').date()
                end_date = datetime.strptime(task['end'], '%Y-%m-%d').date()
                
                # Calculer la position et largeur
                days_from_start = (start_date - min_date_obj).days
                duration = (end_date - start_date).days + 1
                
                left_percent = (days_from_start / total_days) * 100
                width_percent = (duration / total_days) * 100
                
                tasks_html += f"""
                <div class="gantt-task" style="
                    position: absolute;
                    left: {left_percent}%;
                    width: {width_percent}%;
                    background-color: {task['color']};
                    color: white;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                    cursor: pointer;
                    transition: all 0.3s ease;
                    z-index: 10;
                " title="{task['name']} - {task['subcontractor']} - {task['duration']} jours">
                    <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        {task['name']}
                    </div>
                </div>
                """
        
        return f"""
        <div style="background: white; border: 2px solid #20B2AA; border-radius: 10px; padding: 20px; margin: 20px 0; box-shadow: 0 4px 12px rgba(32, 178, 170, 0.1);">
            <div style="margin-bottom: 20px;">
                <h4 style="color: #20B2AA; margin: 0 0 10px 0; font-size: 18px; font-weight: bold;">📊 Diagramme de Gantt - {lot.name}</h4>
                <p style="margin: 0; color: #666; font-size: 14px;">Période : {min_date_obj.strftime('%d/%m/%Y')} - {max_date_obj.strftime('%d/%m/%Y')} ({total_days} jours)</p>
            </div>
            
            <div style="position: relative; overflow-x: auto;">
                <div style="min-width: 800px; position: relative;">
                    <!-- Échelle temporelle -->
                    <div style="height: 40px; border-bottom: 2px solid #20B2AA; margin-bottom: 20px; position: relative;">
                        {timeline_html}
                    </div>
                    
                    <!-- Barres de tâches -->
                    <div style="height: 200px; position: relative; background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%); border-radius: 8px; padding: 20px;">
                        {tasks_html}
                    </div>
                </div>
            </div>
            
            <!-- Informations détaillées -->
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e9ecef;">
                <h5 style="color: #20B2AA; margin: 0 0 15px 0; font-size: 16px; font-weight: bold;">📋 Détail des tâches</h5>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
                    {self._generate_task_details_html(gantt_data)}
                </div>
            </div>
        </div>
        """

    def _generate_timeline_html(self, min_date, max_date):
        """Génère l'échelle temporelle du Gantt."""
        timeline_html = ""
        current_date = min_date
        day_count = 0
        
        while current_date <= max_date:
            # Afficher les mois et semaines
            if current_date.day == 1 or day_count == 0:
                timeline_html += f"""
                <div style="
                    position: absolute;
                    left: {(day_count / (max_date - min_date).days) * 100}%;
                    transform: translateX(-50%);
                    text-align: center;
                    font-weight: bold;
                    color: #20B2AA;
                    font-size: 12px;
                    border-left: 1px solid #20B2AA;
                    padding-left: 5px;
                    height: 100%;
                ">
                    {current_date.strftime('%b %Y')}
                </div>
                """
            
            # Afficher les semaines
            if current_date.weekday() == 0:  # Lundi
                timeline_html += f"""
                <div style="
                    position: absolute;
                    left: {(day_count / (max_date - min_date).days) * 100}%;
                    transform: translateX(-50%);
                    text-align: center;
                    color: #666;
                    font-size: 10px;
                    border-left: 1px dashed #ccc;
                    padding-left: 3px;
                    height: 100%;
                    top: 20px;
                ">
                    S{current_date.isocalendar()[1]}
                </div>
                """
            
            current_date += timedelta(days=1)
            day_count += 1
        
        return timeline_html

    def _generate_task_details_html(self, gantt_data):
        """Génère les détails des tâches pour le Gantt."""
        details_html = ""
        for task in gantt_data:
            status_display = {
                'draft': '📝 Brouillon',
                'planned': '📅 Planifiée',
                'in_progress': '⚡ En cours',
                'done': '✅ Terminée',
                'cancelled': '❌ Annulée'
            }.get(task['state'], '❓ Inconnu')
            
            details_html += f"""
            <div style="
                background: white;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            ">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <div style="
                        width: 12px;
                        height: 12px;
                        background-color: {task['color']};
                        border-radius: 50%;
                        margin-right: 10px;
                    "></div>
                    <h6 style="margin: 0; color: #20B2AA; font-weight: bold; font-size: 14px;">{task['name']}</h6>
                </div>
                <p style="margin: 5px 0; font-size: 12px; color: #666;"><strong>👷 Sous-traitant:</strong> {task['subcontractor']}</p>
                <p style="margin: 5px 0; font-size: 12px; color: #666;"><strong>📅 Période:</strong> {task['start']} - {task['end']}</p>
                <p style="margin: 5px 0; font-size: 12px; color: #666;"><strong>⏱️ Durée:</strong> {task['duration']} jour(s)</p>
                <p style="margin: 5px 0; font-size: 12px; color: #666;"><strong>📊 Statut:</strong> {status_display}</p>
            </div>
            """
        
        return details_html

    def _generate_planning_tasks_table_formal(self, planning_tasks):
        """Génère le tableau HTML des tâches de planning avec style formel."""
        if not planning_tasks:
            return "<p style='color: #666; font-style: italic; text-align: center; padding: 40px; background-color: #f8f9fa; border-radius: 8px;'>Aucune tâche de planning trouvée</p>"
        
        tasks_html = ""
        for task in planning_tasks:
            # Durée en jours
            duration = 0
            if task.date_start and task.date_stop:
                duration = (task.date_stop.date() - task.date_start.date()).days
            
            # Style du statut
            status_styles = {
                'draft': {'bg': '#6c757d', 'color': 'white', 'text': '📝 Brouillon'},
                'planned': {'bg': '#17a2b8', 'color': 'white', 'text': '📅 Planifiée'},
                'in_progress': {'bg': '#ffc107', 'color': 'black', 'text': '⚡ En cours'},
                'done': {'bg': '#28a745', 'color': 'white', 'text': '✅ Terminée'},
                'cancelled': {'bg': '#dc3545', 'color': 'white', 'text': '❌ Annulée'}
            }
            status_style = status_styles.get(task.state, status_styles['draft'])
            
            # Indication hors limites
            row_class = "background-color: #ffe6e6;" if task.is_out_of_bounds else ""
            
            tasks_html += f"""
            <tr style="border-bottom: 1px solid #e9ecef; {row_class}">
                <td style="padding: 12px; vertical-align: top;">
                    <strong style="color: #20B2AA;">{task.name}</strong>
                    {f'<br><small style="color: #666;">{task.description}</small>' if task.description else ''}
                </td>
                <td style="padding: 12px; text-align: center; font-weight: bold;">{task.subcontractor_id.name if task.subcontractor_id else 'Non assigné'}</td>
                <td style="padding: 12px; text-align: center; font-weight: bold;">
                    {task.date_start.strftime('%d/%m/%Y') if task.date_start else 'Non définie'}
                </td>
                <td style="padding: 12px; text-align: center; font-weight: bold;">
                    {task.date_stop.strftime('%d/%m/%Y') if task.date_stop else 'Non définie'}
                </td>
                <td style="padding: 12px; text-align: center; font-weight: bold; color: #20B2AA;">{duration} jour{'s' if duration > 1 else ''}</td>
                <td style="padding: 12px; text-align: center;">
                    <span style="background-color: {status_style['bg']}; color: {status_style['color']}; padding: 8px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                        {status_style['text']}
                    </span>
                    {' ⚠️' if task.is_out_of_bounds else ''}
                </td>
            </tr>
            """
        
        return f"""
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <thead>
                <tr style="background: linear-gradient(135deg, #20B2AA 0%, #1a9999 100%); color: white;">
                    <th style="padding: 15px; text-align: left; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Tâche</th>
                    <th style="padding: 15px; text-align: center; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Sous-traitant</th>
                    <th style="padding: 15px; text-align: center; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Début</th>
                    <th style="padding: 15px; text-align: center; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Fin</th>
                    <th style="padding: 15px; text-align: center; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Durée</th>
                    <th style="padding: 15px; text-align: center; font-weight: bold; font-size: 14px; letter-spacing: 0.5px;">Statut</th>
                </tr>
            </thead>
            <tbody>
                {tasks_html}
            </tbody>
        </table>
        """

    def _create_empty_planning_page(self, lot, contract, blg_images):
        """Crée une page d'information quand aucune tâche de planning n'est trouvée."""
        return f"""
        <!-- Saut de page pour planning Gantt -->
        <div style="page-break-before: always;"></div>
        <div class="page">
            <!-- En-tête avec logos -->
            <div style="display: flex; align-items: center; justify-content: center; padding: 20px 0; border-bottom: 2px solid #20B2AA; margin-bottom: 30px;">
                <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 60px; margin-right: 30px;"/>
                <div style="text-align: center;">
                    <h1 style="color: #20B2AA; font-size: 28px; font-weight: bold; margin: 0;">📅 Planning Gantt - {lot.name}</h1>
                    <p style="color: #666; margin: 5px 0 0 0; font-size: 14px;">Planification des tâches et calendrier</p>
                </div>
                <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 60px; margin-left: 30px;"/>
            </div>
            
            <!-- Message d'information -->
            <div style="text-align: center; padding: 50px 0;">
                <div style="background-color: #e7f3ff; border: 2px solid #20B2AA; border-radius: 10px; padding: 40px; margin: 20px 0;">
                    <h2 style="color: #20B2AA; margin-bottom: 20px;">📅 Planning Gantt</h2>
                    <h3 style="color: #333; margin-bottom: 15px;">Lot : {lot.name}</h3>
                    <p style="color: #20B2AA; font-size: 16px; margin-bottom: 20px;">
                        Le planning détaillé sera établi lors de la phase de préparation des travaux.
                    </p>
                    <p style="color: #20B2AA; font-weight: bold; font-size: 14px;">
                        Planification en cours d'élaboration
                    </p>
                </div>
                
                <div style="margin-top: 40px; color: #666; font-size: 12px;">
                    <p>Le planning détaillé sera communiqué avant le démarrage des travaux.</p>
                    <p>Les dates de réalisation seront définies en concertation avec le sous-traitant.</p>
                </div>
            </div>
        </div>
        """

    def _generate_consolidated_purchase_orders_pdf(self, contract, blg_images):
        """Génère un PDF consolidé pour tous les bons de commande des lots du contrat."""
        try:
            all_purchase_orders = []
            total_amount = 0.0
            
            # Récupérer tous les bons de commande pour tous les lots
            for lot in contract.lot_ids:
                lot_orders = self._get_lot_purchase_orders(lot, contract)
                for order in lot_orders:
                    all_purchase_orders.append({
                        'order': order,
                        'lot': lot,
                        'lot_amount': sum(line.price_subtotal for line in order.order_line.filtered(lambda l: l.lot_id.id == lot.id or not l.lot_id))
                    })
                    total_amount += sum(line.price_subtotal for line in order.order_line.filtered(lambda l: l.lot_id.id == lot.id or not l.lot_id))
            
            if not all_purchase_orders:
                return None
            
            # Générer le HTML consolidé
            html_content = self._generate_consolidated_purchase_orders_html(contract, all_purchase_orders, total_amount, blg_images)
            
            # Générer le PDF
            return self._generate_single_pdf(html_content, f"Bons de commande consolidés - {contract.subcontractor_id.name}")
            
        except Exception as e:
            _logger.error(f"❌ Erreur génération PDF bons de commande consolidés: {e}")
            return None

    def _generate_purchase_orders_pdf(self, lot, contract, blg_images):
        """Génère un PDF séparé pour les bons de commande du lot."""
        try:
            # Récupérer les bons de commande du lot
            purchase_orders = self._get_lot_purchase_orders(lot, contract)
            
            if not purchase_orders:
                return None
            
            # Générer le HTML pour les bons de commande
            html_content = self._generate_purchase_orders_html(lot, contract, purchase_orders, blg_images)
            
            # Générer le PDF
            return self._generate_single_pdf(html_content, f"Bons de commande - {lot.name}")
            
        except Exception as e:
            _logger.error(f"❌ Erreur génération PDF bons de commande pour {lot.name}: {e}")
            return None

    def _generate_planning_gantt_pdf(self, lot, contract, blg_images):
        """Génère un PDF séparé pour le planning Gantt du lot."""
        try:
            # Récupérer les tâches de planning du lot
            planning_tasks = self.env['construction.planning.task'].search([
                ('lot_id', '=', lot.id),
                ('chantier_id', '=', contract.chantier_id.id)
            ], order='date_start asc')
            
            if not planning_tasks:
                return None
            
            # Générer le HTML pour le planning Gantt
            html_content = self._generate_planning_gantt_html(lot, contract, planning_tasks, blg_images)
            
            # Générer le PDF
            return self._generate_single_pdf(html_content, f"Planning Gantt - {lot.name}")
            
        except Exception as e:
            _logger.error(f"❌ Erreur génération PDF planning Gantt pour {lot.name}: {e}")
            return None

    def _generate_document_annex_pdf(self, lot, document_type, blg_images):
        """Génère un PDF pour un document annexe existant."""
        try:
            html_content = self._create_document_page_html(lot, document_type, blg_images)
            return self._generate_single_pdf(html_content, f"{document_type} - {lot.name}")
        except Exception as e:
            _logger.error(f"❌ Erreur génération PDF {document_type} pour {lot.name}: {e}")
            return None

    def _get_lot_purchase_orders(self, lot, contract):
        """Récupère les bons de commande associés au lot."""
        # Recherche via lot_ids sur le bon de commande
        orders_via_lot_ids = self.env['purchase.order'].search([
            ('lot_ids', 'in', [lot.id]),
            ('state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        
        # Recherche via les lignes de commande
        order_lines_with_lot = self.env['purchase.order.line'].search([
            ('lot_id', '=', lot.id),
            ('order_id.state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        orders_via_lines = order_lines_with_lot.mapped('order_id')
        
        # Combiner les deux méthodes
        all_lot_orders = orders_via_lot_ids | orders_via_lines
        
        # Filtrage par sous-traitant si spécifié
        if contract.subcontractor_id:
            purchase_orders = all_lot_orders.filtered(lambda po: po.partner_id == contract.subcontractor_id)
            if not purchase_orders:
                purchase_orders = all_lot_orders
        else:
            purchase_orders = all_lot_orders
        
        return purchase_orders

    def _generate_purchase_orders_html(self, lot, contract, purchase_orders, blg_images):
        """Génère le HTML pour les bons de commande avec style formel."""
        # Construire le contenu HTML avec style formel
        orders_content = ""
        total_amount = 0.0
        
        for order in purchase_orders:
            # Filtrer les lignes spécifiques au lot
            order_lines = order.order_line.filtered(lambda l: l.lot_id.id == lot.id or not l.lot_id)
            order_total = sum(line.price_subtotal for line in order_lines)
            total_amount += order_total
            
            # État avec style formel
            state_display = {
                'draft': ('Brouillon', '#6c757d', '📝'),
                'sent': ('Envoyé', '#17a2b8', '📤'),
                'to_approve': ('À approuver', '#ffc107', '⏳'),
                'purchase': ('Confirmé', '#28a745', '✅'),
                'done': ('Terminé', '#20B2AA', '🏁'),
                'cancel': ('Annulé', '#dc3545', '❌')
            }.get(order.state, (order.state, '#6c757d', '❓'))
            
            orders_content += f"""
            <div style="margin-bottom: 30px; border: 2px solid #20B2AA; border-radius: 10px; padding: 25px; background-color: #f8f9fa; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 2px solid #20B2AA; padding-bottom: 15px;">
                    <h4 style="color: #20B2AA; margin: 0; font-size: 18px; font-weight: bold;">{state_display[2]} {order.name}</h4>
                    <span style="background-color: {state_display[1]}; color: white; padding: 8px 15px; border-radius: 25px; font-size: 13px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                        {state_display[0]}
                    </span>
                </div>
                
                <div style="margin-bottom: 20px; background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #20B2AA;">
                    <p style="margin: 8px 0; font-weight: bold;"><strong>📅 Date de commande :</strong> {order.date_order.strftime('%d/%m/%Y') if order.date_order else 'Non définie'}</p>
                    <p style="margin: 8px 0;"><strong>🏢 Fournisseur :</strong> {order.partner_id.name or 'Non défini'}</p>
                    <p style="margin: 8px 0;"><strong>📋 Référence :</strong> {order.partner_ref or 'Non définie'}</p>
                    <p style="margin: 8px 0;"><strong>📝 Notes :</strong> {order.notes or 'Aucune note'}</p>
                </div>
                
                {self._generate_order_lines_table_formal(order_lines)}
                
                <div style="text-align: right; margin-top: 20px; padding: 15px; background: linear-gradient(135deg, #20B2AA 0%, #1a9999 100%); border-radius: 8px; color: white;">
                    <p style="margin: 0; font-size: 18px; font-weight: bold;">
                        💰 Total : {order_total:,.2f} {order.currency_id.symbol}
                    </p>
                </div>
            </div>
            """
        
    def _generate_consolidated_purchase_orders_html(self, contract, all_purchase_orders, total_amount, blg_images):
        """Génère le HTML consolidé pour tous les bons de commande des lots du contrat."""
        # Construire le contenu HTML consolidé
        orders_content = ""
        lot_groups = {}
        
        # Grouper les commandes par lot
        for order_data in all_purchase_orders:
            lot = order_data['lot']
            if lot.id not in lot_groups:
                lot_groups[lot.id] = {
                    'lot': lot,
                    'orders': [],
                    'lot_total': 0.0
                }
            lot_groups[lot.id]['orders'].append(order_data['order'])
            lot_groups[lot.id]['lot_total'] += order_data['lot_amount']
        
        # Générer le contenu pour chaque lot
        for lot_id, lot_data in lot_groups.items():
            lot = lot_data['lot']
            orders = lot_data['orders']
            lot_total = lot_data['lot_total']
            
            orders_content += f"""
            <div style="margin-bottom: 40px; border: 3px solid #20B2AA; border-radius: 15px; padding: 25px; background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%); box-shadow: 0 4px 12px rgba(32, 178, 170, 0.15);">
                <h3 style="color: #20B2AA; text-align: center; margin: 0 0 25px 0; font-size: 24px; font-weight: bold;">📦 Lot : {lot.name}</h3>
                <p style="text-align: center; color: #1a7a7a; font-size: 16px; margin-bottom: 25px;">Montant total du lot : <strong>{lot_total:,.2f} €</strong></p>
            """
            
            for order in orders:
                # Filtrer les lignes spécifiques au lot
                order_lines = order.order_line.filtered(lambda l: l.lot_id.id == lot.id or not l.lot_id)
                order_total = sum(line.price_subtotal for line in order_lines)
                
                # État avec style formel
                state_display = {
                    'draft': ('Brouillon', '#6c757d', '📝'),
                    'sent': ('Envoyé', '#17a2b8', '📤'),
                    'to_approve': ('À approuver', '#ffc107', '⏳'),
                    'purchase': ('Confirmé', '#28a745', '✅'),
                    'done': ('Terminé', '#20B2AA', '🏁'),
                    'cancel': ('Annulé', '#dc3545', '❌')
                }.get(order.state, (order.state, '#6c757d', '❓'))
                
                orders_content += f"""
                <div style="margin-bottom: 30px; border: 2px solid #20B2AA; border-radius: 10px; padding: 25px; background-color: #f8f9fa; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 2px solid #20B2AA; padding-bottom: 15px;">
                        <h4 style="color: #20B2AA; margin: 0; font-size: 18px; font-weight: bold;">{state_display[2]} {order.name}</h4>
                        <span style="background-color: {state_display[1]}; color: white; padding: 8px 15px; border-radius: 25px; font-size: 13px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                            {state_display[0]}
                        </span>
                    </div>
                    
                    <div style="margin-bottom: 20px; background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #20B2AA;">
                        <p style="margin: 8px 0; font-weight: bold;"><strong>📅 Date de commande :</strong> {order.date_order.strftime('%d/%m/%Y') if order.date_order else 'Non définie'}</p>
                        <p style="margin: 8px 0;"><strong>🏢 Fournisseur :</strong> {order.partner_id.name or 'Non défini'}</p>
                        <p style="margin: 8px 0;"><strong>📋 Référence :</strong> {order.partner_ref or 'Non définie'}</p>
                        <p style="margin: 8px 0;"><strong>📝 Notes :</strong> {order.notes or 'Aucune note'}</p>
                    </div>
                    
                    {self._generate_order_lines_table_formal(order_lines)}
                    
                    <div style="text-align: right; margin-top: 20px; padding: 15px; background: linear-gradient(135deg, #20B2AA 0%, #1a9999 100%); border-radius: 8px; color: white;">
                        <p style="margin: 0; font-size: 18px; font-weight: bold;">
                            💰 Total : {order_total:,.2f} {order.currency_id.symbol}
                        </p>
                    </div>
                </div>
                """
            
            orders_content += "</div>"
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Bons de commande consolidés - {contract.subcontractor_id.name}</title>
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
    </style>
</head>
<body>
    <div class="page">
        <!-- En-tête avec logos -->
        <div style="display: flex; align-items: center; justify-content: center; padding: 25px 0; border-bottom: 3px solid #20B2AA; margin-bottom: 35px;">
            <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 70px; margin-right: 40px;"/>
            <div style="text-align: center;">
                <h1>🛒 Bons de commande consolidés</h1>
                <h2>Sous-traitant : {contract.subcontractor_id.name}</h2>
                <p style="color: #666; margin: 5px 0 0 0; font-size: 16px;">Détail consolidé des commandes pour tous les lots du contrat</p>
            </div>
            <img src="{blg_images['logo']}" alt="Logo BLG GROUPE" style="height: 70px; margin-left: 40px;"/>
        </div>
        
        <!-- Informations du chantier -->
        <div style="background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%); border-left: 5px solid #20B2AA; padding: 20px; margin-bottom: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(32, 178, 170, 0.1);">
            <h3>📋 Informations contractuelles</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div>
                    <p style="margin: 8px 0; font-weight: bold;"><strong>🏗️ Chantier :</strong> {contract.chantier_id.name}</p>
                    <p style="margin: 8px 0; font-weight: bold;"><strong>👷 Sous-traitant :</strong> {contract.subcontractor_id.name}</p>
                </div>
                <div>
                    <p style="margin: 8px 0; font-weight: bold;"><strong>📦 Nombre de lots :</strong> {len(contract.lot_ids)}</p>
                    <p style="margin: 8px 0; font-weight: bold;"><strong>📊 Nombre de commandes :</strong> {len(all_purchase_orders)}</p>
                </div>
            </div>
        </div>
        
        <!-- Liste consolidée des bons de commande -->
        <div style="margin-bottom: 35px;">
            <h3>📄 Détail consolidé des commandes contractuelles</h3>
            {orders_content}
        </div>
        
        <!-- Récapitulatif financier consolidé -->
        <div style="border: 3px solid #20B2AA; border-radius: 15px; padding: 25px; background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%); margin-bottom: 35px; box-shadow: 0 4px 12px rgba(32, 178, 170, 0.15);">
            <h3 style="text-align: center; margin: 0 0 20px 0; font-size: 24px; font-weight: bold;">💰 Récapitulatif financier consolidé</h3>
            <div style="text-align: center;">
                <p style="font-size: 20px; margin: 15px 0; font-weight: bold; color: #1a7a7a;">Montant total consolidé :</p>
                <p style="font-size: 28px; font-weight: bold; color: #20B2AA; margin: 0; text-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    {total_amount:,.2f} €
                </p>
            </div>
        </div>
        
        <!-- Note légale -->
        <div style="border-top: 2px solid #20B2AA; padding-top: 20px; font-size: 12px; color: #666; text-align: center; background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
            <p style="margin: 8px 0; font-weight: bold;">Les bons de commande ci-dessus constituent la base contractuelle consolidée des prestations à réaliser.</p>
            <p style="margin: 8px 0;">Tous les montants sont exprimés HT sauf mention contraire.</p>
            <p style="margin: 8px 0; font-style: italic;">Document contractuel consolidé - BLG GROUPE - Tous droits réservés</p>
        </div>
    </div>
</body>
</html>"""
