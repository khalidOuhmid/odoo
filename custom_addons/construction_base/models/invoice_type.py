from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class InvoiceType(models.Model):
    _name = "construction.invoice_type"
    _description = "Cycle de facturation pour les chantiers"
    _order = "sequence, name"

    name = fields.Char(string="Nom du cycle", required=True)
    code = fields.Char(string="Code", required=True, help="Code unique pour identifier le cycle")
    description = fields.Text(string="Description")
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)
    
    # Lignes de facturation
    line_ids = fields.One2many(
        'construction.invoice_type.line', 
        'invoice_type_id', 
        string="Étapes de facturation",
        copy=True
    )
    
    # Champs calculés
    total_percentage = fields.Float(
        string="Total %", 
        compute='_compute_total_percentage',
        store=True,
        help="Somme des pourcentages (doit être 100%)"
    )
    line_count = fields.Integer(
        string="Nombre d'étapes",
        compute='_compute_line_count'
    )
    
    # Contraintes
    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)', 'Le code du cycle de facturation doit être unique.'),
    ]

    @api.depends('line_ids.percentage')
    def _compute_total_percentage(self):
        for record in self:
            record.total_percentage = sum(record.line_ids.mapped('percentage'))

    @api.depends('line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.constrains('line_ids')
    def _check_total_percentage(self):
        for record in self:
            if record.line_ids:
                total = sum(record.line_ids.mapped('percentage'))
                if abs(total - 100.0) > 0.01:  # Tolérance pour les arrondis
                    raise ValidationError(
                        f"Le total des pourcentages doit être égal à 100% "
                        f"(actuellement {total}%)"
                    )

    @api.constrains('line_ids')
    def _check_unique_percentages(self):
        for record in self:
            percentages = record.line_ids.mapped('trigger_percentage')
            if len(percentages) != len(set(percentages)):
                raise ValidationError(
                    "Les pourcentages de déclenchement doivent être uniques dans un même cycle."
                )

    def action_view_lines(self):
        """Action pour voir les lignes de facturation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Étapes de facturation - {self.name}',
            'res_model': 'construction.invoice_type.line',
            'view_mode': 'list,form',
            'domain': [('invoice_type_id', '=', self.id)],
            'context': {
                'default_invoice_type_id': self.id,
            },
            'target': 'current',
        }

    @api.model
    def action_create_new_cycle(self):
        """Action pour créer un nouveau cycle de facturation"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nouveau cycle de facturation',
            'res_model': 'construction.invoice_type',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_active': True,
            }
        }


