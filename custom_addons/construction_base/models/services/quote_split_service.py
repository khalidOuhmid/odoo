# -*- coding: utf-8 -*-
"""
Purchase Split Service

This service handles the division of main quotes into purchase orders by construction lots
and their assignment to specialized subcontractors.
"""

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PurchaseSplitService(models.AbstractModel):
    """
    Service for splitting construction quotes into purchase orders by lots and assigning to subcontractors.

    This service provides functionality to:
    - Analyze main quotes and identify lot-specific content
    - Generate purchase orders for each lot
    - Assign purchase orders to appropriate subcontractors
    - Maintain relationships between main quotes and purchase orders
    """
    _name = 'purchase.split.service'
    _description = 'Purchase Order Splitting Service'

    @api.model
    def split_quote_to_purchase_by_lots(self, chantier_id, main_quote_id=None):
        """
        Split the main quote of a chantier into purchase orders by lots.

        Args:
            chantier_id (int): ID of the construction project
            main_quote_id (int, optional): Specific quote to split. If None, uses the latest confirmed quote.

        Returns:
            dict: Result with created purchase orders and assignment information
        """
        try:
            chantier = self.env['construction.chantier'].browse(chantier_id)
            if not chantier.exists():
                raise ValidationError(_("Construction project not found"))

            # Get the main quote to split
            main_quote = self._get_main_quote(chantier, main_quote_id)
            if not main_quote:
                raise ValidationError(_("No valid quote found to split"))

            # Validate prerequisites
            self._validate_split_prerequisites(chantier, main_quote)

            # Analyze quote structure and group by lots
            lot_groups = self._analyze_quote_structure(main_quote)

            if not lot_groups:
                raise ValidationError(_("No lot-specific content found in the quote"))

            # Create purchase orders for each lot
            created_purchase_orders = []
            assignment_results = []

            for lot_id, quote_data in lot_groups.items():
                lot = self.env['construction.lot'].browse(lot_id)

                # Si le lot est géré par un partenaire interne (employee), ne pas créer de bon de commande
                internal_assignees = lot.subcontractor_ids.filtered(lambda p: getattr(p, 'contact_type', False) == 'employee')
                if internal_assignees and (len(lot.subcontractor_ids) == len(internal_assignees)):
                    assignment_results.append({
                        'lot_name': lot.name,
                        'assigned': False,
                        'skipped': True,
                        'reason': 'internal_lot',
                        'message': _("Lot géré en interne: aucun bon de commande généré")
                    })
                    continue

                # Create purchase order for this lot
                purchase_order = self._create_lot_purchase_order(main_quote, lot, quote_data)
                created_purchase_orders.append(purchase_order)

                # Try to assign to appropriate subcontractor
                assignment_result = self._assign_purchase_order_to_subcontractor(chantier, purchase_order, lot)
                assignment_results.append(assignment_result)

            # Update main quote status
            self._update_main_quote_status(main_quote, created_purchase_orders)

            # Log the operation
            _logger.info(
                "Quote to purchase splitting completed for chantier %s: %d purchase orders created",
                chantier.name, len(created_purchase_orders)
            )

            return {
                'success': True,
                'main_quote_id': main_quote.id,
                'created_purchase_orders': created_purchase_orders.ids,
                'assignment_results': assignment_results,
                'total_purchase_orders': len(created_purchase_orders),
                'message': _("%d purchase orders created successfully") % len(created_purchase_orders)
            }

        except Exception as e:
            _logger.error("Purchase order splitting failed for chantier %s: %s", chantier_id, str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': _("Purchase order splitting failed: %s") % str(e)
            }

    def _get_main_quote(self, chantier, main_quote_id=None):
        """Get the main quote to split."""
        if main_quote_id:
            quote = self.env['sale.order'].browse(main_quote_id)
            if quote.exists() and quote.chantier_id == chantier:
                return quote

        # Find the latest confirmed quote for this chantier
        quotes = self.env['sale.order'].search([
            ('chantier_id', '=', chantier.id),
            ('state', 'in', ['sale', 'done']),
        ], order='date_order desc', limit=1)

        return quotes[0] if quotes else None

    def _validate_split_prerequisites(self, chantier, main_quote):
        """Validate that all prerequisites for splitting are met."""
        # Check chantier stage
        if not chantier.stage_id or chantier.stage_id.code != 'FD':
            raise ValidationError(_(
                "Purchase order splitting is only available at the 'Finalisation dossier' stage. "
                "Current stage: %s"
            ) % (chantier.stage_id.name if chantier.stage_id else 'None'))

        # Check quote has lots
        if not main_quote.lot_ids:
            raise ValidationError(_(
                "The quote must have lots assigned before splitting. "
                "Please assign lots to the quote first."
            ))

        # Check quote has order lines
        product_lines = main_quote.order_line.filtered(lambda l: not l.display_type)
        if not product_lines:
            raise ValidationError(_(
                "The quote must have product lines to split."
            ))

        # Check chantier has subcontractors assigned
        if not chantier.subcontractors:
            raise ValidationError(_(
                "Please assign subcontractors to the project before splitting quotes."
            ))

    def _analyze_quote_structure(self, main_quote):
        """
        Analyze quote structure and group content by lots.

        Returns:
            dict: {lot_id: {'lines': [...], 'total': float, 'sections': [...]}}
        """
        lot_groups = {}
        current_lot = None

        for line in main_quote.order_line.sorted('sequence'):

            if line.display_type == 'line_section':
                # Try to identify lot from section name
                current_lot = self._identify_lot_from_section(line.name, main_quote.lot_ids)

                if current_lot and current_lot.id not in lot_groups:
                    lot_groups[current_lot.id] = {
                        'lines': [],
                        'sections': [],
                        'total': 0.0,
                        'lot': current_lot
                    }

                if current_lot:
                    lot_groups[current_lot.id]['sections'].append(line)

            elif line.display_type == 'line_note':
                # Add notes to current lot if any
                if current_lot and current_lot.id in lot_groups:
                    lot_groups[current_lot.id]['lines'].append(line)

            else:
                # Product line
                assigned_lot = self._determine_line_lot(line, current_lot, main_quote.lot_ids)

                if assigned_lot:
                    if assigned_lot.id not in lot_groups:
                        lot_groups[assigned_lot.id] = {
                            'lines': [],
                            'sections': [],
                            'total': 0.0,
                            'lot': assigned_lot
                        }

                    lot_groups[assigned_lot.id]['lines'].append(line)
                    lot_groups[assigned_lot.id]['total'] += line.price_subtotal

        return lot_groups

    def _identify_lot_from_section(self, section_name, available_lots):
        """Try to identify a lot from section name."""
        if not section_name:
            return None

        # Remove common prefixes and clean the name
        clean_name = section_name.replace('📋', '').strip()

        # Look for exact match first
        for lot in available_lots:
            if lot.name.lower() in clean_name.lower():
                return lot

        # Look for code match
        for lot in available_lots:
            if lot.code and lot.code.lower() in clean_name.lower():
                return lot

        return None

    def _determine_line_lot(self, line, current_lot, available_lots):
        """Determine which lot a line belongs to."""
        # If line has explicit lot assignment (if such field exists)
        if hasattr(line, 'lot_id') and line.lot_id:
            return line.lot_id

        # If we're in a lot section context
        if current_lot:
            return current_lot

        # Try to determine from product category or name
        return self._guess_lot_from_product(line.product_id, available_lots)

    def _guess_lot_from_product(self, product, available_lots):
        """Try to guess lot from product characteristics."""
        if not product:
            return None

        # Simple keyword matching (can be enhanced)
        product_text = (product.name + ' ' + (product.categ_id.name or '')).lower()

        lot_keywords = {
            'général': ['général', 'general', 'divers'],
            'maçonnerie': ['maçon', 'béton', 'ciment', 'parpaing', 'brique'],
            'électricité': ['électr', 'cable', 'prise', 'interrupteur', 'tableau'],
            'plomberie': ['plomb', 'tuyau', 'robinet', 'sanitaire', 'évacuation'],
            'peinture': ['peinture', 'pinceau', 'rouleau', 'enduit'],
        }

        for lot in available_lots:
            lot_name_lower = lot.name.lower()
            if lot_name_lower in lot_keywords:
                keywords = lot_keywords[lot_name_lower]
                if any(keyword in product_text for keyword in keywords):
                    return lot

        # If no specific match, return first available lot (général if exists)
        general_lot = available_lots.filtered(lambda l: 'général' in l.name.lower())
        return general_lot[0] if general_lot else available_lots[0]

    def _create_lot_purchase_order(self, main_quote, lot, quote_data):
        """Create a purchase order for a specific lot."""
        # Prepare purchase order values
        purchase_vals = {
            'partner_id': None,  # Will be set when assigned to subcontractor
            'chantier_id': main_quote.chantier_id.id,
            'origin': f"{main_quote.name} - {lot.name}",
            'state': 'draft',
            'date_order': fields.Datetime.now(),
            'company_id': main_quote.company_id.id,
            'currency_id': main_quote.currency_id.id,
            'notes': f"Bon de commande généré automatiquement pour le lot : {lot.name}",
        }

        # Add lot_ids field if it exists in purchase.order
        if hasattr(self.env['purchase.order'], 'lot_ids'):
            purchase_vals['lot_ids'] = [(6, 0, [lot.id])]

        # Create the purchase order
        purchase_order = self.env['purchase.order'].create(purchase_vals)

        # Add lot section
        self._create_purchase_line(purchase_order, {
            'display_type': 'line_section',
            'name': f"🛒 {lot.name}",
            'sequence': 10,
        })

        # Add all sections for this lot
        sequence = 20
        for section in quote_data.get('sections', []):
            if section.name != f"🛒 {lot.name}":  # Avoid duplicate main section
                self._create_purchase_line(purchase_order, {
                    'display_type': 'line_section',
                    'name': section.name,
                    'sequence': sequence,
                })
                sequence += 10

        # Add all product lines for this lot
        for line in quote_data.get('lines', []):
            line_vals = self._prepare_purchase_line(line, sequence)
            self._create_purchase_line(purchase_order, line_vals)
            sequence += 10

        return purchase_order

    def _prepare_purchase_line(self, original_line, sequence):
        """Prepare values for a purchase order line from the original sale line."""
        vals = {
            'sequence': sequence,
            'display_type': original_line.display_type,
            'name': original_line.name,
        }

        if not original_line.display_type:
            # Product line - adapt fields for purchase.order.line
            vals.update({
                'product_id': original_line.product_id.id,
                'product_qty': original_line.product_uom_qty,  # purchase uses product_qty
                'product_uom': original_line.product_uom.id,
                'price_unit': original_line.price_unit,
                'taxes_id': [(6, 0, original_line.tax_id.ids)],  # purchase uses taxes_id
                # Note: discount doesn't exist in purchase.order.line
            })

            # Copy construction-specific fields if they exist
            construction_fields = ['room_location', 'floor_level', 'construction_notes']
            for field in construction_fields:
                if hasattr(original_line, field):
                    value = getattr(original_line, field)
                    if value:
                        vals[field] = value

        return vals

    def _create_purchase_line(self, purchase_order, vals):
        """Create a purchase order line with proper defaults."""
        vals['order_id'] = purchase_order.id
        return self.env['purchase.order.line'].create(vals)

    def _assign_purchase_order_to_subcontractor(self, chantier, purchase_order, lot):
        """Assign purchase order to appropriate subcontractor with improved logic."""

        # 0. Exclure les contacts internes de toute assignation de fournisseur
        # 1. Chercher les sous-traitants spécialisés dans ce lot (via speciality_ids)
        specialized_subcontractors = chantier.subcontractor_ids.filtered(
            lambda s: (getattr(s, 'contact_type', False) != 'employee') and (lot in getattr(s, 'speciality_ids', self.env['construction.lot']) or lot in getattr(s, 'lots', self.env['construction.lot']))
        ).filtered(lambda s: s.supplier_rank > 0)  # S'assurer que c'est un fournisseur

        # 2. Si aucun spécialiste trouvé dans les sous-traitants du chantier,
        #    chercher dans tous les sous-traitants disponibles
        if not specialized_subcontractors:
            all_specialists = self.env['res.partner'].search([
                ('is_subcontractor', '=', True),
                ('supplier_rank', '>', 0),  # Doit être fournisseur
                ('speciality_ids', 'in', lot.id),
                ('contact_type', '!=', 'employee')
            ])

            # Proposer d'ajouter ces spécialistes au chantier
            return {
                'purchase_order_id': purchase_order.id,
                'lot_name': lot.name,
                'assigned': False,
                'reason': 'no_specialist_in_chantier',
                'suggested_subcontractors': all_specialists.ids,
                'suggestion_message': f"Aucun spécialiste en '{lot.name}' assigné au chantier. "
                                      f"{len(all_specialists)} spécialiste(s) disponible(s) dans la base."
            }

        # 3. Logique de sélection intelligente du sous-traitant
        selected_subcontractor = self._select_best_subcontractor(
            specialized_subcontractors, lot, chantier
        )

        # 4. Assigner le bon de commande
        purchase_order.write({
            'partner_id': selected_subcontractor.id,
            'notes': f"Bon de commande automatiquement assigné à {selected_subcontractor.name} "
                     f"(spécialiste en {lot.name})"
        })

        # 5. Log de l'assignation sur le chantier
        chantier.message_post(
            body=f"🛒 Bon de commande {purchase_order.name} assigné à {selected_subcontractor.name} "
                 f"pour le lot '{lot.name}'",
            message_type='notification'
        )

        return {
            'purchase_order_id': purchase_order.id,
            'lot_name': lot.name,
            'assigned': True,
            'subcontractor_id': selected_subcontractor.id,
            'subcontractor_name': selected_subcontractor.name,
            'assignment_reason': self._get_assignment_reason(selected_subcontractor, specialized_subcontractors)
        }

    def _select_best_subcontractor(self, specialized_subcontractors, lot, chantier):
        """Sélectionne le meilleur sous-traitant selon plusieurs critères."""

        if len(specialized_subcontractors) == 1:
            return specialized_subcontractors[0]

        # Critères de sélection (du plus important au moins important) :

        # 1. Sous-traitant avec le moins de bons de commande déjà assignés sur ce chantier
        subcontractor_workload = {}
        existing_orders = self.env['purchase.order'].search([
            ('chantier_id', '=', chantier.id),
            ('partner_id', 'in', specialized_subcontractors.ids)
        ])

        for sub in specialized_subcontractors:
            subcontractor_workload[sub.id] = len(existing_orders.filtered(
                lambda po: po.partner_id.id == sub.id
            ))

        # 2. Préférer celui avec le moins de charge de travail
        min_workload = min(subcontractor_workload.values()) if subcontractor_workload else 0
        best_candidates = specialized_subcontractors.filtered(
            lambda s: subcontractor_workload.get(s.id, 0) == min_workload
        )

        # 3. En cas d'égalité, prendre celui avec le plus de spécialités
        #    (polyvalence peut être un avantage)
        if len(best_candidates) > 1:
            best_candidates = best_candidates.sorted(
                lambda s: len(s.speciality_ids), reverse=True
            )

        # 4. En dernier recours, ordre alphabétique pour la reproductibilité
        return best_candidates.sorted('name')[0]

    def _get_assignment_reason(self, selected_subcontractor, all_candidates):
        """Retourne la raison de l'assignation pour traçabilité."""
        if len(all_candidates) == 1:
            return "Seul spécialiste disponible"

        # Compter les bons de commande existants
        existing_count = self.env['purchase.order'].search_count([
            ('partner_id', '=', selected_subcontractor.id)
        ])

        if existing_count == 0:
            return "Répartition équitable - aucun bon de commande assigné"
        else:
            return f"Répartition équitable - {existing_count} bon(s) de commande déjà assigné(s)"

    def _update_main_quote_status(self, main_quote, purchase_orders):
        """Update main quote to link it with purchase orders."""
        # Add a note to the main quote
        note = _("This quote has been split into %d purchase orders:\n") % len(purchase_orders)
        for purchase_order in purchase_orders:
            partner_name = purchase_order.partner_id.name if purchase_order.partner_id else _("Unassigned")
            note += f"- {purchase_order.name} ({partner_name})\n"

        if main_quote.note:
            main_quote.note += f"\n\n{note}"
        else:
            main_quote.note = note

    @api.model
    def get_purchase_orders_for_chantier(self, chantier_id):
        """Get all purchase orders for a chantier."""
        return self.env['purchase.order'].search([
            ('chantier_id', '=', chantier_id),
        ])

    @api.model
    def can_split_quote_to_purchase(self, chantier_id):
        """Check if quote to purchase splitting is available for a chantier."""
        chantier = self.env['construction.chantier'].browse(chantier_id)

        # Check stage
        if not chantier.stage_id or chantier.stage_id.code != 'FD':
            return False

        # Check has confirmed quotes
        quotes = self.env['sale.order'].search([
            ('chantier_id', '=', chantier_id),
            ('state', 'in', ['sale', 'done']),
        ])

        return bool(quotes)

    @api.model
    def quick_access_purchase_order(self, purchase_order_id):
        """Quick access action for purchase order editing."""
        purchase_order = self.env['purchase.order'].browse(purchase_order_id)
        if not purchase_order.exists():
            raise ValidationError(_("Purchase order not found"))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order: %s') % purchase_order.name,
            'res_model': 'purchase.order',
            'res_id': purchase_order_id,
            'view_mode': 'form',
            'target': 'new',  # Open in popup for quick editing
            'context': {
                'default_chantier_id': purchase_order.chantier_id.id,
                'form_view_initial_mode': 'edit',
            }
        }
