from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


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
                        "Le total des pourcentages doit être égal à 100% "
                        "(actuellement {}%)".format(total)
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
            'name': 'Étapes de facturation - {}'.format(self.name),
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

    def create_invoice_schedule_for_chantier(self, chantier_id, quote_id, lot_ids=None, margin_percentage=0.0):
        """
        Créer un planning de facturation pour un chantier basé sur ce cycle de facturation
        
        Args:
            chantier_id: ID du chantier
            quote_id: ID du devis accepté qui servira de base pour les calculs
            lot_ids: Liste des IDs des lots concernés (optionnel, par défaut tous les lots du chantier)
            margin_percentage: Pourcentage de marge à déduire
        
        Returns:
            Recordset des planifications de facturation créées
        """
        self.ensure_one()
        
        chantier = self.env['construction.chantier'].browse(chantier_id)
        quote = self.env['sale.order'].browse(quote_id)
        
        if not chantier.exists():
            raise ValidationError("Le chantier spécifié n'existe pas.")
            
        if not quote.exists() or quote.state not in ['sale', 'done']:
            raise ValidationError("Le devis doit être confirmé (état 'sale' ou 'done').")
            
        if quote.chantier_id != chantier:
            raise ValidationError("Le devis doit être lié au même chantier.")
        
        # Si pas de lots spécifiés, utiliser tous les lots du chantier
        if not lot_ids:
            lot_ids = chantier.lots_ids.ids
        
        schedules = self.env['construction.invoice.schedule']
        
        # Créer une planification pour chaque ligne du cycle
        for line in self.line_ids:
            schedule_vals = {
                'chantier_id': chantier_id,
                'invoice_type_line_id': line.id,
                'quote_id': quote_id,
                'margin_percentage': margin_percentage,
                'lot_ids': [(6, 0, lot_ids)],  # Many2many set
                'name': line.name,
                'sequence': line.sequence,
                'trigger_percentage': line.trigger_percentage,
                'amount_percentage': line.percentage,
                'is_advance_payment': line.is_advance_payment,
                'state': 'planned',
                'notes': "Généré automatiquement du cycle '{}' pour le devis {}".format(self.name, quote.name)
            }
            
            schedule = self.env['construction.invoice.schedule'].create(schedule_vals)
            schedules |= schedule
        
        # Message de confirmation sur le chantier
        body_msg = "📋 Planning de facturation créé : cycle '{}' basé sur le devis {} ({} étapes, {} lots, marge {}%)".format(
            self.name, quote.name, len(schedules), len(lot_ids), margin_percentage
        )
        chantier.message_post(
            body=body_msg,
            message_type='notification'
        )
        
        return schedules


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

    @api.depends('name', 'trigger_percentage', 'percentage', 'is_advance_payment')
    def _compute_display_name(self):
        for rec in self:
            if rec.is_advance_payment:
                rec.display_name = "{} (Signature - {}%)".format(rec.name or '', rec.percentage or 0)
            else:
                rec.display_name = "{} ({}% → {}%)".format(
                    rec.name or '', 
                    rec.trigger_percentage or 0, 
                    rec.percentage or 0
                )

    @api.constrains('trigger_percentage', 'is_advance_payment')
    def _check_advance_payment_logic(self):
        for record in self:
            if record.is_advance_payment and record.trigger_percentage != 0:
                raise ValidationError(
                    "Un acompte de signature doit avoir un déclenchement à 0% "
                    "(avant le début des travaux)."
                )


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

    # Nouveau : référence au devis accepté pour la facturation
    quote_id = fields.Many2one(
        'sale.order',
        string="Devis de référence",
        help="Devis accepté servant de base pour calculer les montants de facturation",
        domain="[('chantier_id', '=', chantier_id), ('state', 'in', ['sale', 'done'])]"
    )

    # Nouveau : marge sélectionnée à déduire
    margin_percentage = fields.Float(
        string="Marge sélectionnée (%)",
        default=0.0,
        help="Marge à déduire des montants du devis pour calculer le prix des lots"
    )

    # Nouveau : lots concernés par cette facturation
    lot_ids = fields.Many2many(
        'construction.lot',
        'invoice_schedule_lot_rel',
        'schedule_id', 'lot_id',
        string="Lots concernés",
        help="Lots du chantier concernés par cette facture"
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

    @api.depends('chantier_id.total_cost', 'amount_percentage', 'quote_id', 'margin_percentage', 'lot_ids')
    def _compute_amount_fixed(self):
        for record in self:
            # Nouveau calcul basé sur le devis accepté et les lots sélectionnés avec marge
            if record.quote_id and record.lot_ids:
                total_amount = 0.0
                
                # Méthode 1: Recherche des lignes du devis par sections de lots
                # Les sections de lots sont créées par l'assistant de devis avec le pattern "📋 {lot.name}"
                for lot in record.lot_ids:
                    lot_section_name = "📋 {}".format(lot.name)
                    
                    # Trouver la section du lot dans le devis
                    section_line = record.quote_id.order_line.filtered(
                        lambda line: line.display_type == 'line_section' and 
                        line.name == lot_section_name
                    )
                    
                    if section_line:
                        # Récupérer toutes les lignes produits qui suivent cette section
                        # jusqu'à la prochaine section ou la fin du devis
                        section_sequence = section_line.sequence
                        next_section = record.quote_id.order_line.filtered(
                            lambda line: line.display_type == 'line_section' and 
                            line.sequence > section_sequence
                        ).sorted('sequence')
                        
                        # Définir la plage de séquences pour ce lot
                        end_sequence = next_section[0].sequence if next_section else float('inf')
                        
                        # Récupérer les lignes produits dans cette section
                        lot_lines = record.quote_id.order_line.filtered(
                            lambda line: not line.display_type and 
                            section_sequence < line.sequence < end_sequence
                        )
                        
                        # Calculer le montant total de ce lot avec la marge appliquée
                        lot_subtotal = sum(lot_lines.mapped('price_subtotal'))
                        lot_amount_with_margin = lot_subtotal * (1 - record.margin_percentage / 100)
                        total_amount += lot_amount_with_margin
                
                # Méthode 2 (fallback): Si pas de sections trouvées, chercher par lot_ids sur les lignes
                if total_amount == 0.0:
                    quote_lines = record.quote_id.order_line.filtered(
                        lambda line: hasattr(line, 'lot_ids') and not line.display_type and
                        any(lot in record.lot_ids for lot in line.lot_ids)
                    )
                    
                    if quote_lines:
                        for line in quote_lines:
                            # Appliquer la marge : prix_lot = prix_devis * (1 - marge/100)
                            line_amount = line.price_subtotal * (1 - record.margin_percentage / 100)
                            total_amount += line_amount
                
                # Méthode 3 (fallback final): Répartition proportionnelle
                if total_amount == 0.0 and record.chantier_id.lots_ids and record.quote_id.amount_total:
                    lot_ratio = len(record.lot_ids) / len(record.chantier_id.lots_ids)
                    base_amount = record.quote_id.amount_total * lot_ratio
                    total_amount = base_amount * (1 - record.margin_percentage / 100)
                
                # Appliquer le pourcentage de cette étape de facturation
                record.amount_fixed = total_amount * (record.amount_percentage / 100)
                
            elif record.chantier_id and record.chantier_id.total_cost:
                # Ancien calcul (fallback) - utilisation du coût total du chantier
                record.amount_fixed = record.chantier_id.total_cost * (record.amount_percentage / 100)
            else:
                record.amount_fixed = 0.0

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
                "Le chantier n'a pas encore atteint {}% d'avancement "
                "(actuellement {}%)".format(self.trigger_percentage, self.chantier_id.progress)
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

                # Notifier sur le chantier en utilisant message_notify pour éviter l'erreur lors des calculs
                try:
                    # Utiliser une référence directe au chantier pour éviter les problèmes de contexte
                    chantier = self.env['construction.chantier'].browse(record.chantier_id.id)
                    body_msg = "📊 Facturation automatique déclenchée : {} (Avancement: {}% ≥ {}%)".format(
                        record.name, current_progress, record.trigger_percentage
                    )
                    chantier.sudo().message_post(
                        body=body_msg,
                        message_type='notification'
                    )
                except Exception:
                    # En cas d'échec, on continue sans bloquer le processus
                    pass

                # Création automatique de la facture et envoi d'email
                record._auto_create_and_send_invoice()

    # ------------------------------------------------------------------
    #  NOUVEAU : génération de facture + email automatique
    # ------------------------------------------------------------------

    def _auto_create_and_send_invoice(self):
        """Créer la facture et envoyer l'email automatiquement."""
        for rec in self:
            if rec.state != 'ready' or rec.invoice_id:
                continue

            chantier = rec.chantier_id
            partner = chantier.client

            # Créer la facture
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_origin': chantier.name,
                'invoice_date': fields.Date.today(),
                'ref': "Chantier {} - {}".format(chantier.name, rec.name),
                'invoice_line_ids': [(0, 0, {
                    'name': "{} - {}".format(rec.name, chantier.name),
                    'quantity': 1,
                    'price_unit': rec.amount_fixed,
                    'account_id': partner.property_account_receivable_id.id,
                })],
            }

            invoice = rec.env['account.move'].create(invoice_vals)
            
            # Poster la facture pour avoir un numéro officiel
            try:
                invoice.action_post()
            except Exception as e:
                # Si impossible de poster, continuer avec le brouillon
                _logger.warning("Impossible de poster automatiquement la facture %s: %s", invoice.id, str(e))

            # Marquer la planification comme facturée
            rec.write({
                'invoice_id': invoice.id,
                'state': 'invoiced',
                'invoice_date': fields.Date.today()
            })
            
            # Préparer les informations pour le chatter
            invoice_ref = invoice.name if invoice.name and invoice.name != '/' else "FACT-{}".format(invoice.id)
            
            # Créer un message détaillé dans le chatter du chantier
            lot_names = ', '.join(rec.lot_ids.mapped('name')) if rec.lot_ids else 'N/A'
            quote_name = rec.quote_id.name if rec.quote_id else 'N/A'
            date_str = fields.Date.today().strftime('%d/%m/%Y')
            
            message_body = """
            <div class="alert alert-success">
                <h4>🧾 Facture générée automatiquement</h4>
                <ul>
                    <li><strong>Référence:</strong> {}</li>
                    <li><strong>Étape:</strong> {}</li>
                    <li><strong>Montant:</strong> {:,.2f} €</li>
                    <li><strong>Client:</strong> {}</li>
                    <li><strong>Lots concernés:</strong> {}</li>
                    <li><strong>Devis de référence:</strong> {}</li>
                    <li><strong>Date:</strong> {}</li>
                </ul>
            </div>
            """.format(
                invoice_ref,
                rec.name,
                rec.amount_fixed,
                partner.name,
                lot_names,
                quote_name,
                date_str
            )
            
            # Poster le message principal avec les détails
            subject_text = "💰 Facture {} générée".format(invoice_ref)
            message = chantier.message_post(
                body=message_body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                subject=subject_text
            )
            
            # Essayer d'attacher le PDF de la facture au message
            try:
                # Générer le PDF de la facture
                pdf_content = rec.env['ir.actions.report']._render_qweb_pdf(
                    'account.account_invoices', [invoice.id]
                )[0]
                
                # Créer la pièce jointe
                attachment = rec.env['ir.attachment'].create({
                    'name': "{}.pdf".format(invoice_ref),
                    'type': 'binary',
                    'datas': pdf_content,
                    'res_model': 'construction.chantier',
                    'res_id': chantier.id,
                    'mimetype': 'application/pdf',
                })
                
                # Lier la pièce jointe au message
                message.attachment_ids = [(6, 0, [attachment.id])]
                
                # Message de confirmation avec pièce jointe
                attachment_url = "/web/content/{}".format(attachment.id)
                pdf_message = "📎 Facture PDF générée et attachée : <a href='{}' target='_blank'>{}</a>".format(
                    attachment_url, attachment.name
                )
                chantier.message_post(
                    body=pdf_message,
                    message_type='notification'
                )
                
            except Exception as e:
                _logger.warning("Impossible de générer le PDF pour la facture %s: %s", invoice.id, str(e))
                chantier.message_post(
                    body="⚠️ Facture créée mais PDF non généré automatiquement. Vous pouvez l'imprimer depuis la facture.",
                    message_type='notification'
                )

            # Envoyer l'email au client si le template existe
            email_sent = False
            try:
                template = rec.env.ref('construction_base.email_template_invoice_ready')
                if template:
                    template.send_mail(invoice.id, force_send=True)
                    email_sent = True
            except ValueError:
                # Template absent
                _logger.info("Template email non trouvé pour la facture %s", invoice.id)
            except Exception as e:
                _logger.warning("Erreur lors de l'envoi de l'email pour la facture %s: %s", invoice.id, str(e))
            
            # Message de confirmation d'envoi email
            if email_sent:
                email_body = "📧 Email de facture envoyé automatiquement à {}".format(partner.email)
                chantier.message_post(
                    body=email_body,
                    message_type='notification'
                )
            else:
                chantier.message_post(
                    body="ℹ️ Facture créée - Email non envoyé automatiquement (vérifiez la configuration des templates)",
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

        body_msg = "Facture créée : {} - {:,.2f} € ({}%)".format(
            self.name, self.amount_fixed, self.amount_percentage
        )
        self.chantier_id.message_post(
            body=body_msg,
            message_type='notification'
        )

    @api.depends('name', 'trigger_percentage', 'amount_percentage', 'is_advance_payment')
    def _compute_display_name(self):
        for rec in self:
            if rec.is_advance_payment:
                rec.display_name = "{} (Signature - {}%)".format(rec.name or '', rec.amount_percentage or 0)
            else:
                rec.display_name = "{} ({}% → {}%)".format(
                    rec.name or '', 
                    rec.trigger_percentage or 0, 
                    rec.amount_percentage or 0
                )
