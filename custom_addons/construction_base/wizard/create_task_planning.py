from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta

class CreateTaskPlanning(models.TransientModel):
    _name = 'construction.planning.task.create'
    _description = 'Création de tache de planning'

    name = fields.Char('Nom de la tâche', required=True)
    lot_id = fields.Many2one('construction.lot', string='Lot', required=True, domain="[('id', 'in', available_lot_ids)]")
    chantier_id = fields.Many2one(
        'construction.chantier',
        string='Chantier',
        required=True,
        readonly=True,
        help="Chantier concerné"
    )
    available_lot_ids = fields.Many2many('construction.lot', compute='_compute_available_lots')
    chantier_date_start = fields.Date(related='chantier_id.date_start_contract', string='Date début chantier', readonly=True)
    chantier_date_end = fields.Date(related='chantier_id.date_end_contract', string='Date fin chantier', readonly=True)
    date_start = fields.Datetime('Date de début', required=True)
    date_stop = fields.Datetime('Date de fin', required=True)
    duration = fields.Float('Durée (jours)', compute='_compute_duration', store=True)
    is_out_of_bounds = fields.Boolean('Hors limites', compute='_compute_is_out_of_bounds', 
                                     help="Indique si la tâche est en dehors des dates du chantier")
    selected_subcontractor_id = fields.Many2one(
        'res.partner',
        string='Sous-traitant sélectionné',
        required=True,
        domain="[('id', 'in', available_subcontractor_ids)]",
        help="Choisissez le sous-traitant à assigner"
    )
    available_subcontractor_ids = fields.Many2many(
        'res.partner',
        string='Sous-traitants disponibles',
        compute='_compute_available_subcontractors'
    )

    @api.depends('date_start', 'date_stop')
    def _compute_duration(self):
        for record in self:
            if record.date_start and record.date_stop:
                delta = record.date_stop - record.date_start
                record.duration = delta.total_seconds() / (24 * 3600)  # Convertir en jours
            else:
                record.duration = 0.0

    @api.depends('date_start', 'date_stop', 'chantier_date_start', 'chantier_date_end')
    def _compute_is_out_of_bounds(self):
        """Calcule si la tâche est en dehors des dates du chantier."""
        for wizard in self:
            out_of_bounds = False
            if wizard.chantier_date_start and wizard.date_start:
                task_date_start = wizard.date_start.date()
                if task_date_start < wizard.chantier_date_start:
                    out_of_bounds = True

            if wizard.chantier_date_end and wizard.date_stop:
                task_date_stop = wizard.date_stop.date()
                if task_date_stop > wizard.chantier_date_end:
                    out_of_bounds = True

            wizard.is_out_of_bounds = out_of_bounds

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        self._compute_available_subcontractors()

    @api.onchange('date_start', 'date_stop', 'chantier_id')
    def _onchange_dates(self):
        """Vérifie et ajuste les dates si nécessaire lors de leur modification."""
        self._compute_available_subcontractors()

        warning = {}

        if not self.chantier_id or not self.date_start or not self.date_stop:
            return

        # Convertir les datetime en date pour comparaison
        task_date_start = self.date_start.date()
        task_date_stop = self.date_stop.date()

        # Vérifier si les dates sont en dehors des limites du chantier
        date_changed = False
        message_parts = []

        if self.chantier_date_start and task_date_start < self.chantier_date_start:
            # Ajuster la date de début à la date de début du chantier
            self.date_start = fields.Datetime.to_datetime(self.chantier_date_start)
            date_changed = True
            message_parts.append("date de début ajustée à la date de début du chantier")

        if self.chantier_date_end and task_date_stop > self.chantier_date_end:
            # Ajuster la date de fin à la date de fin du chantier
            self.date_stop = fields.Datetime.to_datetime(self.chantier_date_end)
            date_changed = True
            message_parts.append("date de fin ajustée à la date de fin du chantier")

        if date_changed:
            warning = {
                'title': 'Dates ajustées',
                'message': "Les dates de la tâche ont été ajustées pour respecter les limites du chantier: " + ", ".join(message_parts)
            }

        return {'warning': warning} if warning else None
        
    @api.depends('chantier_id')
    def _compute_available_lots(self):
        for wizard in self:
            if wizard.chantier_id:
                wizard.available_lot_ids = [(6, 0, wizard.chantier_id.lots_ids.ids)]
            else:
                wizard.available_lot_ids = [(5, 0, 0)]

    def _compute_available_subcontractors(self):
        for wizard in self:
            if not wizard.lot_id or not wizard.date_start or not wizard.date_stop:
                wizard.available_subcontractor_ids = [(5, 0, 0)]
                continue

            # Récupérer tous les sous-traitants
            all_subcontractors = self.env['res.partner'].search([
                ('supplier_rank', '>', 0)
            ])

            # Filtrer les sous-traitants disponibles (pas de chevauchement de dates)
            available_subcontractors = self.env['res.partner']

            for subcontractor in all_subcontractors:
                # Vérifier si le sous-traitant a des tâches qui se chevauchent
                overlapping_tasks = self.env['construction.planning.task'].search([
                    ('subcontractor_id', '=', subcontractor.id),
                    ('date_start', '<=', wizard.date_stop),
                    ('date_stop', '>=', wizard.date_start),
                    ('chantier_id', '!=', wizard.chantier_id.id)  # Exclure les tâches du chantier actuel
                ])

                if not overlapping_tasks:
                    available_subcontractors += subcontractor

            wizard.available_subcontractor_ids = available_subcontractors

    def action_create_task(self):
        self.ensure_one()

        if not self.date_start or not self.date_stop:
            raise ValidationError(_("Les dates de début et de fin sont obligatoires."))

        if self.date_stop <= self.date_start:
            raise ValidationError(_("La date de fin doit être postérieure à la date de début."))

        # Vérifier que les dates sont dans les limites du chantier
        if self.is_out_of_bounds:
            error_messages = []

            task_date_start = self.date_start.date()
            task_date_stop = self.date_stop.date()

            if self.chantier_date_start and task_date_start < self.chantier_date_start:
                error_messages.append("La date de début ({}) est antérieure à la date de début du chantier ({})".format(task_date_start, self.chantier_date_start))

            if self.chantier_date_end and task_date_stop > self.chantier_date_end:
                error_messages.append("La date de fin ({}) est postérieure à la date de fin du chantier ({})".format(task_date_stop, self.chantier_date_end))

            if error_messages:
                raise ValidationError("Erreur de dates: " + ", ".join(error_messages))

        # Créer la tâche de planning
        task_vals = {
            'name': self.name,
            'chantier_id': self.chantier_id.id,
            'lot_id': self.lot_id.id,
            'subcontractor_id': self.selected_subcontractor_id.id,
            'date_start': self.date_start,
            'date_stop': self.date_stop,
            'state': 'planned'
        }

        task = self.env['construction.planning.task'].create(task_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Tâche de planning'),
            'res_model': 'construction.planning.task',
            'res_id': task.id,
            'view_mode': 'form',
            'target': 'current',
        }