class InvoiceTypeLine(models.Model):
    _name = "construction.invoice_type.line"
    _description = "Ligne de cycle de facturation"
    _order = "invoice_type_id, sequence, trigger_percentage"

    invoice_type_id = fields.Many2one(
        'construction.invoice_type', 
        string="Cycle de facturation",
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char(string="Description", required=True)
    sequence = fields.Integer(string="Séquence", default=10)
    
    # Déclenchement
    trigger_percentage = fields.Float(
        string="Déclenchement (%)",
        required=True,
        help="Pourcentage d'avancement du chantier qui déclenche cette facture"
    )
    
    # Montant à facturer
    percentage = fields.Float(
        string="Montant (%)",
        required=True,
        help="Pourcentage du montant total à facturer à cette étape"
    )
    
    # Options
    is_advance_payment = fields.Boolean(
        string="Acompte signature",
        help="Cette facture est émise à la signature (avant démarrage travaux)"
    )
    
    notes = fields.Text(string="Notes")
    
    # Contraintes
    _sql_constraints = [
        ('positive_trigger', 'CHECK(trigger_percentage >= 0 AND trigger_percentage <= 100)', 
         'Le pourcentage de déclenchement doit être entre 0 et 100%.'),
        ('positive_amount', 'CHECK(percentage >= 0 AND percentage <= 100)', 
         'Le pourcentage à facturer doit être entre 0 et 100%.'),
    ]

    @api.constrains('trigger_percentage', 'is_advance_payment')
    def _check_advance_payment_logic(self):
        for record in self:
            if record.is_advance_payment and record.trigger_percentage != 0:
                raise ValidationError(
                    "Un acompte de signature doit avoir un déclenchement à 0% "
                    "(avant le début des travaux)."
                )

    def name_get(self):
        result = []
        for record in self:
            if record.is_advance_payment:
                name = f"{record.name} (Signature - {record.percentage}%)"
            else:
                name = f"{record.name} ({record.trigger_percentage}% → {record.percentage}%)"
            result.append((record.id, name))
        return result


class InvoiceSchedule(models.Model):
    _name = "construction.invoice.schedule"
    _description = "Planning de facturation pour un chantier"
    _order = "chantier_id, sequence, trigger_percentage"

    chantier_id = fields.Many2one(
        'construction.chantier',
        string="Chantier",
        required=True,
        ondelete='cascade'
    )
    
    invoice_type_line_id = fields.Many2one(
        'construction.invoice_type.line',
        string="Ligne de cycle",
        help="Ligne du cycle de facturation qui a généré cette planification"
    )
    
    name = fields.Char(string="Description", required=True)
    sequence = fields.Integer(string="Séquence", default=10)
    
    # Déclenchement et montant
    trigger_percentage = fields.Float(
        string="Déclenchement (%)",
        required=True,
        help="Pourcentage d'avancement qui déclenche cette facture"
    )
    amount_percentage = fields.Float(
        string="Montant (%)",
        required=True,
        help="Pourcentage du montant total à facturer"
    )
    amount_fixed = fields.Monetary(
        string="Montant calculé",
        compute='_compute_amount_fixed',
        store=True,
        currency_field='currency_id'
    )
    
    # Dates et suivi
    planned_date = fields.Date(string="Date prévue")
    invoice_date = fields.Date(string="Date de facture")
    payment_date = fields.Date(string="Date de paiement")
    
    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('planned', 'Planifié'),
        ('ready', 'Prêt à facturer'),
        ('invoiced', 'Facturé'),
        ('paid', 'Payé'),
        ('cancelled', 'Annulé')
    ], string="État", default='draft')
    
    # Options
    is_advance_payment = fields.Boolean(
        string="Acompte signature",
        help="Cette facture est émise à la signature"
    )
    is_triggered = fields.Boolean(
        string="Déclenchée",
        help="Le seuil d'avancement a été atteint"
    )
    
    # Liens
    invoice_id = fields.Many2one(
        'account.move',
        string="Facture",
        readonly=True
    )
    
    currency_id = fields.Many2one(
        related='chantier_id.currency_id',
        store=True
    )
    
    notes = fields.Text(string="Notes")

    @api.depends('chantier_id.total_cost', 'amount_percentage')
    def _compute_amount_fixed(self):
        for record in self:
            if record.chantier_id and record.chantier_id.total_cost:
                record.amount_fixed = record.chantier_id.total_cost * (record.amount_percentage / 100)
            else:
                record.amount_fixed = 0

    def action_mark_ready(self):
        """Marquer comme prêt à facturer"""
        self.ensure_one()
        if self.chantier_id.progress >= self.trigger_percentage or self.is_advance_payment:
            self.write({
                'state': 'ready',
                'is_triggered': True
            })
        else:
            raise ValidationError(
                f"Le chantier n'a pas encore atteint {self.trigger_percentage}% d'avancement "
                f"(actuellement {self.chantier_id.progress}%)"
            )

    def check_progress_trigger(self):
        """Vérifier si cette étape doit être déclenchée selon l'avancement"""
        for record in self:
            current_progress = record.chantier_id.progress
            
            # Les acomptes de signature ne se déclenchent pas automatiquement par l'avancement
            # Ils doivent être déclenchés manuellement
            if record.is_advance_payment:
                continue
            
            # Déclencher si le seuil d'avancement est atteint
            should_trigger = current_progress >= record.trigger_percentage
            
            # Marquer comme déclenchée si pas encore fait et conditions remplies
            if should_trigger and record.state == 'planned' and not record.is_triggered:
                record.write({
                    'state': 'ready',
                    'is_triggered': True
                })
                
                # Notifier sur le chantier
                record.chantier_id.message_post(
                    body=f"📊 Facturation automatique déclenchée : {record.name} "
                         f"(Avancement: {current_progress}% ≥ {record.trigger_percentage}%)",
                    message_type='notification'
                )

    def action_create_invoice(self):
        """Créer la facture pour cette étape"""
        self.ensure_one()
        if self.state != 'ready':
            raise ValidationError("Cette étape n'est pas prête à être facturée.")
        
        # Ici on pourrait créer la vraie facture
        # Pour l'instant, on simule
        self.write({
            'state': 'invoiced',
            'invoice_date': fields.Date.today()
        })
        
        self.chantier_id.message_post(
            body=f"Facture créée : {self.name} - {self.amount_fixed:,.2f} € ({self.amount_percentage}%)",
            message_type='notification'
        )

    def name_get(self):
        result = []
        for record in self:
            if record.is_advance_payment:
                name = f"{record.name} (Signature - {record.amount_percentage}%)"
            else:
                name = f"{record.name} ({record.trigger_percentage}% → {record.amount_percentage}%)"
            result.append((record.id, name))
        return result
