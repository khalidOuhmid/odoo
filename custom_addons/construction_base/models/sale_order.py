# models/sale_order.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ✅ LIEN VERS LE CHANTIER
    chantier_id = fields.Many2one('construction.chantier', string='Chantier')
    lot_ids = fields.Many2many('lot', string='Lots concernés')
    
    # Champs pour la facturation par paliers
    invoice_milestone = fields.Selection([
        ('none', 'Aucun'),
        ('30', '30% - Premier acompte'),
        ('60', '60% - Deuxième acompte'),
        ('90', '90% - Troisième acompte'),
        ('100', '100% - Solde avec retenue'),
    ], string='Palier de facturation', default='none')
    
    has_retention = fields.Boolean(
        string='Retenue de garantie appliquée',
        default=False,
        help="Indique si une retenue de garantie de 5% a été appliquée"
    )
    
    retention_amount = fields.Monetary(
        string='Montant retenue de garantie',
        compute='_compute_retention_amount',
        store=True
    )

    # ✅ ÉTATS PERSONNALISÉS POUR LE WORKFLOW CONSTRUCTION
    state = fields.Selection(
        selection_add=[
            ('validated', 'Devis validé'),
            ('no_follow', 'Sans suite'),
            ('draft',)  # Maintenir l'ordre
        ],
        ondelete={
            'validated': 'cascade',
            'no_follow': 'cascade'
        }
    )
    
    @api.depends('amount_total', 'has_retention')
    def _compute_retention_amount(self):
        """Calculer le montant de la retenue de garantie (5%)"""
        for order in self:
            if order.has_retention:
                order.retention_amount = order.amount_total * 0.05
            else:
                order.retention_amount = 0.0

    def action_validate_quote(self):
        """Valider le devis et faire progresser le chantier"""
        self.write({'state': 'validated'})

        # Faire progresser le chantier vers "Devis accepté"
        if self.chantier_id:
            try:
                next_stage = self.env.ref('construction_base.stage_devis_accepte')
                self.chantier_id.stage_id = next_stage

                # Log de l'action
                self.chantier_id.message_post(
                    body=f"Devis {self.name} validé - Passage à l'étape '{next_stage.name}'"
                )
            except ValueError:
                pass  # Stage non trouvé

        return True

    def action_mark_no_follow(self):
        """Marquer sans suite et archiver le chantier"""
        self.write({'state': 'no_follow'})

        # Déplacer le chantier vers "Sans suite"
        if self.chantier_id:
            try:
                archive_stage = self.env.ref('construction_base.stage_sans_suite')
                self.chantier_id.write({
                    'stage_id': archive_stage.id,
                    'state': 'abandoned'
                })

                # Log de l'action
                self.chantier_id.message_post(
                    body=f"Devis {self.name} marqué sans suite - Chantier archivé"
                )
            except ValueError:
                pass

        return True
    
    def action_create_milestone_invoice(self):
        """Créer une facture selon le palier de progression du chantier"""
        self.ensure_one()
        
        if not self.chantier_id:
            raise ValidationError("Cette commande n'est pas liée à un chantier.")
        
        progress = self.chantier_id.progress
        
        # Déterminer le palier de facturation
        if progress >= 90:
            milestone = '90'
            percentage = 0.90
        elif progress >= 60:
            milestone = '60'
            percentage = 0.60
        elif progress >= 30:
            milestone = '30'
            percentage = 0.30
        else:
            raise ValidationError("Le chantier doit avoir au moins 30% de progression pour facturer.")
        
        # Vérifier si ce palier a déjà été facturé
        existing_invoices = self.invoice_ids.filtered(
            lambda inv: inv.state != 'cancel' and 
            inv.invoice_origin and milestone in inv.invoice_origin
        )
        
        if existing_invoices:
            raise ValidationError(f"Le palier {milestone}% a déjà été facturé.")
        
        # Créer la facture
        invoice_vals = self._prepare_invoice()
        invoice_vals['invoice_origin'] = f"{self.name} - Acompte {milestone}%"
        
        # Si c'est le dernier palier (90%), appliquer la retenue de garantie
        if milestone == '90':
            self.has_retention = True
            invoice_vals['narration'] = (
                f"Facture d'acompte à {milestone}% de l'avancement des travaux.\n"
                f"Une retenue de garantie de 5% ({self.retention_amount:.2f} €) sera appliquée."
            )
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Créer les lignes de facture avec le pourcentage approprié
        for line in self.order_line:
            if line.display_type:
                continue
                
            invoice_line_vals = line._prepare_invoice_line()
            
            # Ajuster la quantité selon le pourcentage du palier
            # moins ce qui a déjà été facturé
            already_invoiced_qty = sum(
                self.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
                .invoice_line_ids.filtered(lambda l: l.product_id == line.product_id)
                .mapped('quantity')
            )
            
            to_invoice_qty = (line.product_uom_qty * percentage) - already_invoiced_qty
            
            if to_invoice_qty > 0:
                invoice_line_vals.update({
                    'move_id': invoice.id,
                    'quantity': to_invoice_qty,
                })
                self.env['account.move.line'].create(invoice_line_vals)
        
        # Mettre à jour le palier de facturation
        self.invoice_milestone = milestone
        
        # Ouvrir la facture créée
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facture',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
