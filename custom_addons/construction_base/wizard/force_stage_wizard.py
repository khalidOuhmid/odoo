from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ForceStageWizard(models.TransientModel):
    _name = 'construction.force.stage.wizard'
    _description = 'Forcer changement d\'étape (Admin uniquement)'

    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True)
    current_stage_id = fields.Many2one('construction.stage', string='Étape actuelle', readonly=True)
    new_stage_id = fields.Many2one('construction.stage', string='Nouvelle étape', required=True)
    reason = fields.Text('Motif du changement forcé', required=True, 
                        placeholder="Expliquez pourquoi ce changement d'étape est nécessaire...")
    
    @api.model
    def default_get(self, fields_list):
        """Pré-remplir avec les valeurs du chantier"""
        defaults = super().default_get(fields_list)
        
        if 'chantier_id' in defaults and defaults['chantier_id']:
            chantier = self.env['construction.chantier'].browse(defaults['chantier_id'])
            defaults['current_stage_id'] = chantier.stage_id.id
            
        return defaults
    
    def action_force_change(self):
        """Effectuer le changement d'étape forcé"""
        # Vérifier les droits admin
        if not self.env.user.has_group('base.group_system'):
            raise ValidationError("Seuls les administrateurs peuvent forcer un changement d'étape.")
        
        # Vérifier que c'est bien un changement
        if self.current_stage_id == self.new_stage_id:
            raise ValidationError("L'étape sélectionnée est identique à l'étape actuelle.")
        
        # Effectuer le changement avec bypass
        old_stage_name = self.current_stage_id.name
        new_stage_name = self.new_stage_id.name
        
        self.chantier_id.with_context(bypass_stage_validation=True).write({
            'stage_id': self.new_stage_id.id
        })
        
        # Log détaillé de l'action forcée
        self.chantier_id.message_post(
            body=f"""
            🚨 CHANGEMENT D'ÉTAPE FORCÉ
            
            👤 Administrateur : {self.env.user.name}
            📅 Date : {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}
            🔄 Transition : {old_stage_name} → {new_stage_name}
            
            📝 Motif :
            {self.reason}
            """,
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '⚠️ Étape forcée',
                'message': f'Chantier passé de "{old_stage_name}" à "{new_stage_name}"',
                'type': 'warning',
                'sticky': True
            }
        } 