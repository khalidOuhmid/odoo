# -*- coding: utf-8 -*-
"""
Extension du modèle sale.order pour la gestion des chantiers de construction
Compatible Odoo 18 - Respecte les conventions de codage officielles
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # =================== LIENS AVEC LES CHANTIERS ===================
    
    chantier_id = fields.Many2one(
        'construction.chantier', 
        string='Chantier',
        help="Chantier de construction lié à ce devis/commande"
    )
    
    lot_ids = fields.Many2many(
        'construction.lot',  # Corrigé: utiliser construction.lot au lieu de lot
        string='Lots concernés',
        help="Lots de construction concernés par ce devis"
    )
    
    # =================== FACTURATION PAR PALIERS ===================
    
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
        store=True,
        currency_field='currency_id'
    )

    # =================== WORKFLOW CONSTRUCTION ===================
    
    # Extension des états standard pour le workflow construction
    # Note: Odoo 18 gère mieux l'extension des Selection avec selection_add
    
    @api.depends('amount_total', 'has_retention')
    def _compute_retention_amount(self):
        """Calculer le montant de la retenue de garantie (5%)"""
        for order in self:
            if order.has_retention:
                order.retention_amount = order.amount_total * 0.05
            else:
                order.retention_amount = 0.0

    # =================== ACTIONS WORKFLOW ===================

    def action_validate_quote(self):
        """Valider le devis et faire progresser le chantier"""
        self.ensure_one()
        
        # Changer l'état vers 'sale' (état standard Odoo)
        if self.state in ['draft', 'sent']:
            self.action_confirm()

        # Faire progresser le chantier si lié
        if self.chantier_id:
            self._progress_chantier_stage('devis_accepte')
            
            # Log de l'action
            self.chantier_id.message_post(
                body=_("Devis %s validé - Chantier mis à jour automatiquement") % self.name,
                message_type='notification'
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devis validé'),
                'message': _('Le devis a été confirmé et le chantier mis à jour.'),
                'type': 'success'
            }
        }

    def action_mark_no_follow(self):
        """Marquer sans suite et archiver le chantier"""
        self.ensure_one()
        
        # Annuler le devis
        if self.state not in ['cancel']:
            self.action_cancel()

        # Déplacer le chantier vers "Sans suite" si lié
        if self.chantier_id:
            self._progress_chantier_stage('sans_suite')
            self.chantier_id.write({'state': 'abandoned'})

            # Log de l'action
            self.chantier_id.message_post(
                body=_("Devis %s marqué sans suite - Chantier archivé") % self.name,
                message_type='comment'
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Devis sans suite'),
                'message': _('Le devis a été marqué sans suite et le chantier archivé.'),
                'type': 'warning'
            }
        }
    
    def action_create_milestone_invoice(self):
        """Créer une facture selon le palier de progression du chantier"""
        self.ensure_one()
        
        if not self.chantier_id:
            raise ValidationError(_("Cette commande n'est pas liée à un chantier."))
        
        progress = self.chantier_id.progress
        
        # Déterminer le palier de facturation
        milestone_data = self._determine_milestone_from_progress(progress)
        
        if not milestone_data:
            raise ValidationError(
                _("Le chantier doit avoir au moins 30%% de progression pour facturer. "
                  "Progression actuelle : %.1f%%") % progress
            )
        
        milestone = milestone_data['milestone']
        
        # Vérifier si ce palier a déjà été facturé
        if self._is_milestone_already_invoiced(milestone):
            raise ValidationError(_("Le palier %s%% a déjà été facturé.") % milestone)
        
        # Créer la facture
        invoice = self._create_milestone_invoice(milestone_data)
        
        # Mettre à jour le palier de facturation
        self.invoice_milestone = milestone
        
        # Log de l'action dans le chantier
        if self.chantier_id:
            self.chantier_id.message_post(
                body=_("Facture d'acompte %s%% créée : %s (%.2f €)") % (
                    milestone, invoice.name, invoice.amount_total
                ),
                message_type='notification'
            )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facture %s%%') % milestone,
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_retention_release_invoice(self):
        """Créer la facture de libération de retenue de garantie"""
        self.ensure_one()
        
        if not self.has_retention:
            raise ValidationError(_("Aucune retenue de garantie n'est appliquée sur cette commande."))
        
        if self.retention_amount <= 0:
            raise ValidationError(_("Le montant de la retenue de garantie est nul."))
        
        # Vérifier si la retenue a déjà été libérée
        if self._is_retention_already_released():
            raise ValidationError(_("La retenue de garantie a déjà été libérée."))
        
        # Créer la facture de libération
        invoice = self._create_retention_release_invoice()
        
        # Log dans le chantier
        if self.chantier_id:
            self.chantier_id.message_post(
                body=_("Libération de la retenue de garantie : %s (%.2f €)") % (
                    invoice.name, self.retention_amount
                ),
                message_type='notification'
            )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Libération retenue de garantie'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # =================== MÉTHODES PRIVÉES ===================

    def _progress_chantier_stage(self, stage_code):
        """Faire progresser le chantier vers une étape donnée"""
        if not self.chantier_id:
            return
            
        try:
            # Rechercher l'étape par code
            stage = self.env['construction.stage'].search([
                ('code', '=', stage_code)
            ], limit=1)
            
            if stage:
                self.chantier_id.with_context(
                    bypass_stage_validation=True
                ).write({'stage_id': stage.id})
                
        except Exception:
            # Si l'étape n'existe pas, ne pas bloquer le processus
            pass

    def _determine_milestone_from_progress(self, progress):
        """Détermine le palier de facturation selon la progression"""
        milestones = [
            {'milestone': '90', 'percentage': 0.90, 'min_progress': 90.0},
            {'milestone': '60', 'percentage': 0.60, 'min_progress': 60.0},
            {'milestone': '30', 'percentage': 0.30, 'min_progress': 30.0},
        ]
        
        for milestone_data in milestones:
            if progress >= milestone_data['min_progress']:
                return milestone_data
        
        return None

    def _is_milestone_already_invoiced(self, milestone):
        """Vérifie si un palier a déjà été facturé"""
        return bool(self.invoice_ids.filtered(
            lambda inv: inv.state != 'cancel' and 
            inv.invoice_origin and milestone in str(inv.invoice_origin)
        ))

    def _is_retention_already_released(self):
        """Vérifie si la retenue a déjà été libérée"""
        return bool(self.invoice_ids.filtered(
            lambda inv: inv.state != 'cancel' and 
            inv.invoice_origin and _('Libération retenue') in str(inv.invoice_origin)
        ))

    def _create_milestone_invoice(self, milestone_data):
        """Crée la facture pour un palier donné"""
        milestone = milestone_data['milestone']
        percentage = milestone_data['percentage']
        
        # Préparer les données de la facture
        invoice_vals = self._prepare_invoice()
        invoice_vals['invoice_origin'] = _("%s - Acompte %s%%") % (self.name, milestone)
        
        # Gestion spéciale pour le palier 90% avec retenue de garantie
        if milestone == '90':
            self.has_retention = True
            invoice_vals['narration'] = self._prepare_retention_info()
        
        # Créer la facture
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Créer les lignes de facture proportionnelles
        for line in self.order_line.filtered(lambda l: not l.display_type):
            to_invoice_qty = self._calculate_milestone_quantity(line, percentage)
            
            if to_invoice_qty > 0:
                invoice_line_vals = line._prepare_invoice_line()
                invoice_line_vals.update({
                    'move_id': invoice.id,
                    'quantity': to_invoice_qty,
                })
                self.env['account.move.line'].create(invoice_line_vals)
        
        return invoice

    def _create_retention_release_invoice(self):
        """Crée la facture de libération de retenue"""
        # Préparer les données de la facture
        invoice_vals = self._prepare_invoice()
        invoice_vals.update({
            'invoice_origin': _("%s - Libération retenue de garantie") % self.name,
            'narration': _(
                "Libération de la retenue de garantie de 5%% (%.2f €) "
                "après expiration de la période de garantie."
            ) % self.retention_amount
        })
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Créer le produit de service si nécessaire
        retention_product = self._get_or_create_retention_product()
        
        # Créer la ligne de facture pour la retenue
        line_vals = {
            'move_id': invoice.id,
            'product_id': retention_product.id,
            'name': _("Libération retenue de garantie 5%%"),
            'quantity': 1,
            'price_unit': self.retention_amount,
            'tax_ids': [(6, 0, [])],  # Pas de taxes sur la retenue
        }
        
        self.env['account.move.line'].create(line_vals)
        
        return invoice

    def _prepare_retention_info(self):
        """Prépare les informations sur la retenue de garantie"""
        return _(
            "Facture d'acompte à 90%% de l'avancement des travaux.\n"
            "Une retenue de garantie de 5%% (%.2f €) sera prélevée sur le montant total.\n"
            "Cette retenue sera libérée après la période de garantie d'un an."
        ) % self.retention_amount

    def _calculate_milestone_quantity(self, order_line, percentage):
        """Calcule la quantité à facturer pour une ligne donnée selon le palier"""
        # Quantité déjà facturée pour ce produit
        already_invoiced_qty = sum(
            self.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
            .invoice_line_ids.filtered(lambda l: l.product_id == order_line.product_id)
            .mapped('quantity')
        )
        
        # Quantité à facturer pour ce palier
        target_qty = order_line.product_uom_qty * percentage
        to_invoice_qty = target_qty - already_invoiced_qty
        
        return max(0, to_invoice_qty)

    def _get_or_create_retention_product(self):
        """Récupère ou crée le produit de service pour la retenue de garantie"""
        # Rechercher le produit existant
        retention_product = self.env['product.product'].search([
            ('default_code', '=', 'RET_GARANTIE')
        ], limit=1)
        
        if not retention_product:
            # Créer le produit de service
            category = self.env.ref('product.product_category_all', raise_if_not_found=False)
            retention_product = self.env['product.product'].create({
                'name': _('Retenue de garantie'),
                'type': 'service',
                'categ_id': category.id if category else False,
                'default_code': 'RET_GARANTIE',
                'list_price': 0.0,
                'standard_price': 0.0,
                'taxes_id': [(6, 0, [])],
                'supplier_taxes_id': [(6, 0, [])],
                'description': _('Produit de service pour la libération des retenues de garantie'),
                'sale_ok': True,
                'purchase_ok': False,
            })
        
        return retention_product

    # =================== API ET UTILITAIRES ===================

    def get_available_milestones(self):
        """Retourne les paliers de facturation disponibles selon la progression"""
        if not self.chantier_id:
            return []
        
        progress = self.chantier_id.progress
        available = []
        
        milestones = [
            ('30', 30.0, _('Premier acompte')),
            ('60', 60.0, _('Deuxième acompte')),
            ('90', 90.0, _('Troisième acompte')),
        ]
        
        for milestone, min_progress, description in milestones:
            if (progress >= min_progress and 
                not self._is_milestone_already_invoiced(milestone)):
                available.append({
                    'milestone': milestone,
                    'description': description,
                    'can_invoice': True
                })
        
        return available

    def action_open_quote_wizard(self):
        """Ouvrir l'assistant intelligent de création de devis"""
        self.ensure_one()
        
        if not self.chantier_id:
            raise ValidationError(_("Ce devis n'est pas lié à un chantier."))
        
        # Créer le wizard avec les lots du chantier
        wizard = self.env['construction.quote.wizard'].create({
            'sale_order_id': self.id,
            'chantier_id': self.chantier_id.id,
            'lot_ids': [(6, 0, self.chantier_id.lots_ids.ids)],
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assistant de création de devis - %s') % self.chantier_id.name,
            'res_model': 'construction.quote.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'sale.order',
                'active_id': self.id,
            }
        }

    @api.onchange('chantier_id')
    def _onchange_chantier_id(self):
        """Mise à jour automatique du partenaire et des lots quand le chantier change"""
        if self.chantier_id:
            if self.chantier_id.client and not self.partner_id:
                self.partner_id = self.chantier_id.client
            if self.chantier_id.lots_ids:
                self.lot_ids = self.chantier_id.lots_ids

    @api.constrains('chantier_id', 'lot_ids')
    def _check_lots_compatibility(self):
        """Vérifier que les lots sélectionnés appartiennent au chantier"""
        for record in self:
            if record.chantier_id and record.lot_ids:
                invalid_lots = record.lot_ids - record.chantier_id.lots_ids
                if invalid_lots:
                    raise ValidationError(
                        _("Les lots suivants ne sont pas liés au chantier sélectionné : %s") 
                        % ', '.join(invalid_lots.mapped('name'))
                    )


