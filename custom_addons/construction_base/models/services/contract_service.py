# -*- coding: utf-8 -*-
"""
Service de génération de contrats de sous-traitance.
Génère des contrats PDF standardisés avec les informations du sous-traitant,
les prix et les règles spécifiques aux lots de chantier.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, timedelta
import base64

_logger = logging.getLogger(__name__)


class ContractService(models.AbstractModel):
    """Service de génération de contrats de sous-traitance."""
    
    _name = 'construction.contract.service'
    _description = 'Service de génération de contrats de sous-traitance'

    def generate_subcontractor_contract(self, chantier, subcontractor, lot_ids, contract_data):
        """
        Génère un contrat de sous-traitance.
        
        Args:
            chantier: construction.chantier
            subcontractor: res.partner (sous-traitant)
            lot_ids: construction.lot records
            contract_data: dict avec prix, délais, conditions
            
        Returns:
            construction.subcontractor.contract record
        """
        self.ensure_one()
        
        # Validation des données
        if not chantier or not subcontractor or not lot_ids:
            raise ValidationError(_("Données manquantes pour la génération du contrat."))
        
        # Créer le contrat
        contract_vals = self._prepare_contract_vals(chantier, subcontractor, lot_ids, contract_data)
        contract = self.env['construction.subcontractor.contract'].create(contract_vals)
        
        # Générer le PDF
        pdf_content = self._generate_contract_pdf(contract)
        contract.contract_pdf = base64.b64encode(pdf_content)
        contract.filename = f"Contrat_{subcontractor.name}_{chantier.name}.pdf"
        
        # Créer le lien portail
        portal_url = self._create_portal_link(contract)
        contract.portal_url = portal_url
        
        # Envoyer par email
        self._send_contract_email(contract)
        
        return contract

    def _prepare_contract_vals(self, chantier, subcontractor, lot_ids, contract_data):
        """Préparer les valeurs du contrat."""
        return {
            'chantier_id': chantier.id,
            'subcontractor_id': subcontractor.id,
            'lot_ids': [(6, 0, lot_ids.ids)],
            'contract_number': self._generate_contract_number(),
            'start_date': contract_data.get('start_date', fields.Date.today()),
            'end_date': contract_data.get('end_date'),
            'total_amount': contract_data.get('total_amount', 0.0),
            'payment_terms': contract_data.get('payment_terms', '30 jours'),
            'warranty_period': contract_data.get('warranty_period', 12),  # mois
            'insurance_required': contract_data.get('insurance_required', True),
            'state': 'draft',
            'notes': contract_data.get('notes', ''),
        }

    def _generate_contract_number(self):
        """Générer un numéro de contrat unique."""
        return f"CONTRACT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _generate_contract_pdf(self, contract):
        """Générer le PDF du contrat."""
        # Template HTML pour le contrat
        html_content = self._get_contract_template(contract)
        
        # Convertir en PDF (utiliser le service de rapport Odoo)
        pdf_content = self.env['ir.actions.report']._run_wkhtmltopdf(
            [html_content], 
            landscape=False,
            specific_paperformat_args={'data_only': True}
        )
        
        return pdf_content

    def _get_contract_template(self, contract):
        """Générer le template HTML du contrat."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Contrat de sous-traitance</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; font-size: 12px; }}
                .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }}
                .section {{ margin: 20px 0; }}
                .section h3 {{ color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px; }}
                .signature {{ margin-top: 50px; text-align: center; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .payment-schedule {{ margin: 20px 0; }}
                .payment-schedule table {{ width: 100%; }}
                .company-info {{ margin: 20px 0; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #007bff; }}
                .contract-details {{ margin: 20px 0; }}
                .conditions {{ margin: 20px 0; }}
                .conditions ol {{ padding-left: 20px; }}
                .conditions li {{ margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>CONTRAT DE SOUS-TRAITANCE</h1>
                <h2>N° {contract.contract_number}</h2>
            </div>
            
            <div class="company-info">
                <h3>Désignation des parties contractantes</h3>
                <p><strong>Contractant général :</strong></p>
                <p>L'entreprise</p>
                <p><strong>{contract.chantier_id.company_id.name}</strong></p>
                <p>{contract.chantier_id.company_id.street or ''}<br/>
                {contract.chantier_id.company_id.city or ''} {contract.chantier_id.company_id.zip or ''}</p>
                
                <p><strong>Sous-traitant :</strong></p>
                <p><strong>{contract.subcontractor_id.name}</strong></p>
                <p>{contract.subcontractor_id.street or ''}<br/>
                {contract.subcontractor_id.city or ''} {contract.subcontractor_id.zip or ''}</p>
                
                <p><strong>Montant :</strong> {contract.total_amount:,.2f} €</p>
                <p><strong>Chantier :</strong> {contract.chantier_id.name}</p>
            </div>
            
            <div class="section">
                <h3>1 - Désignation des prestations</h3>
                <p><strong>OPÉRATION :</strong> {contract.chantier_id.name}</p>
                <p><strong>MAÎTRE D'ŒUVRE :</strong> {contract.chantier_id.company_id.name}</p>
                <p><strong>NATURE DES TRAVAUX :</strong> {contract.chantier_id.description or 'Travaux de construction'}</p>
                <p><strong>LIEU D'EXÉCUTION :</strong> {contract.chantier_id.address}</p>
                <p><strong>NATURE DES PRESTATIONS, OBJET DE LA PRÉSENTE :</strong></p>
                <ul>
                    {''.join([f'<li>{lot.name} - {lot.price:,.2f} €</li>' for lot in contract.lot_ids])}
                </ul>
            </div>
            
            <div class="section">
                <h3>2 - Prix</h3>
                <p><strong>{contract.total_amount:,.2f} €</strong></p>
                <p>Le prix est ferme et non révisable. - « AUTOLIQUIDATION, article 242 nonies A de l'annexe II au code général des impôts.</p>
                <p>Ce prix comprend l'ensemble des coûts, frais et débours de l'Entreprise nécessaires à la bonne exécution du Contrat et dont l'appréciation relève de la seule responsabilité de l'Entreprise et couvre l'ensemble des aléas d'exécution des travaux.</p>
                <p>Le prix constitue l'intégralité de la rémunération due par {contract.chantier_id.company_id.name} à l'Entreprise, laquelle ne saurait prétendre à aucun supplément de prix en raison de prestations qui, bien que non expressément énumérées, entrent dans le cadre de ses obligations contractuelles.</p>
            </div>
            
            <div class="section">
                <h3>3 - Échéancier de paiement</h3>
                <p>Le prix est payable selon l'échéancier suivant :</p>
                <div class="payment-schedule">
                    <table>
                        <thead>
                            <tr>
                                <th>Avancement réel chantier</th>
                                <th>Facturation</th>
                                <th>Montant en € HT = TTC</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>30%</td>
                                <td>30%</td>
                                <td>{contract.total_amount * 0.3:,.2f}</td>
                            </tr>
                            <tr>
                                <td>100%</td>
                                <td>70%</td>
                                <td>{contract.total_amount * 0.7:,.2f}</td>
                            </tr>
                            <tr>
                                <td><strong>TOTAL</strong></td>
                                <td><strong>100%</strong></td>
                                <td><strong>{contract.total_amount:,.2f} €</strong></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <p>La gestion financière est assurée depuis un compte tiers sécurisé. La signature du PV de réception par le MAITRE D'OUVRAGE, qui atteste que les travaux ont été réalisés conformément au cahier des charges, permet la libération des fonds vers notre partenaire travaux (le sous-traitant) a maximum J+30 après réception des travaux.</p>
            </div>
            
            <div class="section">
                <h3>4 – Délais</h3>
                <p>Suivant planning prévisionnel en annexe, tout planning remis par {contract.chantier_id.company_id.name} en cours d'exécution du marché aura valeur contractuelle.</p>
                <p><strong>Date de début :</strong> {contract.start_date}</p>
                <p><strong>Date de fin :</strong> {contract.end_date or 'À définir selon planning'}</p>
            </div>
            
            <div class="section">
                <h3>5 – Documents contractuels et annexes</h3>
                <p>1) La présente commande et le cas échéant ses annexes, à savoir, par ordre de préséance :</p>
                <ul>
                    <li>Les documents graphiques : plans d'exécution du projet.</li>
                    <li>La notice technique : dossier d'exécution et planning du projet.</li>
                    <li>Le bon de commande (Les quantités et prestations y figurant sont estimatives et ne sauraient être exploitées pour remettre en cause de quelque manière que ce soit le caractère forfaitaire du marché. Elle n'est pas contractuelle mais sert de base pour fixer les prix de travaux modificatifs et dresser les situations de travaux et décomptes)</li>
                </ul>
                <p>2) Les « conditions générales de commande » jointes</p>
            </div>
            
            <div class="section">
                <h3>6 – Documents à transmettre à {contract.chantier_id.company_id.name}</h3>
                <p>Le prestataire remet, à la signature de la présente commande et tous les 6 mois :</p>
                <ul>
                    <li>Un extrait K bis</li>
                    <li>Une Attestation de fourniture des déclarations sociales et de paiement des cotisations de sécurité sociales émanant de l'organisme de protection sociale chargé du recouvrement portant le nombre de salariés déclarés datant de moins de 3 mois.</li>
                    <li>La liste nominative de ses salariés étrangers soumis à autorisation de travail auxquels il fera appel pour l'exécution de cette commande accompagnée de l'attestation conforme au décret 2007-801 du 11/05/2007.</li>
                    <li>Une attestation (datant de moins de trois mois) d'assurance responsabilité civile professionnelle et décennale à l'égard de tous tiers, y compris l'entreprise, valable tant pendant la durée des prestations qu'après leur achèvement</li>
                </ul>
            </div>
            
            <div class="section">
                <h3>7 – Validité</h3>
                <p>Cette commande est nulle si elle n'est pas retournée acceptée, accompagnée des documents demandés dans les 5 jours à compter de sa réception par le prestataire, à moins que ce dernier n'ait commencé à exécuter les prestations objet de la présente, auquel cas ce commencement d'exécution vaut acceptation sans réserve par le prestataire de la présente commande.</p>
            </div>
            
            <div class="signature">
                <p>Fait à _____________, le {fields.Date.today()}</p>
                <br><br>
                <p>Signature du maître d'ouvrage : _________________</p>
                <br><br>
                <p>Signature du sous-traitant : _________________</p>
            </div>
            
            <div class="conditions">
                <h3>CONDITIONS GÉNÉRALES DE COMMANDE</h3>
                
                <ol>
                    <li><strong>Conditions d'achat</strong><br/>
                    Toutes les conditions générales de vente du prestataire figurant sur ses lettres, avis de réception, devis, factures, bordereaux, ... ne peuvent être admises sans le consentement écrit de l'entreprise. Toute modification éventuelle de la présente commande n'est opposable au contractant général que si elle fait l'objet d'un accord écrit de celui-ci. Toute cession ou sous-traitance de la présente commande est inopposable au contractant général sauf accord écrit préalable de celui-ci. Dans tous les cas l'entreprise restera seule responsable envers le contractant général.</li>
                    
                    <li><strong>Règlementation du travail - Hygiène et sécurité</strong><br/>
                    L'entreprise fait son affaire personnelle, sans recours contre le contractant général, de toutes les obligations auxquelles sont tenues les entreprises en matière de protection de la santé, de sécurité et d'environnement. Elle est seule responsable de la sécurité, de quelque façon que ce soit, de tout intervenant sur le chantier.</li>
                    
                    <li><strong>Matériel et outillage</strong><br/>
                    Le matériel et l'outillage nécessaires à l'exécution des prestations confiées à l'entreprise sont à la charge de cette dernière. La maintenance durant toute la durée de l'utilisation ainsi que la garde, le contrôle et la surveillance sont à la charge de l'entreprise.</li>
                    
                    <li><strong>Obligations diverses de l'entreprise</strong><br/>
                    4.1 - Étendue du contrat<br/>
                    L'entreprise reconnaît avoir préalablement pris connaissance des documents et mené les investigations nécessaires pour accomplir sa mission. Dans le cadre de son forfait, elle mettra en œuvre tous les moyens nécessaires (matériels, personnels, ...) à cet effet.</li>
                    
                    <li><strong>Délais et pénalités de retard</strong><br/>
                    5.1 Retenues sur situations mensuelles et/ou décompte définitif<br/>
                    Les prestations doivent être exécutées dans les conditions de délai indiquées dans la Commande. Le respect des délais prévus au planning contractuel constitue une obligation essentielle de l'entreprise qui s'engage à respecter tant les dates de démarrage et de terminaison que les délais intermédiaires correspondant aux différents ouvrages ou tâches composant ses travaux.</li>
                    
                    <li><strong>Modalités de règlement</strong><br/>
                    6.1. Modalités de paiement du bon de commande initial<br/>
                    Le règlement sera effectué par virement bancaire suivant l'échéancier de paiement sous réserve de l'adéquation de celui-ci avec l'avancement réel du chantier.</li>
                    
                    <li><strong>Garanties, responsabilités et assurances</strong><br/>
                    L'entreprise fait son affaire de toute réclamation concernant l'utilisation de brevets ou de licences, de sorte que le contractant général ne puisse être recherchée, ni les prestations arrêtées ou interrompues. Elle s'oblige à souscrire une police d'assurance couvrant le risque de responsabilité civile professionnelle et décennale à l'égard de tout tiers, y compris l'entreprise, avec une garantie suffisante pour la nature et l'importance du risque correspondant aux prestations qui lui sont confiées.</li>
                    
                    <li><strong>Résiliation</strong><br/>
                    La présente commande peut être résiliée au bénéfice du contractant général, après mise en demeure restée infructueuse pendant 8 jours pour inexécution par l'entreprise d'une de ses obligations contractuelles et ce, sans préjudice des dommages-intérêts.</li>
                    
                    <li><strong>Règlement des litiges</strong><br/>
                    Tout différend, quelles qu'en soient la nature et la date de survenance, relatif à l'interprétation, l'exécution ou la résiliation de la présente commande, et qui n'aurait pu trouver de solution amiable, sera soumis à l'appréciation des tribunaux de Paris. En cas de litige, la loi applicable sera la loi française.</li>
                    
                    <li><strong>Réception</strong><br/>
                    10.1 Préparation à la réception<br/>
                    L'exécution des travaux doit aboutir à la livraison au Maître d'Ouvrage au jour de la réception, d'un ouvrage achevé dans les conditions de qualité prévues par les DTU ou les règles de l'art.</li>
                </ol>
            </div>
            
            <div class="section">
                <h3>11 - Relations entre parties</h3>
                <p>Préalablement à la production de ce bon de commande, le MAITRE D'OUVRAGE, que vous avez rencontré lors d'une réunion, a signé le contrat de construction le liant à {contract.chantier_id.company_id.name} et a, de fait, agréé votre entreprise comme sous-traitant.</p>
            </div>
        </body>
        </html>
        """

    def _create_portal_link(self, contract):
        """Créer le lien vers le portail web."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/my/contract/{contract.id}"

    def _send_contract_email(self, contract):
        """Envoyer le contrat par email avec lien vers le portail."""
        template = self.env.ref('construction_base.email_template_subcontractor_contract', raise_if_not_found=False)
        
        if template:
            template.send_mail(contract.id, force_send=True)
        else:
            # Email par défaut si pas de template
            self._send_default_contract_email(contract)

    def _send_default_contract_email(self, contract):
        """Envoyer un email par défaut avec le contrat."""
        subject = f"Contrat de sous-traitance - {contract.chantier_id.name}"
        body = f"""
        Bonjour {contract.subcontractor_id.name},
        
        Veuillez trouver ci-joint votre contrat de sous-traitance pour le chantier {contract.chantier_id.name}.
        
        Vous pouvez également consulter et signer le contrat en ligne : {contract.portal_url}
        
        Cordialement,
        {contract.chantier_id.company_id.name}
        """
        
        # Envoyer l'email
        self.env['mail.mail'].create({
            'subject': subject,
            'body_html': body,
            'email_from': contract.chantier_id.company_id.email,
            'email_to': contract.subcontractor_id.email,
            'attachment_ids': [(6, 0, [contract.contract_pdf.id])] if contract.contract_pdf else [],
        }).send() 