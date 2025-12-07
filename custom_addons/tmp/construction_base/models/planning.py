# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta

class ConstructionPlanningTask(models.Model):
        _name = 'construction.planning.task'
        _description = 'Tâche de planning chantier'
        _inherit = ['mail.thread', 'mail.activity.mixin']
        _order = 'date_start, date_stop, chantier_id, lot_id'

        name = fields.Char('Nom de la tâche', required=True, tracking=True)
        chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, ondelete='cascade', tracking=True)
        lot_id = fields.Many2one('construction.lot', string='Lot', ondelete='set null', tracking=True)
        subcontractor_id = fields.Many2one('res.partner', string='Sous-traitant', domain="[('supplier_rank', '>', 0)]", tracking=True)
        date_start = fields.Datetime('Date de début', required=True, tracking=True)
        date_stop = fields.Datetime('Date de fin', required=True, tracking=True)
        color = fields.Integer('Couleur', default=0)
        state = fields.Selection([
            ('draft', 'Brouillon'),
            ('planned', 'Planifiée'),
            ('in_progress', 'En cours'),
            ('done', 'Terminée'),
            ('cancelled', 'Annulée')
        ], string='Statut', default='planned', tracking=True)
        description = fields.Text('Description')
        notes = fields.Text('Notes internes')

        # Champs calculés pour les contraintes de dates
        chantier_date_start = fields.Date(related='chantier_id.date_start_contract', string='Date début chantier', store=True)
        chantier_date_end = fields.Date(related='chantier_id.date_end_contract', string='Date fin chantier', store=True)
        is_out_of_bounds = fields.Boolean('Hors limites', compute='_compute_is_out_of_bounds', store=True,
                                         help="Indique si la tâche est en dehors des dates du chantier")

        _sql_constraints = [
            ('date_check', 'CHECK(date_stop >= date_start)', 'La date de fin doit être postérieure à la date de début !'),
        ]

        @api.depends('date_start', 'date_stop', 'chantier_date_start', 'chantier_date_end')
        def _compute_is_out_of_bounds(self):
            """Calcule si la tâche est en dehors des dates du chantier."""
            for task in self:
                out_of_bounds = False
                if task.chantier_date_start and task.date_start:
                    task_date_start = task.date_start.date()
                    if task_date_start < task.chantier_date_start:
                        out_of_bounds = True

                if task.chantier_date_end and task.date_stop:
                    task_date_stop = task.date_stop.date()
                    if task_date_stop > task.chantier_date_end:
                        out_of_bounds = True

                task.is_out_of_bounds = out_of_bounds

                # Mettre à jour la couleur si hors limites
                if out_of_bounds and task.color == 0:  # Ne pas écraser une couleur déjà définie
                    task.color = 2  # Rouge pour indiquer hors limites

        @api.onchange('date_start', 'date_stop', 'chantier_id')
        def _onchange_dates(self):
            """Vérifie et ajuste les dates si nécessaire lors de leur modification."""
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

        @api.constrains('date_start', 'date_stop', 'chantier_id')
        def _check_dates_within_chantier(self):
            """Vérifie que les dates de la tâche sont dans les limites du chantier."""
            for task in self:
                if not task.chantier_id or not task.date_start or not task.date_stop:
                    continue

                # Convertir les datetime en date pour comparaison
                task_date_start = task.date_start.date()
                task_date_stop = task.date_stop.date()

                error_messages = []

                if task.chantier_date_start and task_date_start < task.chantier_date_start:
                    error_messages.append(f"La date de début ({task_date_start}) est antérieure à la date de début du chantier ({task.chantier_date_start})")

                if task.chantier_date_end and task_date_stop > task.chantier_date_end:
                    error_messages.append(f"La date de fin ({task_date_stop}) est postérieure à la date de fin du chantier ({task.chantier_date_end})")

                if error_messages:
                    raise ValidationError("Erreur de dates: " + ", ".join(error_messages))

        @api.depends('name', 'chantier_id', 'lot_id')
        def _compute_display_name(self):
            for rec in self:
                parts = [rec.name]
                if rec.lot_id:
                    parts.append(rec.lot_id.name)
                if rec.chantier_id:
                    parts.append(rec.chantier_id.name)
                rec.display_name = ' - '.join(parts)

        def action_create_planning_task(self):
            """Ouvre le wizard de création de tâche de planning pour le chantier de cette tâche."""
            self.ensure_one()
            return {
                'type': 'ir.actions.act_window',
                'name': 'Créer une tâche de planning',
                'res_model': 'construction.planning.task.create',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_chantier_id': self.chantier_id.id,
                    'available_lot_ids': self.chantier_id.lots_ids.ids
                }
            }

        @api.model
        def init_all_chantier_tasks(self):
            """Initialise les tâches pour tous les chantiers actifs qui ont des lots mais pas de tâches."""
            # Récupérer tous les chantiers actifs qui ont des lots
            chantiers = self.env['construction.chantier'].search([
                ('state', '=', 'active'),
                ('lots_ids', '!=', False)
            ])

            for chantier in chantiers:
                # Vérifier si des tâches existent déjà pour ce chantier
                existing_tasks = self.search([
                    ('chantier_id', '=', chantier.id)
                ])

                # Si aucune tâche n'existe, initialiser une tâche vide pour chaque lot
                if not existing_tasks and chantier.lots_ids:
                    for lot in chantier.lots_ids:
                        # Vérifier si une tâche existe déjà pour ce lot
                        lot_task = self.search([
                            ('chantier_id', '=', chantier.id),
                            ('lot_id', '=', lot.id)
                        ], limit=1)

                        if not lot_task:
                            # Créer une tâche vide pour ce lot
                            self.create({
                                'name': f'Tâche {lot.name}',
                                'chantier_id': chantier.id,
                                'lot_id': lot.id,
                                'date_start': chantier.date_start_contract or fields.Datetime.now(),
                                'date_stop': chantier.date_end_contract or fields.Datetime.now() + timedelta(days=30),
                                'state': 'draft'
                            })

            return True

        def export_to_pdf(self):
            """Exporte le planning au format PDF."""
            self.ensure_one()

            # Déterminer le contexte de l'export (chantier spécifique ou global)
            domain = []
            title = "Planning Global des Chantiers"

            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')

            if active_model == 'construction.chantier' and active_id:
                chantier = self.env['construction.chantier'].browse(active_id)
                domain = [('chantier_id', '=', chantier.id)]
                title = f"Planning - {chantier.name}"

            # Générer le rapport PDF
            return self.env.ref('construction_base.action_report_planning').report_action(
                self.search(domain), 
                data={
                    'title': title,
                    'date_generation': fields.Datetime.now(),
                }
            )

        def export_to_excel(self):
            """Exporte le planning au format Excel."""
            self.ensure_one()

            # Déterminer le contexte de l'export (chantier spécifique ou global)
            domain = []
            filename = "planning_global.xlsx"

            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')

            if active_model == 'construction.chantier' and active_id:
                chantier = self.env['construction.chantier'].browse(active_id)
                domain = [('chantier_id', '=', chantier.id)]
                filename = f"planning_{chantier.name.replace(' ', '_').lower()}.xlsx"

            # Récupérer les données à exporter
            tasks = self.search(domain)

            # Créer le fichier Excel
            import io
            import xlsxwriter

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet('Planning')

            # Styles
            header_format = workbook.add_format({'bold': True, 'bg_color': '#CCCCCC', 'border': 1})
            cell_format = workbook.add_format({'border': 1})
            date_format = workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy hh:mm'})

            # En-têtes
            headers = ['Tâche', 'Chantier', 'Lot', 'Sous-traitant', 'Date début', 'Date fin', 'Statut']
            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            # Données
            for row, task in enumerate(tasks, 1):
                worksheet.write(row, 0, task.name, cell_format)
                worksheet.write(row, 1, task.chantier_id.name, cell_format)
                worksheet.write(row, 2, task.lot_id.name if task.lot_id else '', cell_format)
                worksheet.write(row, 3, task.subcontractor_id.name if task.subcontractor_id else '', cell_format)
                worksheet.write(row, 4, task.date_start, date_format)
                worksheet.write(row, 5, task.date_stop, date_format)
                worksheet.write(row, 6, dict(task._fields['state'].selection).get(task.state), cell_format)

            # Ajuster la largeur des colonnes
            for col in range(len(headers)):
                worksheet.set_column(col, col, 20)

            workbook.close()
            output.seek(0)

            # Retourner le fichier Excel
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content?model=construction.planning.task&field=excel_file&filename={filename}&download=true',
                'target': 'self',
                'context': {
                    'excel_file': output.read().encode('base64'),
                }
            }
