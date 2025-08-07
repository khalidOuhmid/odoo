# -*- coding: utf-8 -*-
"""
Modèle de contrat avec tous les champs requis par le template
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import hashlib
import logging
import base64

_logger = logging.getLogger(__name__)


class SubcontractorContract(models.Model):
    _name = 'construction.subcontractor.contract'
    _description = 'Contrat de sous-traitance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Champs principaux
    name = fields.Char('Nom du contrat', required=True, tracking=True)
    contract_number = fields.Char('Numéro', required=True, copy=False, readonly=True)

    # Relations
    chantier_id = fields.Many2one('construction.chantier', 'Chantier', required=True, tracking=True)
    subcontractor_id = fields.Many2one('res.partner', 'Sous-traitant', required=True, tracking=True)
    lot_ids = fields.Many2many('construction.lot', 'contract_lot_rel', 'contract_id', 'lot_id', 'Lots concernés')
    company_id = fields.Many2one('res.company', 'Entreprise', default=lambda self: self.env.company)
    lot_names = fields.Char(string='Lots (noms)', compute='_compute_lot_names', store=False)

    # Conditions contractuelles
    start_date = fields.Date('Date de début', required=True, default=fields.Date.today, tracking=True)
    end_date = fields.Date('Date de fin', tracking=True)
    total_amount = fields.Monetary('Montant total', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', 'Devise', default=lambda self: self.env.company.currency_id)
    payment_terms = fields.Selection([
        ('30_days', '30 jours'), ('45_days', '45 jours'), ('60_days', '60 jours'),
        ('end_of_work', 'Fin des travaux'),
    ], string='Conditions de paiement', default='30_days', tracking=True)
    warranty_period = fields.Integer('Garantie (mois)', default=12)
    insurance_required = fields.Boolean('Assurance requise', default=True)
    notes = fields.Text('Notes')
    
    # Code URSSAF personnalisable
    urssaf_code = fields.Char('Code URSSAF', help="Code URSSAF avec description pour ce contrat")

    # Documents et portail
    contract_pdf = fields.Binary('Contrat PDF', attachment=True)
    filename = fields.Char('Nom du fichier')
    portal_url = fields.Char('Lien portail', readonly=True)
    access_token = fields.Char('Token d\'accès', copy=False, readonly=True)

    # États
    state = fields.Selection([
        ('draft', 'Brouillon'), ('sent', 'Envoyé'), ('signed', 'Signé'),
        ('active', 'Actif'), ('completed', 'Terminé'), ('cancelled', 'Annulé'),
    ], default='draft', tracking=True, string='État')

    # Signature électronique
    signature_state = fields.Selection([
        ('pending', 'En attente'), ('signed', 'Signé'), ('refused', 'Refusé'),
    ], default='pending', tracking=True, string='État signature')
    signed_date = fields.Datetime('Date de signature', readonly=True)
    signature_ip = fields.Char('IP de signature', readonly=True)
    signature_comment = fields.Text('Commentaire de signature', readonly=True)
    signature_image = fields.Binary('Signature', readonly=True)
    
    # Empreinte numérique et traçabilité juridique
    signature_hash = fields.Char('Empreinte SHA-256', readonly=True, help="Hash cryptographique du contrat signé")
    signature_timestamp = fields.Datetime('Horodatage certifié', readonly=True)
    user_agent = fields.Char('Navigateur utilisé', readonly=True)
    signature_certificate = fields.Text('Certificat de signature', readonly=True, help="Données de traçabilité pour validité juridique")
    contract_hash_before_signature = fields.Char('Hash avant signature', readonly=True)
    contract_hash_after_signature = fields.Char('Hash après signature', readonly=True)

    @api.model
    def create(self, vals):
        if not vals.get('contract_number'):
            vals['contract_number'] = self.env['ir.sequence'].next_by_code('construction.contract') or 'CT-NEW'
        return super().create(vals)

    def action_send_contract(self):
        self.ensure_one()
        if not self.contract_pdf:
            raise ValidationError(_("Le PDF doit être généré avant envoi."))
        if not self.subcontractor_id.email:
            raise ValidationError(_("Le sous-traitant doit avoir un email."))
        
        self.write({'state': 'sent'})
        self._send_contract_email()
        self.message_post(body=f"Contrat envoyé à {self.subcontractor_id.name}", message_type='notification')
        return True

    def action_electronic_signature(self, signature_data=None):
        self.ensure_one()
        import hashlib
        import json
        from datetime import datetime
        
        # Calculer le hash du contrat avant signature
        contract_content_before = f"{self.name}{self.contract_number}{self.total_amount}{self.subcontractor_id.name}"
        hash_before = hashlib.sha256(contract_content_before.encode('utf-8')).hexdigest()
        
        # Horodatage précis
        signature_timestamp = fields.Datetime.now()
        timestamp_str = signature_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f UTC')
        
        # Données pour le certificat de signature
        certificate_data = {
            'contract_number': self.contract_number,
            'subcontractor_name': self.subcontractor_id.name,
            'subcontractor_email': self.subcontractor_id.email,
            'signature_timestamp': timestamp_str,
            'ip_address': signature_data.get('ip'),
            'user_agent': signature_data.get('user_agent', ''),
            'signature_method': 'electronic_signature',
            'contract_amount': str(self.total_amount),
            'chantier_name': self.chantier_id.name,
        }
        
        # Générer un hash de toutes les données de signature
        signature_content = json.dumps(certificate_data, sort_keys=True) + (signature_data.get('signature_image') or '')
        signature_hash = hashlib.sha256(signature_content.encode('utf-8')).hexdigest()
        
        self.write({
            'signature_state': 'signed',
            'signed_date': signature_timestamp,
            'state': 'signed',
            'signature_ip': signature_data.get('ip'),
            'signature_comment': signature_data.get('comment'),
            'signature_image': signature_data.get('signature_image'),
            'signature_hash': signature_hash,
            'signature_timestamp': signature_timestamp,
            'user_agent': signature_data.get('user_agent', ''),
            'signature_certificate': json.dumps(certificate_data, indent=2),
            'contract_hash_before_signature': hash_before,
        })
        
        # Générer le PDF final avec signature
        pdf_content = self.env['construction.contract.service']._generate_pdf_with_full_template(self)
        self.write({'contract_pdf': base64.b64encode(pdf_content)})
        
        # Calculer le hash du contrat après signature
        contract_content_after = f"{self.name}{self.contract_number}{self.total_amount}{self.subcontractor_id.name}{signature_hash}"
        hash_after = hashlib.sha256(contract_content_after.encode('utf-8')).hexdigest()
        self.write({'contract_hash_after_signature': hash_after})

        self.message_post(
            body=f"Contrat signé électroniquement par {self.subcontractor_id.name}<br/>"
                 f"Empreinte numérique: {signature_hash[:16]}...<br/>"
                 f"Horodatage: {timestamp_str}",
            message_type='notification'
        )
        self._send_signature_confirmation()
        return True
    
    def get_signature_certificate_display(self):
        """Retourne les informations de certification pour affichage."""
        self.ensure_one()
        if not self.signature_certificate:
            return False
        
        import json
        try:
            cert_data = json.loads(self.signature_certificate)
            return {
                'contract_number': cert_data.get('contract_number'),
                'signature_timestamp': cert_data.get('signature_timestamp'),
                'ip_address': cert_data.get('ip_address'),
                'signature_hash': self.signature_hash,
                'hash_before': self.contract_hash_before_signature,
                'hash_after': self.contract_hash_after_signature,
                'user_agent': cert_data.get('user_agent', ''),
                'subcontractor_email': cert_data.get('subcontractor_email'),
            }
        except:
            return False
    
    def verify_signature_integrity(self):
        """Vérifie l'intégrité de la signature électronique."""
        self.ensure_one()
        if not self.signature_hash or not self.signature_certificate:
            return False
        
        import json
        import hashlib
        try:
            # Recalculer le hash avec les données originales
            cert_data = json.loads(self.signature_certificate)
            signature_content = json.dumps(cert_data, sort_keys=True) + (self.signature_image.decode('utf-8') if self.signature_image else '')
            calculated_hash = hashlib.sha256(signature_content.encode('utf-8')).hexdigest()
            
            return calculated_hash == self.signature_hash
        except:
            return False
        
    @api.depends('lot_ids')
    def _compute_lot_names(self):
        """Concatène les noms des lots pour l’affichage dans les mails / PDF."""
        for rec in self:
            rec.lot_names = ', '.join(rec.lot_ids.mapped('name')) if rec.lot_ids else ''

    def _generate_access_token(self):
        self.ensure_one()
        return hashlib.sha256(f"{self.id}-{self.create_date}".encode()).hexdigest()

    def _send_contract_email(self):
        template = self.env.ref('construction_base.email_template_contract_signature', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def _send_signature_confirmation(self):
        # Logique d'envoi de confirmation
        pass

    def action_view_portal(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.portal_url,
            'target': 'new',
        }

    def action_download_pdf(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/contract_pdf?download=true',
            'target': 'self',
        }
