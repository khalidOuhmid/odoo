from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class LotDocumentWizard(models.TransientModel):
    _name = 'lot.document.wizard'
    _description = 'Gestion des documents du lot'

    lot_id = fields.Many2one('construction.lot', string='Lot', required=True, readonly=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, readonly=True)
    subcontractor_id = fields.Many2one('res.partner', string='Sous-traitant', required=True, readonly=True)

    # Documents existants
    document_cctp = fields.Binary(string="CCTP", attachment=True)
    document_subcontractor_contract = fields.Binary(string="Contrat de sous-traitance", attachment=True)
    
    # Nouveaux champs pour les plannings
    document_general_planning = fields.Binary(string="Planning général", attachment=True)
    document_subcontractor_planning = fields.Binary(string="Planning du sous-traitant", attachment=True)
    
    # Champs pour la preview du contrat
    preview_contract_pdf = fields.Binary(string="Aperçu contrat", readonly=True)
    preview_filename = fields.Char(string="Nom fichier preview", readonly=True)
    preview_html = fields.Html(string="Aperçu HTML", readonly=True)
    show_preview = fields.Boolean(string="Afficher preview", default=False)

    # Champs modifiables pour les informations du contrat
    company_name = fields.Char(string="Nom de l'entreprise", default="BLG GROUPE")
    company_street = fields.Char(string="Rue de l'entreprise", default="44 RUE COMMANDERIE DES TEMPLIERS")
    company_city = fields.Char(string="Ville de l'entreprise", default="AMBARES-ET-LAGRAVE")
    company_zip = fields.Char(string="Code postal de l'entreprise", default="33440")
    
    subcontractor_name = fields.Char(string="Nom du sous-traitant")
    subcontractor_vat = fields.Char(string="SIREN du sous-traitant")
    
    chantier_name = fields.Char(string="Nom du chantier")
    chantier_description = fields.Text(string="Description du chantier")
    chantier_address = fields.Text(string="Adresse du chantier")
    
    specialty_description = fields.Char(string="Nature des prestations")
    total_amount = fields.Float(string="Montant total", digits=(16, 2))
    po_references = fields.Char(string="Références des bons de commande", default="À définir")
    
    # Échéancier de paiement
    payment_schedule_30_percent = fields.Float(string="Acompte 30%", digits=(16, 2))
    payment_schedule_70_percent = fields.Float(string="Solde 70%", digits=(16, 2))

    @api.onchange('total_amount')
    def _onchange_total_amount(self):
        """Recalcule automatiquement l'échéancier de paiement quand le montant total change"""
        if self.total_amount:
            self.payment_schedule_30_percent = self.total_amount * 0.30
            self.payment_schedule_70_percent = self.total_amount * 0.70

    def default_get(self, fields_list):
        """Initialise les valeurs par défaut du wizard"""
        res = super().default_get(fields_list)
        
        # Récupérer les IDs depuis le contexte
        lot_id = self.env.context.get('default_lot_id')
        chantier_id = self.env.context.get('default_chantier_id')
        subcontractor_id = self.env.context.get('default_subcontractor_id')
        
        if lot_id:
            lot = self.env['construction.lot'].browse(lot_id)
            chantier = lot.chantier_id
            subcontractor = lot.subcontractor_ids[0] if lot.subcontractor_ids else False
            
            res.update({
                'lot_id': lot_id,
                'chantier_id': lot.chantier_id.id,
                'subcontractor_id': subcontractor.id if subcontractor else False,
            })
            
            # Initialiser les champs modifiables avec les valeurs des modèles
            if chantier:
                res.update({
                    'chantier_name': chantier.name or "Chantier non défini",
                    'chantier_description': chantier.description or "Description non définie",
                    'chantier_address': chantier.address or "Adresse non définie",
                })
            
            if subcontractor:
                res.update({
                    'subcontractor_name': subcontractor.name or "Sous-traitant non défini",
                    'subcontractor_vat': subcontractor.vat or "Non défini",
                })
            
            res.update({
                'specialty_description': lot.name or "Lot non défini",
                'total_amount': lot.price or 0.0,
                'payment_schedule_30_percent': (lot.price or 0.0) * 0.30,
                'payment_schedule_70_percent': (lot.price or 0.0) * 0.70,
            })
            
            # Récupérer les documents existants du lot
            if hasattr(lot, 'document_cctp') and lot.document_cctp:
                res['document_cctp'] = lot.document_cctp
            if hasattr(lot, 'document_subcontractor_contract') and lot.document_subcontractor_contract:
                res['document_subcontractor_contract'] = lot.document_subcontractor_contract
            if hasattr(lot, 'document_general_planning') and lot.document_general_planning:
                res['document_general_planning'] = lot.document_general_planning
            if hasattr(lot, 'document_subcontractor_planning') and lot.document_subcontractor_planning:
                res['document_subcontractor_planning'] = lot.document_subcontractor_planning
        
        if chantier_id:
            res['chantier_id'] = chantier_id
            
        if subcontractor_id:
            res['subcontractor_id'] = subcontractor_id
        
        # Gérer l'affichage de la preview
        if self.env.context.get('show_preview'):
            preview_html = self.env.context.get('default_preview_html', '')
            res.update({
                'preview_html': preview_html,
                'show_preview': True,
            })
        
        return res

    def _get_payment_schedule(self):
        """Calcule l'échéancier de paiement basé sur le prix du lot"""
        if not self.lot_id or not self.lot_id.price:
            return []
        
        total_price = self.lot_id.price
        return [
            {'percentage': 30, 'amount': total_price * 0.3},
            {'percentage': 70, 'amount': total_price * 0.7},
        ]

    def action_save_documents(self):
        self.ensure_one()
        lot = self.lot_id
        vals = {}
        if self.document_cctp:
            vals['document_cctp'] = self.document_cctp
        if self.document_subcontractor_contract:
            vals['document_subcontractor_contract'] = self.document_subcontractor_contract
        if self.document_general_planning:
            vals['document_general_planning'] = self.document_general_planning
        if self.document_subcontractor_planning:
            vals['document_subcontractor_planning'] = self.document_subcontractor_planning
        if vals:
            lot.write(vals)
        return {'type': 'ir.actions.act_window_close'}

    def action_send_contract_email(self):
        self.ensure_one()
        # On suppose que le lot a un sous-traitant principal
        partner = self.subcontractor_id
        chantier = self.chantier_id
        if not partner:
            raise ValidationError("Aucun sous-traitant assigné à ce lot.")
        # On utilise l'action du chantier pour envoyer l'email
        chantier.action_send_contract_to_subcontractor()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Email envoyé',
                'message': 'L\'email de dépôt a été envoyé au sous-traitant.',
                'type': 'success',
            }
        }

    def action_generate_contract(self):
        """Génère le contrat final et le sauvegarde"""
        self.ensure_one()
        
        _logger.info(f"Début génération contrat pour lot {self.lot_id.name}")
        
        # Vérifications préliminaires
        if not self.subcontractor_id:
            raise ValidationError("Aucun sous-traitant assigné à ce lot.")
        
        if not self.chantier_id:
            raise ValidationError("Aucun chantier associé à ce lot.")
        
        _logger.info(f"Vérifications OK - Sous-traitant: {self.subcontractor_id.name}, Chantier: {self.chantier_id.name}")
        
        # Générer le PDF du contrat
        try:
            pdf_content = self._generate_contract_pdf()
            _logger.info(f"PDF généré avec succès, taille: {len(pdf_content)} bytes")
        except Exception as e:
            _logger.error(f"Erreur génération PDF: {e}")
            raise ValidationError(f"Erreur lors de la génération du PDF: {str(e)}")
        
        # Encoder le contenu PDF en base64
        pdf_base64 = base64.b64encode(pdf_content)
        
        # Sauvegarder le document généré
        filename = f"Contrat_{self.lot_id.name}_{self.subcontractor_id.name}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': pdf_base64,
            'res_model': 'construction.lot',
            'res_id': self.lot_id.id,
            'mimetype': 'application/pdf',
        })
        
        _logger.info(f"Attachment créé: {attachment.id}")
        
        # Mettre à jour le wizard avec le document généré
        self.document_subcontractor_contract = pdf_base64
        
        # Mettre à jour le lot directement avec le contrat généré
        self.lot_id.write({
            'document_subcontractor_contract': pdf_base64,
        })
        
        _logger.info(f"Lot mis à jour avec le contrat généré")
        
        # Rafraîchir la vue pour montrer le contrat généré
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gérer les documents du lot',
            'res_model': 'lot.document.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_lot_id': self.lot_id.id,
                'default_chantier_id': self.chantier_id.id,
                'default_subcontractor_id': self.subcontractor_id.id,
            }
        }

    def action_preview_contract(self):
        """Génère une preview HTML du contrat de sous-traitance"""
        self.ensure_one()
        
        # Vérifications préliminaires
        if not self.subcontractor_id:
            raise ValidationError("Aucun sous-traitant assigné à ce lot.")
        
        if not self.chantier_id:
            raise ValidationError("Aucun chantier associé à ce lot.")
        
        # Générer le HTML de preview
        html_content = self._get_contract_html()
        
        # Créer un fichier HTML avec les styles appropriés
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Aperçu du contrat de sous-traitance</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .table th {{ background-color: #f2f2f2; }}
                h1, h2, h3 {{ color: #333; }}
                .page-break {{ page-break-before: always; }}
                @media print {{
                    .no-print {{ display: none; }}
                }}
                .controls {{ margin-bottom: 20px; padding: 10px; background-color: #f9f9f9; border: 1px solid #ddd; }}
                .controls button {{ margin-right: 10px; padding: 8px 16px; cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="controls no-print">
                <button onclick="window.print()">Imprimer</button>
                <button onclick="window.close()">Fermer</button>
                <span style="margin-left: 20px; color: #666;">Aperçu du contrat de sous-traitance</span>
            </div>
            {html_content}
        </body>
        </html>
        """
        
        # Encoder le HTML en base64
        import base64
        html_encoded = base64.b64encode(full_html.encode('utf-8'))
        
        # Mettre à jour le wizard avec la preview
        self.write({
            'preview_contract_pdf': html_encoded,
            'preview_filename': f"Preview_Contrat_{self.subcontractor_id.name}_{self.chantier_id.name}.html"
        })
        
        # Retourner une action pour télécharger le fichier HTML
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=preview_contract_pdf&filename={self.preview_filename}&download=true',
            'target': 'new',
        }

    def action_show_html_preview(self):
        """Affiche le HTML du contrat dans une nouvelle fenêtre"""
        self.ensure_one()
        
        html_content = self._get_contract_html()
        
        # Encoder le HTML en base64 pour l'URL
        import base64
        html_encoded = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/static/src/html/preview_contract.html?content={html_encoded}',
            'target': 'new',
        }

    def action_download_preview(self):
        """Télécharge la preview HTML du contrat"""
        self.ensure_one()
        
        html_content = self._get_contract_html()
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=preview_contract_pdf&filename=preview_contract.html&download=true',
            'target': 'self',
        }

    def action_show_preview_popup(self):
        """Affiche l'aperçu HTML du contrat dans une popup"""
        self.ensure_one()
        
        # Générer l'aperçu HTML avec les valeurs actuelles
        try:
            html_content = self._get_contract_html()
            self.preview_html = html_content
        except Exception as e:
            _logger.error(f"Erreur lors de la génération de l'aperçu: {e}")
            self.preview_html = f"<div class='alert alert-danger'>Erreur lors de la génération de l'aperçu: {str(e)}</div>"
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Aperçu du contrat',
            'res_model': 'lot.document.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('construction_base.view_lot_document_wizard_preview').id,
            'target': 'new',
            'context': {'show_preview': True}
        }

    def action_refresh_preview(self):
        """Rafraîchit l'aperçu HTML avec les valeurs modifiées"""
        self.ensure_one()
        
        try:
            html_content = self._get_contract_html()
            self.preview_html = html_content
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aperçu mis à jour',
                    'message': 'L\'aperçu du contrat a été mis à jour avec les nouvelles valeurs.',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Erreur lors de la mise à jour de l'aperçu: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': f'Erreur lors de la mise à jour de l\'aperçu: {str(e)}',
                    'type': 'danger',
                }
            }

    def _generate_contract_pdf(self):
        """Génère le PDF du contrat avec le format exact fourni"""
        # Créer le HTML du contrat selon le format exact
        html_content = self._get_contract_html()
        
        # Convertir en PDF avec les bonnes options
        try:
            pdf_content = self.env['ir.actions.report']._run_wkhtmltopdf(
                [html_content], 
                landscape=False,
                specific_paperformat_args={
                    'data_only': True,
                    'margin_top': 20,
                    'margin_bottom': 20,
                    'margin_left': 20,
                    'margin_right': 20,
                }
            )
        except Exception as e:
            # Fallback si wkhtmltopdf échoue
            _logger.error(f"Erreur génération PDF: {e}")
            # Créer un PDF simple avec reportlab
            pdf_content = self._create_simple_pdf()
        
        return pdf_content

    def _create_simple_pdf(self):
        """Créer un PDF simple en cas d'échec de wkhtmltopdf"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from io import BytesIO
            
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            
            # Titre
            p.setFont("Helvetica-Bold", 16)
            p.drawString(2*cm, 27*cm, "CONTRAT DE SOUS-TRAITANCE")
            
            # Informations de base
            p.setFont("Helvetica", 12)
            p.drawString(2*cm, 25*cm, f"Chantier: {self.chantier_id.name}")
            p.drawString(2*cm, 24*cm, f"Sous-traitant: {self.subcontractor_id.name}")
            p.drawString(2*cm, 23*cm, f"Montant: {self.lot_id.price:,.0f} €")
            
            p.save()
            return buffer.getvalue()
        except Exception as e:
            _logger.error(f"Erreur création PDF simple: {e}")
            return b""

    def _get_contract_html(self):
        """Génère le HTML du contrat de sous-traitance"""
        self.ensure_one()
        
        _logger.info(f"Génération HTML contrat pour lot {self.lot_id.name}")
        
        # Utiliser les valeurs des champs modifiables du wizard
        company_name = self.company_name or "BLG GROUPE"
        company_street = self.company_street or "44 RUE COMMANDERIE DES TEMPLIERS"
        company_city = self.company_city or "AMBARES-ET-LAGRAVE"
        company_zip = self.company_zip or "33440"
        
        # Récupérer les données du sous-traitant depuis les champs modifiables
        subcontractor_name = self.subcontractor_name or "Sous-traitant non défini"
        subcontractor_vat = self.subcontractor_vat or "Non défini"
        
        # Récupérer les données du chantier depuis les champs modifiables
        chantier_name = self.chantier_name or "Chantier non défini"
        chantier_description = self.chantier_description or "Description non définie"
        chantier_address = self.chantier_address or "Adresse non définie"
        
        # Récupérer les données du lot depuis les champs modifiables
        specialty_description = self.specialty_description or "Lot non défini"
        total_amount = self.total_amount or 0.0
        if total_amount is None:
            total_amount = 0.0
        
        # Références des bons de commande
        po_references = self.po_references or "À définir"
        
        # Date actuelle
        current_date = fields.Date.today().strftime('%d/%m/%Y')
        
        # Échéancier de paiement depuis les champs modifiables
        echeancier_ids = [
            {
                'avancement': '30%',
                'facturation': 'Acompte',
                'montant': self.payment_schedule_30_percent or (total_amount * 0.30)
            },
            {
                'avancement': '100%',
                'facturation': 'Solde',
                'montant': self.payment_schedule_70_percent or (total_amount * 0.70)
            }
        ]
        
        # Créer un objet factice pour le template
        class ContractObject:
            def __init__(self, data, env):
                for key, value in data.items():
                    setattr(self, key, value)
                self._name = 'contract.object'
                self.id = 1
                self.env = env
                self.name = "Contrat de sous-traitance"
        
        # Préparer les données pour le template
        contract_data = ContractObject({
            'company_name': company_name,
            'company_street': company_street,
            'company_city': company_city,
            'company_zip': company_zip,
            'subcontractor_name': subcontractor_name,
            'subcontractor_vat': subcontractor_vat,
            'chantier_name': chantier_name,
            'chantier_description': chantier_description,
            'chantier_address': chantier_address,
            'specialty_description': specialty_description,
            'total_amount': total_amount,
            'po_references': po_references,
            'current_date': current_date,
            'echeancier_ids': echeancier_ids,
        }, self.env)
        
        _logger.info(f"Données préparées: {contract_data}")
        _logger.info(f"Lot: {specialty_description}, Prix: {total_amount}, Sous-traitant: {subcontractor_name}")
        _logger.info(f"Chantier: {chantier_name}, Adresse: {chantier_address}")
        
        # Wrapper les données dans une liste 'docs' comme attendu par le template
        template_data = {
            'docs': [contract_data],
            'company': self.env.company,
            'o': contract_data,
        }
        
        _logger.info(f"Template data préparé: {template_data}")
        
        try:
            # Rendre le template
            html_content = self.env['ir.ui.view']._render_template(
                'construction_base.contrat_sous_traitance_template',
                template_data
            )
            _logger.info(f"HTML généré avec succès, taille: {len(html_content)}")
            return html_content
        except Exception as e:
            _logger.error(f"Erreur lors du rendu du template: {e}")
            raise ValidationError(f"Erreur lors de la génération du contrat: {str(e)}")

    def _get_subcontractor_specialty(self):
        """Détermine la spécialité du sous-traitant basée sur le lot et les informations disponibles"""
        lot = self.lot_id
        subcontractor = self.subcontractor_id
        
        # Déterminer la spécialité basée sur le nom du lot
        lot_name_lower = lot.name.lower() if lot.name else ''
        
        # Spécialités disponibles
        specialties = {
            'électricité': {
                'code': '43.21Z',
                'name': 'Installation électrique',
                'description': 'Installation électrique, mise aux normes, tableaux électriques, éclairage, prises, interrupteurs, câblage, mise en conformité électrique, installation domotique, sécurité électrique.'
            },
            'électrique': {
                'code': '43.21Z',
                'name': 'Installation électrique',
                'description': 'Installation électrique, mise aux normes, tableaux électriques, éclairage, prises, interrupteurs, câblage, mise en conformité électrique, installation domotique, sécurité électrique.'
            },
            'plomberie': {
                'code': '43.22Z',
                'name': 'Installation d\'eau et de gaz',
                'description': 'Installation sanitaire, plomberie, chauffage, climatisation, ventilation, installation d\'eau chaude et froide, évacuation, raccordement gaz, maintenance plomberie.'
            },
            'peinture': {
                'code': '43.34Z',
                'name': 'Travaux de peinture et vitrerie',
                'description': 'Travaux de peinture intérieure et extérieure, revêtements muraux, enduits, ravalement, vitrerie, pose de vitres, rénovation peinture, décoration.'
            },
            'maçonnerie': {
                'code': '43.11Z',
                'name': 'Démolition et préparation de terrain',
                'description': 'Maçonnerie, béton, fondations, murs, cloisons, dalles, terrassement, gros œuvre, construction, rénovation structurelle.'
            },
            'carrelage': {
                'code': '43.32Z',
                'name': 'Installation de revêtements de sols et murs',
                'description': 'Pose de carrelage, faïence, parquet, sols souples, revêtements muraux, joints, étanchéité, finitions sols et murs.'
            },
            'menuiserie': {
                'code': '43.33Z',
                'name': 'Installation de portes et fenêtres',
                'description': 'Pose de portes, fenêtres, escaliers, placards, menuiserie intérieure et extérieure, fermetures, serrurerie, quincaillerie.'
            },
            'isolation': {
                'code': '43.39Z',
                'name': 'Autres installations pour les bâtiments',
                'description': 'Isolation thermique et acoustique, laine minérale, polystyrène, ouate de cellulose, isolation toiture, murs, combles, étanchéité.'
            },
            'couverture': {
                'code': '43.12Z',
                'name': 'Installation de toitures',
                'description': 'Couverture, toiture, charpente, zinguerie, gouttières, chéneaux, étanchéité toiture, réparation toiture.'
            }
        }
        
        # Chercher la spécialité dans le nom du lot
        for keyword, specialty in specialties.items():
            if keyword in lot_name_lower:
                return specialty
        
        # Si pas trouvé, chercher dans les spécialités du sous-traitant
        if hasattr(subcontractor, 'lot_ids') and subcontractor.lot_ids:
            for lot_specialty in subcontractor.lot_ids:
                lot_specialty_name = lot_specialty.name.lower() if lot_specialty.name else ''
                for keyword, specialty in specialties.items():
                    if keyword in lot_specialty_name:
                        return specialty
        
        # Par défaut, retourner une spécialité générique
        return {
            'code': '43.99Z',
            'name': 'Autres travaux de construction spécialisés',
            'description': 'Travaux de construction spécialisés, rénovation, aménagement, finitions, travaux divers selon les besoins du chantier.'
        }
