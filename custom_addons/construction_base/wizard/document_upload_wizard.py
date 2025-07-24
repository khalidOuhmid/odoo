from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DocumentUploadWizard(models.TransientModel):
    _name = 'construction.document.upload.wizard'
    _description = 'Assistant de téléchargement de documents'

    name = fields.Char('Nom du document', required=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True)
    document_type = fields.Selection([
        ('quote', 'Devis'),
        ('contract', 'Contrat'),
        ('subcontract', 'Sous-traitance'),
        ('specs', 'Spécifications techniques'),
        ('plan', 'Plan'),
        ('schedule', 'Planning'),
        ('permit', 'Permis'),
        ('other', 'Autre')
    ], string='Type de Document', required=True, default='other')
    
    file_data = fields.Binary('Fichier', required=True)
    filename = fields.Char('Nom du fichier', required=True)
    description = fields.Text('Description')
    partner_id = fields.Many2one('res.partner', string='Partenaire associé')
    expiry_date = fields.Date('Date d\'expiration')

    @api.model
    def default_get(self, fields_list):
        """Récupérer les valeurs par défaut depuis le contexte"""
        res = super().default_get(fields_list)
        
        # Récupérer le chantier depuis le contexte
        if 'default_chantier_id' in self.env.context:
            res['chantier_id'] = self.env.context['default_chantier_id']
            
        return res

    def action_upload_document(self):
        """Créer le document et fermer le wizard"""
        self.ensure_one()
        
        if not self.file_data:
            raise ValidationError(_("Veuillez sélectionner un fichier."))
            
        if not self.filename:
            raise ValidationError(_("Veuillez spécifier un nom de fichier."))
        
        # Créer le document
        document = self.env['construction.document'].create({
            'name': self.name,
            'chantier_id': self.chantier_id.id,
            'document_type': self.document_type,
            'file_data': self.file_data,
            'filename': self.filename,
            'description': self.description,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'expiry_date': self.expiry_date,
        })
        
        return {
            'type': 'ir.actions.act_window_close',
            'infos': _('Document "%s" ajouté avec succès.') % self.name,
        }
