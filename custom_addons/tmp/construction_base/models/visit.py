from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64


class Visit(models.Model):
    _name = 'construction.visit'
    _description = 'Construction Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    name = fields.Char('Name', required=True, translate=True)
    description = fields.Text('Description', translate=True)
    chantier_id = fields.Many2one('construction.chantier', string='Chantier', required=True, ondelete='cascade')
    date = fields.Datetime('Date et heure', required=True, tracking=True)
    duration = fields.Float('Durée (heures)', default=2.0)

    user_ids = fields.Many2many('res.users', string='Intervenants internes')
    partner_ids = fields.Many2many('res.partner', string='Participants externes')

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifiée'),
        ('confirmed', 'Confirmée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut', default='draft', required=True, tracking=True)

    description = fields.Html('Description')
    notes = fields.Html('Notes et observations')
    report = fields.Html('Rapport de visite')
    visit_type = fields.Selection([
        ('initial', 'Visite initiale'),
        ('progress', 'Suivi de chantier'),
        ('quality', 'Contrôle qualité'),
        ('final', 'Réception')
    ], string='Type de visite', default='progress')

    @api.depends('name', 'chantier_id', 'date')
    def _compute_display_name(self):
        for visite in self:
            if visite.chantier_id and visite.date:
                visite.display_name = f"{visite.name} - {visite.chantier_id.name}"
            else:
                visite.display_name = visite.name or 'Nouvelle visite'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                chantier = self.env['construction.chantier'].browse(vals.get('chantier_id'))
                sequence = self.search_count([('chantier_id', '=', vals.get('chantier_id'))]) + 1
                vals['name'] = f"Visite {sequence} - {chantier.name}"
        return super().create(vals_list)

    # State transition methods
    def action_confirm(self):
        """Confirmer la visite"""
        for visite in self:
            if visite.state not in ['draft', 'planned']:
                raise ValidationError(_("Seules les visites en brouillon ou planifiées peuvent être confirmées."))
            visite.state = 'confirmed'
            visite.message_post(body=_("Visite confirmée"))



    def action_start(self):
        """Démarrer la visite"""
        for visite in self:
            if visite.state != 'confirmed':
                raise ValidationError(_("Seules les visites confirmées peuvent être démarrées."))
            visite.state = 'in_progress'
            visite.message_post(body=_("Visite démarrée"))

    def action_complete(self):
        """Terminer la visite"""
        for visite in self:
            if visite.state != 'in_progress':
                raise ValidationError(_("Seules les visites en cours peuvent être terminées."))
            visite.state = 'completed'
            visite.message_post(body=_("Visite terminée"))
            # Générer et attacher le rapport PDF automatiquement
            try:
                visite._generate_and_attach_report()
            except Exception as e:
                # Ne pas bloquer la fin de visite si le report échoue
                visite.message_post(body=_("Erreur lors de la génération du rapport: %s") % str(e))

    def action_cancel(self):
        """Annuler la visite"""
        for visite in self:
            if visite.state in ['completed', 'cancelled']:
                raise ValidationError(_("Cette visite ne peut pas être annulée."))
            visite.state = 'cancelled'
            visite.message_post(body=_("Visite annulée"))

    def action_reset_to_planned(self):
        """Remettre en planifiée"""
        for visite in self:
            visite.state = 'planned'
            visite.message_post(body=_("Visite remise en planification"))

    # ------------------------------------------------------------------
    # Report helpers
    # ------------------------------------------------------------------
    def _generate_and_attach_report(self):
        """Génère le PDF du rapport de visite et l'attache à l'enregistrement.

        - Utilise l'action de report QWeb `construction_base.action_visit_report`.
        - Crée un `ir.attachment` lié à la visite.
        - Poste un message avec la pièce jointe.
        """
        self.ensure_one()
        report_action = self.env.ref('construction_base.action_visit_report', raise_if_not_found=False)
        if not report_action:
            return False

        # Rendu PDF
        pdf_bytes, _content_type = report_action._render_qweb_pdf(self.ids)
        pdf_b64 = base64.b64encode(pdf_bytes)

        safe_name = (self.name or 'Visite').replace('/', '_').replace('\n', ' ').strip()
        filename = f"Rapport_visite_{safe_name}.pdf"

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/pdf',
            'datas': pdf_b64,
        })

        self.message_post(
            body=_('Rapport de visite généré et attaché.'),
            attachment_ids=[attachment.id]
        )

        return True

    def _get_report_attachments(self):
        """Retourne les pièces jointes de la visite, séparées par type.

        Returns:
            dict: {
                'images': recordset ir.attachment,
                'others': recordset ir.attachment,
            }
        """
        self.ensure_one()
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ], order='create_date')

        image_attachments = attachments.filtered(lambda a: (a.mimetype or '').startswith('image/'))
        other_attachments = attachments - image_attachments

        return {
            'images': image_attachments,
            'others': other_attachments,
        }

    def action_print_report(self):
        """Action bouton pour imprimer le rapport de visite."""
        self.ensure_one()
        action = self.env.ref('construction_base.action_visit_report', raise_if_not_found=False)
        if not action:
            raise ValidationError(_('Action de rapport introuvable.'))
        return action.report_action(self)

    def action_view_calendar(self):
        return {
            'name': 'Planning des Visites',
            'type': 'ir.actions.act_window',
            'res_model': 'construction.visit',
            'view_mode': 'calendar',
            'view_id': self.env.ref('construction_base.view_visit_calendar').id,
            'target': 'current',
            'domain': [('id', '=', self.id)],
            'context': {'search_default_id': self.id}
        }