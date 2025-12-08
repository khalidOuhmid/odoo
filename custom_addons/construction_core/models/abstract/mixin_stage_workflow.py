# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ConstructionStageValidator(models.AbstractModel):
    """
    Abstract Strategy for Stage Validation.
    Concrete classes should implement `validate(record)`.
    """
    _name = 'construction.stage.validator'
    _description = 'Abstract Stage Validator'

    @api.model
    def validate(self, record):
        """
        Validate the transition for the given record.
        :param record: The record (Chantier, Lot...) trying to change stage
        :return: (bool, str) -> (Success, Error Message)
        """
        raise NotImplementedError("Validators must implement validate()")


class ConstructionStageMixin(models.AbstractModel):
    """
    Mixin to add stage validation capabilities to a model.
    """
    _name = 'construction.stage.mixin'
    _description = 'Stage Management Mixin'

    stage_id = fields.Many2one('construction.stage', string="Etape", tracking=True)

    def action_move_to_stage(self, target_stage_id):
        """
        Generic method to move to a target stage with validation.
        """
        self.ensure_one()
        target_stage = self.env['construction.stage'].browse(target_stage_id)
        
        # 1. Find validator
        if target_stage.validator_model:
            validator = self.env[target_stage.validator_model]
            success, msg = validator.validate(self)
            if not success:
                # Log failure if audit mixin is present
                if hasattr(self, '_log_transition_attempt'):
                    self._log_transition_attempt(target_stage, False, msg)
                
                # Notify user
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("Validation échouée"),
                        'message': msg,
                        'type': 'danger',
                        'sticky': True,
                    }
                }

        # 2. Perform transition
        self.write({'stage_id': target_stage.id})
        
        if hasattr(self, '_log_transition_attempt'):
            self._log_transition_attempt(target_stage, True)
            
        return True
