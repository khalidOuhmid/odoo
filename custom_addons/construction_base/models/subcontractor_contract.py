# -*- coding: utf-8 -*-
"""
Modèle pour les contrats de sous-traitance.
Gère les contrats générés, les signatures électroniques et l'accès portail.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SubcontractorContract(models.Model):
    """Contrat de sous-traitance."""
    
    _name = 'construction.subcontractor.contract'
    _description = 'Contrat de sous-traitance'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # =================== CHAMPS PRINCIPAUX ===================
    
    name = fields.Char(
        string='Nom du contrat',
        required=True,
        default=lambda self: _('Nouveau contrat')
    )
    
    contract_number = fields.Char(
        string='Numéro de contrat',
        required=True,
        copy=False,
        readonly=True,
        help="Numéro unique du contrat"
    )
    
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        ondelete='cascade',
        help="Chantier concerné par le contrat"
    )
    
    subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant',
        required=True,
        domain="[('is_subcontractor', '=', True)]",
        help="Sous-traitant signataire du contrat"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',
        string='Lots concernés',
        required=True,
        help="Lots de travaux couverts par le contrat"
    )
    
    # =================== CONDITIONS CONTRACTUELLES ===================
    
    start_date = fields.Date(
        string='Date de début',
        required=True,
        default=fields.Date.today,
        help="Date de début des travaux"
    )
    
    end_date = fields.Date(
        string='Date de fin',
        help="Date de fin prévue des travaux"
    )
    
    total_amount = fields.Monetary(
        string='Montant total',
        currency_field='currency_id',
        required=True,
        help="Montant total du contrat"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        default=lambda self: self.env.company.currency_id
    )
    
    payment_terms = fields.Selection([
        ('30_days', '30 jours'),
        ('45_days', '45 jours'),
        ('60_days', '60 jours'),
        ('end_of_work', 'Fin des travaux'),
        ('custom', 'Personnalisé')
    ], string='Conditions de paiement', default='30_days')
    
    payment_terms_custom = fields.Text(
        string='Conditions personnalisées',
        help="Conditions de paiement personnalisées"
    )
    
    warranty_period = fields.Integer(
        string='Garantie (mois)',
        default=12,
        help="Période de garantie en mois"
    )
    
    insurance_required = fields.Boolean(
        string='Assurance requise',
        default=True,
        help="Assurance décennale requise"
    )
    
    # =================== DOCUMENTS ===================
    
    contract_pdf = fields.Binary(
        string='Contrat PDF',
        attachment=True,
        help="Fichier PDF du contrat généré"
    )
    
    filename = fields.Char(
        string='Nom du fichier',
        help="Nom du fichier PDF"
    )
    
    portal_url = fields.Char(
        string='Lien portail',
        help="Lien vers le portail pour signature"
    )
    
    # =================== SIGNATURE ÉLECTRONIQUE ===================
    
    signature_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('viewed', 'Consulté'),
        ('signed', 'Signé'),
        ('refused', 'Refusé')
    ], string='État signature', default='draft', tracking=True)
    
    signed_date = fields.Datetime(
        string='Date de signature',
        help="Date et heure de signature électronique"
    )
    
    signature_ip = fields.Char(
        string='IP de signature',
        help="Adresse IP de la signature"
    )
    
    signature_comment = fields.Text(
        string='Commentaire signature',
        help="Commentaire du sous-traitant lors de la signature"
    )
    
    # =================== ÉTAT GÉNÉRAL ===================
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', tracking=True)
    
    notes = fields.Text(
        string='Notes',
        help="Notes internes sur le contrat"
    )
    
    # =================== MÉTHODES ===================
    
    @api.model
    def create(self, vals):
        """Générer le numéro de contrat automatiquement."""
        if not vals.get('contract_number'):
            vals['contract_number'] = self._generate_contract_number()
        return super().create(vals)
    
    def _generate_contract_number(self):
        """Générer un numéro de contrat unique."""
        from datetime import datetime
        return f"CONTRACT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def action_send_contract(self):
        """Envoyer le contrat au sous-traitant."""
        self.ensure_one()
        
        if not self.contract_pdf:
            raise ValidationError(_("Le contrat PDF doit être généré avant envoi."))
        
        # Mettre à jour l'état
        self.write({
            'state': 'sent',
            'signature_state': 'sent'
        })
        
        # Envoyer par email
        self._send_contract_email()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Contrat envoyé au sous-traitant.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_sign_electronically(self):
        """Action pour signature électronique (appelée depuis le portail)."""
        self.ensure_one()
        
        # Vérifier que c'est bien le sous-traitant qui signe
        if not self._can_sign():
            raise ValidationError(_("Vous n'êtes pas autorisé à signer ce contrat."))
        
        # Enregistrer la signature
        self.write({
            'signature_state': 'signed',
            'signed_date': fields.Datetime.now(),
            'signature_ip': self.env.context.get('signature_ip', ''),
            'state': 'active'
        })
        
        # Notifier le chantier
        self.chantier_id.message_post(
            body=f"✅ Contrat signé électroniquement par {self.subcontractor_id.name}",
            message_type='comment'
        )
        
        return True
    
    def _can_sign(self):
        """Vérifier si l'utilisateur peut signer le contrat."""
        # Logique de vérification (à adapter selon vos besoins)
        return True
    
    def _send_contract_email(self):
        """Envoyer le contrat par email."""
        template = self.env.ref('construction_base.email_template_subcontractor_contract', raise_if_not_found=False)
        
        if template:
            template.send_mail(self.id, force_send=True)
        else:
            # Email par défaut
            subject = f"Contrat de sous-traitance - {self.chantier_id.name}"
            body = f"""
            Bonjour {self.subcontractor_id.name},
            
            Veuillez trouver ci-joint votre contrat de sous-traitance pour le chantier {self.chantier_id.name}.
            
            Vous pouvez également consulter et signer le contrat en ligne : {self.portal_url}
            
            Cordialement,
            {self.chantier_id.company_id.name}
            """
            
            self.env['mail.mail'].create({
                'subject': subject,
                'body_html': body,
                'email_from': self.chantier_id.company_id.email,
                'email_to': self.subcontractor_id.email,
                'attachment_ids': [(6, 0, [self.contract_pdf.id])] if self.contract_pdf else [],
            }).send()
    
    def action_view_portal(self):
        """Ouvrir le portail de signature."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.portal_url,
            'target': 'new',
        }
    
    def action_download_pdf(self):
        """Télécharger le PDF du contrat."""
        self.ensure_one()
        if not self.contract_pdf:
            raise ValidationError(_("Aucun PDF disponible."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/contract_pdf?download=true',
            'target': 'new',
        } 