class SaleOrderLine(models.Model):
    """Extension des lignes de commande pour la construction"""
    _inherit = 'sale.order.line'

    # =================== CHAMPS CONSTRUCTION ===================

    room_location = fields.Char(
        string='Localisation',
        help="Localisation précise dans le bâtiment (ex: Salon, Cuisine, Chambre 1)"
    )
    
    floor_level = fields.Selection([
        ('basement', 'Sous-sol'),
        ('ground', 'Rez-de-chaussée'),
        ('floor_1', 'Étage 1'),
        ('floor_2', 'Étage 2'),
        ('floor_3', 'Étage 3'),
        ('floor_4', 'Étage 4'),
        ('attic', 'Combles'),
        ('other', 'Autre'),
    ], string='Niveau')
    
    construction_notes = fields.Text(
        string='Notes techniques',
        help="Notes spécifiques pour l'installation ou la mise en œuvre"
    )
    
    # Relation avec les lots de construction
    lot_id = fields.Many2one(
        'construction.lot',
        string='Lot',
        help="Lot de construction auquel appartient cette ligne"
    )
    
    # Informations sur l'avancement
    work_progress = fields.Float(
        string='Avancement (%)',
        default=0.0,
        help="Pourcentage d'avancement de cette ligne de travaux"
    )
    
    is_milestone_item = fields.Boolean(
        string='Article de jalonnement',
        default=False,
        help="Indique si cet article sert de point de jalonnement pour la facturation"
    )

    # =================== CONTRAINTES ===================

    @api.constrains('work_progress')
    def _check_work_progress(self):
        """Vérifier que l'avancement est valide"""
        for line in self:
            if not 0 <= line.work_progress <= 100:
                raise ValidationError(
                    _("L'avancement doit être compris entre 0 et 100%%. "
                      "Valeur actuelle : %.1f%%") % line.work_progress
                )

    @api.constrains('lot_id')
    def _check_lot_compatibility(self):
        """Vérifier que le lot est compatible avec le chantier de la commande"""
        for line in self:
            if (line.lot_id and line.order_id.chantier_id and 
                line.lot_id not in line.order_id.chantier_id.lots_ids):
                raise ValidationError(
                    _("Le lot '%s' ne fait pas partie du chantier '%s'") % (
                        line.lot_id.name, line.order_id.chantier_id.name
                    )
                )

    # =================== MÉTHODES ===================

    def update_work_progress(self, progress):
        """Mettre à jour l'avancement d'une ligne"""
        self.ensure_one()
        if not 0 <= progress <= 100:
            raise ValidationError(_("L'avancement doit être entre 0 et 100%%"))
        
        old_progress = self.work_progress
        self.work_progress = progress
        
        # Log du changement
        if self.order_id.chantier_id:
            self.order_id.chantier_id.message_post(
                body=_("Avancement mis à jour pour '%s' : %.1f%% → %.1f%%") % (
                    self.product_id.name, old_progress, progress
                ),
                message_type='comment'
            )
        
        return True

    def action_mark_completed(self):
        """Marquer cette ligne comme terminée"""
        self.update_work_progress(100.0)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Ligne terminée'),
                'message': _("'%s' marqué comme terminé") % self.product_id.name,
                'type': 'success'
            }
        }

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """Mise à jour automatique de la localisation selon le lot"""
        if self.lot_id and self.lot_id.default_location:
            self.room_location = self.lot_id.default_location

    # =================== COMPUTE METHODS ===================

    def _get_construction_description(self):
        """Génère une description complète pour la construction"""
        self.ensure_one()
        
        description_parts = [self.name]
        
        if self.room_location:
            description_parts.append(_("Localisation : %s") % self.room_location)
        
        if self.floor_level:
            floor_labels = dict(self._fields['floor_level'].selection)
            description_parts.append(_("Niveau : %s") % floor_labels.get(self.floor_level))
        
        if self.construction_notes:
            description_parts.append(_("Notes : %s") % self.construction_notes)
        
        return "\n".join(description_parts)

    def _prepare_invoice_line(self):
        """Surcharge pour inclure les informations de construction"""
        res = super()._prepare_invoice_line()
        
        # Ajouter les informations de construction à la description
        if any([self.room_location, self.floor_level, self.construction_notes]):
            construction_desc = self._get_construction_description()
            res['name'] = construction_desc
        
        return res
