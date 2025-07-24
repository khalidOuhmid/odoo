from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class LotDocumentWizard(models.TransientModel):
    _name = 'lot.document.wizard'
    _description = 'Gestion des documents du lot'

    lot_id = fields.Many2one('construction.lot', string='Lot', required=True, readonly=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, readonly=True)
    subcontractor_id = fields.Many2one('res.partner', string='Sous-traitant', required=True, readonly=True)

    document_cctp = fields.Binary(string="CCTP", attachment=True)
    document_subcontractor_contract = fields.Binary(string="Contrat de sous-traitance", attachment=True)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lot = self.env['construction.lot'].browse(self.env.context.get('active_id'))
        if lot:
            res['lot_id'] = lot.id
            # Récupérer le chantier via la relation inverse
            chantier = self.env['construction.chantier'].search([
                ('lots_ids', 'in', lot.id)
            ], limit=1)
            res['chantier_id'] = chantier.id if chantier else False
            if lot.subcontractor_ids:
                res['subcontractor_id'] = lot.subcontractor_ids[0].id
            # Pré-remplir les documents si présents - avec gestion d'erreur
            try:
                if hasattr(lot, 'document_cctp') and lot.document_cctp:
                    res['document_cctp'] = lot.document_cctp
                if hasattr(lot, 'document_subcontractor_contract') and lot.document_subcontractor_contract:
                    res['document_subcontractor_contract'] = lot.document_subcontractor_contract
            except AttributeError:
                # Les champs document n'existent pas encore sur ce modèle
                pass
        return res

    def _get_payment_schedule(self):
        """Calcule l'échéancier de paiement basé sur le prix du lot"""
        if not self.lot_id or not self.lot_id.price:
            return []
        
        total_price = self.lot_id.price
        return [
            {'percentage': 30, 'amount': total_price * 0.3},
            {'percentage': 60, 'amount': total_price * 0.6},
            {'percentage': 100, 'amount': total_price},
        ]

    def action_save_documents(self):
        self.ensure_one()
        lot = self.lot_id
        vals = {}
        if self.document_cctp:
            vals['document_cctp'] = self.document_cctp
        if self.document_subcontractor_contract:
            vals['document_subcontractor_contract'] = self.document_subcontractor_contract
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
        self.ensure_one()
        
        # Vérifications préliminaires
        if not self.subcontractor_id:
            raise ValidationError("Aucun sous-traitant assigné à ce lot.")
        
        if not self.chantier_id:
            raise ValidationError("Aucun chantier associé à ce lot.")
        
        # Générer le rapport PDF en utilisant le lot et en passant les données nécessaires
        report_template = 'construction_base.subcontractor_contract_template'
        
        # Créer un contexte avec les données nécessaires
        report_data = {
            'lot_id': self.lot_id.id,
            'chantier_id': self.chantier_id.id,
            'subcontractor_id': self.subcontractor_id.id,
        }
        
        pdf_content = self.env['ir.actions.report']._render_qweb_pdf(
            report_template,
            self.ids,
            data=report_data
        )[0]
        
        # Encoder le contenu PDF en base64
        import base64
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
        
        # Mettre à jour le wizard avec le document généré
        self.document_subcontractor_contract = pdf_base64
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Contrat généré',
                'message': f'Le contrat de sous-traitance a été généré: {filename}',
                'type': 'success',
            }
        }

    def action_preview_contract(self):
        """Ouvre une prévisualisation du contrat de sous-traitance"""
        self.ensure_one()
        
        # Vérifications préliminaires
        if not self.subcontractor_id:
            raise ValidationError("Aucun sous-traitant assigné à ce lot.")
        
        if not self.chantier_id:
            raise ValidationError("Aucun chantier associé à ce lot.")
        
        # Retourner l'action pour ouvrir le rapport dans une nouvelle fenêtre
        return {
            'type': 'ir.actions.report',
            'report_name': 'construction_base.action_subcontractor_contract_report',
            'report_type': 'qweb-pdf',
            'data': {},
            'context': self.env.context,
            'target': 'new',
        }
