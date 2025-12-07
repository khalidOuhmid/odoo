# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ConstructionContract(models.Model):
    """
    Subcontractor Contract (Marché de Travaux).
    
    Links a Subcontractor to a specific Lot with a defined monetary selection (Quote).
    """
    _name = 'construction.contract'
    _description = 'Marché de Travaux'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Référence Contrat', required=True, copy=False, default=lambda self: _('Nouveau'))
    
    chantier_id = fields.Many2one('construction.chantier', required=True, string='Chantier')
    lot_id = fields.Many2one('construction.lot', required=True, string='Lot')
    partner_id = fields.Many2one('res.partner', string='Sous-Traitant', required=True)
    
    date_signature = fields.Date(string='Date Signature')
    
    # Documents for Fusion
    cctp_attachment_id = fields.Many2one('ir.attachment', string='CCTP', domain="[('mimetype', '=', 'application/pdf')]")
    planning_attachment_id = fields.Many2one('ir.attachment', string='Planning', domain="[('mimetype', '=', 'application/pdf')]")
    other_attachment_ids = fields.Many2many('ir.attachment', string='Autres Annexes', domain="[('mimetype', '=', 'application/pdf')]")
    
    # Generated Contract
    contract_pdf = fields.Binary(string='Contrat Complet (PDF)', attachment=True)
    contract_pdf_name = fields.Char(string='Nom Fichier Contract')

    amount_ht = fields.Monetary(string='Montant HT', required=True)
    currency_id = fields.Many2one(related='chantier_id.currency_id')
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé pour signature'),
        ('signed', 'Signé'),
        ('cancel', 'Annulé')
    ], default='draft', string='État', tracking=True)

    # Document Compliance Check
    documents_valid = fields.Boolean(string='Documents Conformes', compute='_compute_documents_valid', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.contract') or _('Nouveau')
        return super().create(vals_list)

    @api.depends('partner_id') # Should check partner documents expirations
    def _compute_documents_valid(self):
        for rec in self:
            # Placeholder: In real implementation, check attachments on res.partner
            rec.documents_valid = True 

    def action_send_signature(self):
        """Send email with link to portal."""
        self.ensure_one()
        # Generate the main PDF first if not done
        if not self.contract_pdf:
            self._generate_full_pdf()
            
        template = self.env.ref('construction_contract.email_template_contract_signature', raise_if_not_found=False) # To be created
        if template:
            template.send_mail(self.id, force_send=True)
            
        self.state = 'sent'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Envoyé'),
                'message': _('Le lien de signature a été envoyé au sous-traitant.'),
                'type': 'success',
            }
        }

    def action_preview_portal(self):
        """Preview the portal signature page."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/my/contracts/{self.id}/sign',
            'target': 'self',
        }

    def _generate_full_pdf(self):
        """Merge Contract Report + CCTP + Planning + Annexes."""
        self.ensure_one()
        try:
            from odoo.tools.pdf import merge_pdf
            import base64
            import io

            # 1. Generate Odoo Report
            report_action = self.env.ref('construction_contract.action_report_contract', raise_if_not_found=False) # To be created
            # Fallback mock if report not ready
            streams = []
            
            # TODO: Add main report stream here
            # main_pdf_content, _ = report_action._render_qweb_pdf(self.ids)
            # streams.append(io.BytesIO(main_pdf_content))

            # 2. Append Attachments
            if self.cctp_attachment_id:
                streams.append(io.BytesIO(base64.b64decode(self.cctp_attachment_id.datas)))
            if self.planning_attachment_id:
                streams.append(io.BytesIO(base64.b64decode(self.planning_attachment_id.datas)))
            for att in self.other_attachment_ids:
                streams.append(io.BytesIO(base64.b64decode(att.datas)))
                
            if not streams:
                return # Nothing to merge
                
            # 3. Merge
            merged_content = merge_pdf(streams)
            
            name = (self.name or 'Contrat').replace('/', '_') + '.pdf'
            self.write({
                'contract_pdf': base64.b64encode(merged_content),
                'contract_pdf_name': name
            })
            
        except ImportError:
            # Fallback if libraries missing
            pass
        except Exception as e:
            raise ValidationError(f"Erreur fusion PDF: {str(e)}")

    def action_sign(self):
        self.state = 'signed'
        self.date_signature = fields.Date.today()
        # Initial Validation of Docs
        if self.lot_id.subcontractor_id != self.partner_id:
             self.lot_id.subcontractor_id = self.partner_id

        # Notify Director
        if hasattr(self.chantier_id, 'notify_director'):
            self.chantier_id.notify_director(
                _("Contrat Signé: %s") % self.name,
                _("Le sous-traitant %s a signé le contrat pour le chantier %s.") % (self.partner_id.name, self.chantier_id.name)
            )
