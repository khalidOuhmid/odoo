# -*- coding: utf-8 -*-
"""
Wizard pour générer un contrat unifié pour un sous-traitant sur plusieurs lots
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MultiLotContractWizard(models.TransientModel):
    _name = 'construction.multi.lot.contract.wizard'
    _description = 'Génération de contrat unifié pour plusieurs lots'

    # =================== CHAMPS PRINCIPAUX ===================
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True
    )
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        readonly=True,
        domain="[('supplier_rank', '>', 0)]"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots concernés',
        required=True,
        readonly=True,
        help="Lots du sous-traitant sélectionné"
    )
    
    # =================== INFORMATIONS CALCULÉES ===================
    
    total_amount = fields.Monetary(
        string='Montant total',
        compute='_compute_totals',
        currency_field='currency_id',
        help="Montant total des lots sélectionnés"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    lot_count = fields.Integer(
        string='Nombre de lots',
        compute='_compute_totals'
    )
    
    # =================== DOCUMENTS DISPONIBLES ===================
    
    available_documents = fields.Html(
        string='Documents disponibles',
        compute='_compute_available_documents',
        help="Récapitulatif des documents disponibles pour chaque lot"
    )
    
    # =================== CONFIGURATION CONTRAT ===================
    
    contract_start_date = fields.Date(
        string='Date de début du contrat',
        required=True,
        default=fields.Date.today
    )
    
    contract_end_date = fields.Date(
        string='Date de fin du contrat'
    )
    
    payment_terms = fields.Selection([
        ('30_days', '30 jours'),
        ('45_days', '45 jours'),
        ('60_days', '60 jours'),
        ('end_of_work', 'Fin des travaux'),
    ], string='Conditions de paiement', default='30_days')
    
    warranty_period = fields.Integer(
        string='Garantie (mois)',
        default=12
    )
    
    insurance_required = fields.Boolean(
        string='Assurance requise',
        default=True
    )
    
    contract_notes = fields.Text(
        string='Notes contractuelles',
        help="Notes additionnelles pour le contrat"
    )
    
    # Code URSSAF
    urssaf_code = fields.Selection([
        ('41.20Z', '41.20Z - Construction de bâtiments résidentiels et non résidentiels'),
        ('42.11Z', '42.11Z - Construction de routes et autoroutes'),
        ('43.11Z', '43.11Z - Travaux de démolition'),
        ('43.12A', '43.12A - Travaux de terrassement courants et travaux préparatoires'),
        ('43.21A', '43.21A - Travaux d\'installation électrique dans tous locaux'),
        ('43.21B', '43.21B - Travaux d\'installation électrique sur la voie publique'),
        ('43.22A', '43.22A - Travaux d\'installation d\'eau et de gaz en tous locaux'),
        ('43.22B', '43.22B - Travaux d\'installation d\'équipements thermiques et de climatisation'),
        ('43.29A', '43.29A - Travaux d\'isolation'),
        ('43.31Z', '43.31Z - Travaux de plâtrerie'),
        ('43.32A', '43.32A - Travaux de menuiserie bois et PVC'),
        ('43.32B', '43.32B - Travaux de menuiserie métallique et serrurerie'),
        ('43.33Z', '43.33Z - Travaux de revêtement des sols et des murs'),
        ('43.34Z', '43.34Z - Travaux de peinture et vitrerie'),
        ('43.91A', '43.91A - Travaux de charpente'),
        ('43.91B', '43.91B - Travaux de couverture par éléments'),
        ('43.99A', '43.99A - Travaux d\'étanchéification'),
        ('43.99B', '43.99B - Travaux de montage de structures métalliques'),
        ('43.99C', '43.99C - Travaux de maçonnerie générale et gros œuvre de bâtiment'),
        ('43.99D', '43.99D - Autres travaux de construction spécialisés'),
        ('81.22Z', '81.22Z - Autres activités de nettoyage des bâtiments et nettoyage industriel'),
        ('81.30Z', '81.30Z - Services d\'aménagement paysager'),
    ], string='Code URSSAF', default='43.34Z')
    
    # =================== OPTIONS DE GÉNÉRATION ===================
    
    send_email = fields.Boolean(
        string='Envoyer par email',
        default=True,
        help="Envoyer le contrat par email au sous-traitant"
    )
    
    auto_send = fields.Boolean(
        string='Envoi automatique après signature',
        default=False,
        help="Envoi automatique des documents après signature électronique"
    )
    
    # =================== CONTRAT GÉNÉRÉ ===================
    
    generated_contract_id = fields.Many2one(
        'construction.subcontractor.contract',
        string='Contrat généré',
        readonly=True
    )
    
    contract_generated = fields.Boolean(
        string='Contrat généré',
        default=False
    )

    # =================== OPTIONS D'INCLUSION DES PIÈCES ===================

    include_cctp = fields.Boolean(string="Inclure CCTP", default=True)
    include_general_planning = fields.Boolean(string="Inclure planning général", default=True)
    include_subcontractor_planning = fields.Boolean(string="Inclure planning sous-traitant", default=True)
    include_purchase_orders = fields.Boolean(string="Inclure bons de commande", default=True)

    # =================== APERÇU ===================

    preview_html = fields.Html(string='Aperçu', readonly=True)
    preview_ready = fields.Boolean(string='Aperçu généré', default=False)
    
    # =================== COMPUTED FIELDS ===================
    
    @api.depends('lot_ids')
    def _compute_totals(self):
        """Calcule les totaux des lots sélectionnés."""
        for wizard in self:
            if wizard.lot_ids:
                wizard.lot_count = len(wizard.lot_ids)
                wizard.total_amount = sum(
                    lot.price or lot.price_from_quote or 0.0 
                    for lot in wizard.lot_ids
                )
            else:
                wizard.lot_count = 0
                wizard.total_amount = 0.0
    
    @api.depends('lot_ids', 'subcontractor_id')
    def _compute_available_documents(self):
        """Génère le récapitulatif des documents disponibles."""
        for wizard in self:
            if not wizard.lot_ids:
                wizard.available_documents = "<p>Aucun lot sélectionné</p>"
                continue
            
            html_parts = ["<div class='document_summary'>"]
            html_parts.append("<h4>📋 Récapitulatif des documents disponibles</h4>")
            
            for lot in wizard.lot_ids:
                html_parts.append(f"<div class='lot_documents' style='margin-bottom: 20px; padding: 15px; border: 1px solid #e9ecef; border-radius: 8px;'>")
                html_parts.append(f"<h5 style='color: #20B2AA; margin-bottom: 10px;'>📦 {lot.name}</h5>")
                
                # Documents du lot
                documents = []
                if hasattr(lot, 'document_cctp') and lot.document_cctp:
                    documents.append("✅ CCTP")
                else:
                    documents.append("❌ CCTP")
                
                if hasattr(lot, 'document_general_planning') and lot.document_general_planning:
                    documents.append("✅ Planning général")
                else:
                    documents.append("❌ Planning général")
                
                if hasattr(lot, 'document_subcontractor_planning') and lot.document_subcontractor_planning:
                    documents.append("✅ Planning sous-traitant")
                else:
                    documents.append("❌ Planning sous-traitant")
                
                # Bons de commande
                purchase_orders = self._get_lot_purchase_orders(lot, wizard.subcontractor_id)
                if purchase_orders:
                    documents.append(f"✅ {len(purchase_orders)} bon(s) de commande")
                else:
                    documents.append("❌ Aucun bon de commande")
                
                html_parts.append(f"<p style='margin: 5px 0;'><strong>Documents :</strong> {' | '.join(documents)}</p>")
                html_parts.append(f"<p style='margin: 5px 0;'><strong>Montant :</strong> {(lot.price or lot.price_from_quote or 0.0):,.2f} €</p>")
                html_parts.append("</div>")
            
            html_parts.append("</div>")
            wizard.available_documents = "".join(html_parts)
    
    # =================== MÉTHODES UTILITAIRES ===================
    
    def _get_lot_purchase_orders(self, lot, subcontractor):
        """Récupère les bons de commande d'un lot pour un sous-traitant."""
        # Recherche via lot_ids sur le bon de commande
        orders_via_lot_ids = self.env['purchase.order'].search([
            ('lot_ids', 'in', [lot.id]),
            ('partner_id', '=', subcontractor.id),
            ('state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        
        # Recherche via les lignes de commande
        order_lines_with_lot = self.env['purchase.order.line'].search([
            ('lot_id', '=', lot.id),
            ('order_id.partner_id', '=', subcontractor.id),
            ('order_id.state', 'in', ['draft', 'sent', 'to_approve', 'purchase', 'done'])
        ])
        orders_via_lines = order_lines_with_lot.mapped('order_id')
        
        return orders_via_lot_ids | orders_via_lines
    
    # =================== ACTIONS ===================
    
    def action_generate_contract(self):
        """Génère le contrat unifié pour tous les lots."""
        self.ensure_one()
        
        # Validation
        if not self.lot_ids:
            raise ValidationError(_("Veuillez sélectionner au moins un lot."))
        
        if not self.subcontractor_id:
            raise ValidationError(_("Veuillez sélectionner un sous-traitant."))
        
        if not self.total_amount or self.total_amount <= 0:
            raise ValidationError(_("Le montant total doit être supérieur à 0."))
        
        try:
            # Préparer les données du contrat
            contract_data = {
                'start_date': self.contract_start_date,
                'end_date': self.contract_end_date,
                'total_amount': self.total_amount,
                'payment_terms': self.payment_terms,
                'warranty_period': self.warranty_period,
                'insurance_required': self.insurance_required,
                'notes': self.contract_notes,
                'send_email': self.send_email,
                'auto_send': self.auto_send,
                'urssaf_code': self.urssaf_code,
            }
            
            # Générer le contrat via le service
            contract_service = self.env['construction.contract.service']
            contract = contract_service.generate_contract(
                self.chantier_id,
                self.subcontractor_id,
                self.lot_ids,
                contract_data
            )
            
            # Mettre à jour le wizard
            self.write({
                'generated_contract_id': contract.id,
                'contract_generated': True,
            })
            
            # Envoyer par email si demandé
            if self.send_email:
                contract.action_send_contract()
            
            _logger.info(f"✅ Contrat unifié généré: {contract.contract_number}")
            
            # Message de succès
            self.chantier_id.message_post(
                body=f"📄 Contrat unifié généré pour {self.subcontractor_id.name} "
                     f"({self.lot_count} lot{'s' if self.lot_count > 1 else ''}) - "
                     f"Montant: {self.total_amount:,.2f} €",
                message_type='notification'
            )
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'Contrat unifié - {self.subcontractor_id.name}',
                'res_model': 'construction.subcontractor.contract',
                'res_id': contract.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            _logger.error(f"❌ Erreur génération contrat unifié: {e}")
            raise ValidationError(_("Erreur lors de la génération du contrat: %s") % str(e))

    def action_generate_preview(self):
        """Génère l'aperçu du contrat multi-lots."""
        self.ensure_one()

        if not self.lot_ids:
            raise ValidationError(_("Veuillez sélectionner au moins un lot."))

        try:
            contract_service = self.env['construction.contract.service']
            contract_data = {
                'start_date': self.contract_start_date,
                'end_date': self.contract_end_date,
                'total_amount': self.total_amount,
                'payment_terms': self.payment_terms,
                'warranty_period': self.warranty_period,
                'insurance_required': self.insurance_required,
                'notes': self.contract_notes,
                'send_email': self.send_email,
                'auto_send': self.auto_send,
                'urssaf_code': self.urssaf_code,
                # Flags d'inclusion (actuellement informatifs pour le service)
                'include_cctp': self.include_cctp,
                'include_general_planning': self.include_general_planning,
                'include_subcontractor_planning': self.include_subcontractor_planning,
                'include_purchase_orders': self.include_purchase_orders,
            }

            html = contract_service.generate_preview_html(
                self.chantier_id,
                self.subcontractor_id,
                self.lot_ids,
                contract_data
            )

            self.write({'preview_html': html, 'preview_ready': True})

            return {
                'type': 'ir.actions.act_window',
                'name': _('Aperçu contrat unifié'),
                'res_model': self._name,
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        except Exception as e:
            _logger.error(f"❌ Erreur génération aperçu: {e}")
            raise ValidationError(_("Erreur lors de la génération de l'aperçu: %s") % str(e))
    
    def action_view_contract(self):
        """Affiche le contrat généré."""
        self.ensure_one()
        
        if not self.generated_contract_id:
            raise ValidationError(_("Aucun contrat généré."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Contrat unifié - {self.subcontractor_id.name}',
            'res_model': 'construction.subcontractor.contract',
            'res_id': self.generated_contract_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_purchase_orders(self):
        """Affiche les bons de commande des lots sélectionnés."""
        self.ensure_one()
        
        if not self.lot_ids:
            raise ValidationError(_("Aucun lot sélectionné."))
        
        # Récupérer tous les bons de commande des lots
        all_orders = self.env['purchase.order']
        for lot in self.lot_ids:
            lot_orders = self._get_lot_purchase_orders(lot, self.subcontractor_id)
            all_orders |= lot_orders
        
        if not all_orders:
            raise ValidationError(_("Aucun bon de commande trouvé pour ces lots."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Bons de commande - {self.subcontractor_id.name}',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', all_orders.ids)],
            'context': {
                'default_chantier_id': self.chantier_id.id,
                'default_partner_id': self.subcontractor_id.id,
            }
        }
    
    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut depuis le contexte."""
        defaults = super().default_get(fields_list)
        
        # Récupérer les valeurs du contexte
        for field in ['chantier_id', 'subcontractor_id', 'lot_ids']:
            context_key = f'default_{field}'
            if context_key in self.env.context:
                defaults[field] = self.env.context[context_key]
        
        return defaults
