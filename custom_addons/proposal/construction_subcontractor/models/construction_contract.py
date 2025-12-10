# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import secrets
import logging
import base64
from datetime import timedelta

_logger = logging.getLogger(__name__)

class ConstructionContract(models.Model):
    """
    Gestion des Contrats de Sous-traitance.
    
    Lien juridique et financier avec le partenaire.
    Hérite de FinancialMixin pour alimenter le "Committed Cost" du chantier/lot.
    """
    _name = 'construction.contract'
    _description = 'Construction Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin', 
                'construction.financial.mixin']
    _order = 'date_signed desc, id desc'

    name = fields.Char(string='Référence Contrat', required=True, copy=False, default='Draft')
    
    # PARTIES
    partner_id = fields.Many2one(
        'res.partner', 
        string='Sous-traitant', 
        required=True, 
        tracking=True,
        domain="[('is_subcontractor', '=', True)]"
    )
    
    company_id = fields.Many2one('res.company', string='Société', default=lambda self: self.env.company)

    # CONTEXTE PROJET
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier', 
        required=True, 
        tracking=True
    )
    lot_ids = fields.Many2many(
        'construction.lot', 
        string='Lots de Travaux',
        domain="[('chantier_id', '=', chantier_id)]",
        required=True
    )
    
    _sql_constraints = [
        ('unique_contract_per_partner_chantier', 
         'unique(partner_id, chantier_id)', 
         'Un seul contrat actif est autorisé par sous-traitant pour un chantier donné.')
    ]

    # DATES
    date_start = fields.Date(string='Date de Début', required=True)
    date_end = fields.Date(string='Date de Fin')
    date_signed = fields.Date(string='Date de Signature', tracking=True)

    # FINANCE (Mixin Override)
    # Le montant du contrat EST le montant engagé.
    amount_tax_excluded = fields.Monetary(string="Montant HT", currency_field='currency_id', tracking=True)
    amount_tax = fields.Monetary(string="Taxes", currency_field='currency_id')
    amount_total = fields.Monetary(string="Montant TTC", currency_field='currency_id', compute='_compute_amount_total')
    
    retention_guarantee_rate = fields.Float(string="Retenue de Garantie (%)", default=5.0)

    # ==========================
    # TEMPLATE & PDF GENERATION
    # ==========================
    template_id = fields.Many2one(
        'construction.contract.template',
        string='Modèle de Contrat',
        tracking=True
    )
    
    custom_html_override = fields.Html(
        string='Live Edit Ref.',
        sanitize=False,
        help="Surcharge manuelle du contenu généré par le modèle."
    )

    pdf_document = fields.Binary(string='Contrat PDF', attachment=True)
    pdf_filename = fields.Char(compute='_compute_pdf_filename')

    # ==========================
    # PORTAL & SIGNATURE
    # ==========================
    access_token = fields.Char(string='Jeton d\'accès', copy=False)
    token_expiry_date = fields.Datetime(string='Expiration du Jeton')
    portal_url = fields.Char(compute='_compute_portal_url')
    
    signature_image = fields.Binary(string='Signature', attachment=True)

    # STATUT
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('generated', 'Généré'),
        ('sent', 'Envoyé'),
        ('signed', 'Signé'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='Statut', default='draft', tracking=True)

    # ==========================
    # LOGIQUE MÉTIER
    # ==========================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Draft') == 'Draft':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.contract') or 'Draft'
        return super().create(vals_list)

    @api.depends('amount_tax_excluded', 'amount_tax')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = record.amount_tax_excluded + record.amount_tax

    # ==========================
    # FINOPS MIXIN IMPLEMENTATION
    # ==========================
    def _compute_financial_status(self):
        """
        Pour un contract, le committed = montant signé.
        Le realized = total facturé (suppose un lien vers factures, à faire).
        """
        for contract in self:
            contract.committed_amount = contract.amount_tax_excluded if contract.state in ['signed', 'done'] else 0.0
            # Future: Link to account.move lines for realization
            contract.realized_amount = 0.0

    # ==========================
    # ACTIONS
    # ==========================
    # ==========================
    # ACTIONS
    # ==========================
    def action_generate_pdf(self):
        """
        Génère le PDF à partir du template ou du custom_html et le sauvegarde.
        """
        self.ensure_one()
        
        # Get the report action
        report_ref = 'construction_subcontractor.action_report_construction_contract'
        # Render the PDF
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(report_ref, self.ids)
        
        # Save validation state + PDF
        vals = {
            'pdf_document': base64.b64encode(pdf_content),
            'pdf_filename': f"{self.name.replace('/', '_')}.pdf",
        }
        
        # If currently draft, set to generated
        if self.state == 'draft':
            vals['state'] = 'generated'
            
        self.write(vals)
        _logger.info("PDF Generated for contract %s", self.id)

    def action_send_by_email(self):
        """ Envoie le lien du portail par email """
        self.ensure_one()
        _logger.info("Action: Sending Email for Contract %s (ID: %s)", self.name, self.id)
        
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
            self.token_expiry_date = fields.Datetime.now() + timedelta(days=30)
            _logger.info("Generated new access token for Contract %s", self.id)
        
        # Send Email using Template
        template = self.env.ref('construction_subcontractor.email_template_contract_signature', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
            _logger.info("Email sent for Contract %s using template %s", self.id, template.name)
        else:
            _logger.warning("Email Template 'construction_subcontractor.email_template_contract_signature' not found!")
        
        self.write({'state': 'sent'})
        _logger.info("Contract %s state set to 'sent'", self.id)

    def action_sign(self, signature_data=None):
        _logger.info("Action: Signing Contract %s (ID: %s)", self.name, self.id)
        vals = {
            'state': 'signed', 
            'date_signed': fields.Date.today()
        }
        if signature_data:
            vals['signature_image'] = signature_data
            
        self.write(vals)
        _logger.info("Contract %s state set to 'signed'", self.id)

    # ==========================
    # COMPUTE METHODS
    # ==========================
    @api.depends('name')
    def _compute_pdf_filename(self):
        for record in self:
            safe_name = record.name.replace('/', '_') if record.name else 'contract'
            record.pdf_filename = f"{safe_name}.pdf"

    @api.depends('access_token')
    def _compute_portal_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.access_token:
                record.portal_url = f"{base_url}/my/contract/{record.id}/sign?access_token={record.access_token}"
            else:
                record.portal_url = False
