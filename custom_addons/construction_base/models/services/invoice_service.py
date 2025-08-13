# -*- coding: utf-8 -*-
"""
Service de gestion des factures pour les chantiers de construction
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
import base64
from datetime import datetime

_logger = logging.getLogger(__name__)


class InvoiceService(models.AbstractModel):
    _name = 'construction.invoice.service'
    _description = 'Service de gestion des factures'

    def create_invoice_schedule_for_chantier(self, chantier_id, quote_id, invoice_type_id, lot_ids=None, margin_percentage=0.0):
        """
        Créer un planning de facturation pour un chantier basé sur un cycle de facturation
        
        Args:
            chantier_id: ID du chantier
            quote_id: ID du devis accepté qui servira de base pour les calculs
            invoice_type_id: ID du cycle de facturation à appliquer
            lot_ids: Liste des IDs des lots concernés (optionnel, par défaut tous les lots du chantier)
            margin_percentage: Pourcentage de marge à déduire
        
        Returns:
            Recordset des planifications de facturation créées
        """
        chantier = self.env['construction.chantier'].browse(chantier_id)
        quote = self.env['sale.order'].browse(quote_id)
        invoice_type = self.env['construction.invoice_type'].browse(invoice_type_id)
        
        # Validations
        if not chantier.exists():
            raise ValidationError(_("Le chantier spécifié n'existe pas."))
            
        if not quote.exists() or quote.state not in ['sale', 'done']:
            raise ValidationError(_("Le devis doit être confirmé (état 'sale' ou 'done')."))
            
        if quote.chantier_id != chantier:
            raise ValidationError(_("Le devis doit être lié au même chantier."))
            
        if not invoice_type.exists():
            raise ValidationError(_("Le cycle de facturation spécifié n'existe pas."))
        
        # Si pas de lots spécifiés, utiliser tous les lots du chantier
        if not lot_ids:
            lot_ids = chantier.lots_ids.ids
        
        schedules = self.env['construction.invoice.schedule']
        
        # Créer une planification pour chaque ligne du cycle
        for line in invoice_type.line_ids:
            schedule_vals = {
                'chantier_id': chantier_id,
                'invoice_type_line_id': line.id,
                'quote_id': quote_id,
                'margin_percentage': margin_percentage,
                'lot_ids': [(6, 0, lot_ids)],
                'name': line.name,
                'sequence': line.sequence,
                'trigger_percentage': line.trigger_percentage,
                'amount_percentage': line.percentage,
                'is_advance_payment': line.is_advance_payment,
                'state': 'planned',
                'notes': f"Généré automatiquement du cycle '{invoice_type.name}' pour le devis {quote.name}"
            }
            
            schedule = self.env['construction.invoice.schedule'].create(schedule_vals)
            schedules |= schedule
        
        # Message de confirmation sur le chantier
        body_msg = f"📋 Planning de facturation créé : cycle '{invoice_type.name}' basé sur le devis {quote.name} ({len(schedules)} étapes, {len(lot_ids)} lots, marge {margin_percentage}%)"
        chantier.message_post(
            body=body_msg,
            message_type='notification'
        )
        
        return schedules

    def check_and_trigger_invoices(self, chantier_id):
        """
        Vérifier et marquer les factures comme disponibles selon l'avancement du chantier
        
        Args:
            chantier_id: ID du chantier à vérifier
            
        Returns:
            dict: Résultat de la vérification avec les factures marquées comme disponibles
        """
        chantier = self.env['construction.chantier'].browse(chantier_id)
        
        if not chantier.exists():
            return {'success': False, 'message': 'Chantier introuvable'}
            
        if not chantier.invoice_schedule_ids:
            return {'success': False, 'message': 'Aucun planning de facturation configuré'}
        
        available_count = 0
        errors = []
        
        # Vérifier tous les seuils de facturation
        for schedule in chantier.invoice_schedule_ids:
            try:
                if schedule.check_progress_trigger():
                    available_count += 1
            except Exception as e:
                error_msg = f"Erreur lors de la vérification de {schedule.name}: {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg)
        
        # Message de notification
        if available_count > 0:
            chantier.message_post(
                body=f"💰 {available_count} facture(s) disponible(s) suite à l'avancement du chantier ({chantier.progress}%) - Action manuelle requise",
                message_type='notification'
            )
        
        return {
            'success': True,
            'available_count': available_count,
            'errors': errors,
            'progress': chantier.progress
        }

    def create_and_send_invoice(self, schedule_id):
        """
        Créer une facture et l'envoyer par email
        
        Args:
            schedule_id: ID de la planification de facturation
            
        Returns:
            dict: Résultat de la création et envoi
        """
        schedule = self.env['construction.invoice.schedule'].browse(schedule_id)
        
        if not schedule.exists():
            return {'success': False, 'message': 'Planification introuvable'}
            
        if schedule.state != 'ready':
            return {'success': False, 'message': 'La planification n\'est pas prête à être facturée'}
            
        if schedule.invoice_id:
            return {'success': False, 'message': 'Une facture existe déjà pour cette planification'}
        
        try:
            # Créer la facture
            invoice_result = self._create_invoice_from_schedule(schedule)
            
            if not invoice_result['success']:
                return invoice_result
            
            invoice = invoice_result['invoice']
            
            # Envoyer l'email
            email_result = self._send_invoice_email(invoice, schedule)
            
            return {
                'success': True,
                'invoice_id': invoice.id,
                'invoice_name': invoice.name,
                'amount': schedule.amount_fixed,
                'email_sent': email_result['success'],
                'email_error': email_result.get('error')
            }
            
        except Exception as e:
            error_msg = f"Erreur lors de la création de la facture: {str(e)}"
            _logger.error(error_msg)
            return {'success': False, 'message': error_msg}

    def _create_invoice_from_schedule(self, schedule):
        """
        Créer une facture à partir d'une planification
        
        Args:
            schedule: Record de construction.invoice.schedule
            
        Returns:
            dict: Résultat de la création
        """
        try:
            chantier = schedule.chantier_id
            partner = chantier.client
            
            # Préparer les lignes de facture
            invoice_line_vals = []
            
            # Ligne principale avec compte de revenus de la position fiscale/produit par défaut
            income_account = partner.property_account_receivable_id.id
            invoice_line_vals.append((0, 0, {
                'name': f"{schedule.name} - {chantier.name}",
                'quantity': 1,
                'price_unit': schedule.amount_fixed or 0.0,
            }))
            
            # Créer la facture
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_origin': chantier.name,
                'invoice_date': fields.Date.today(),
                'ref': f"Chantier {chantier.name} - {schedule.name}",
                'invoice_line_ids': invoice_line_vals,
            }
            
            invoice = self.env['account.move'].create(invoice_vals)
            
            # Poster la facture pour avoir un numéro officiel
            try:
                invoice.action_post()
            except Exception as e:
                _logger.warning(f"Impossible de poster automatiquement la facture {invoice.id}: {e}")
            
            # Marquer la planification comme facturée
            schedule.write({
                'invoice_id': invoice.id,
                'state': 'invoiced',
                'invoice_date': fields.Date.today()
            })
            
            # Message détaillé dans le chatter du chantier
            self._log_invoice_creation(chantier, schedule, invoice)
            
            return {'success': True, 'invoice': invoice}
            
        except Exception as e:
            return {'success': False, 'message': f"Erreur création facture: {str(e)}"}

    def _send_invoice_email(self, invoice, schedule):
        """
        Envoyer l'email avec la facture
        
        Args:
            invoice: Record de account.move
            schedule: Record de construction.invoice.schedule
            
        Returns:
            dict: Résultat de l'envoi
        """
        try:
            # Essayer d'envoyer avec le template existant
            template = self.env.ref('construction_base.email_template_invoice_ready')
            if template:
                template.send_mail(invoice.id, force_send=True)
                return {'success': True}
            else:
                return {'success': False, 'error': 'Template email non trouvé'}
                
        except Exception as e:
            error_msg = f"Erreur envoi email: {str(e)}"
            _logger.warning(error_msg)
            return {'success': False, 'error': error_msg}

    def _log_invoice_creation(self, chantier, schedule, invoice):
        """
        Logger la création de facture dans le chatter du chantier
        
        Args:
            chantier: Record de construction.chantier
            schedule: Record de construction.invoice.schedule
            invoice: Record de account.move
        """
        try:
            # Informations pour le message
            lot_names = ', '.join(schedule.lot_ids.mapped('name')) if schedule.lot_ids else 'N/A'
            quote_name = schedule.quote_id.name if schedule.quote_id else 'N/A'
            date_str = fields.Date.today().strftime('%d/%m/%Y')
            invoice_ref = invoice.name if invoice.name and invoice.name != '/' else f"FACT-{invoice.id}"
            
            # Message HTML simple (balises sûres pour le chatter)
            message_body = (
                f"<p><strong>🧾 Facture générée automatiquement</strong></p>"
                f"<p><strong>Référence:</strong> {invoice_ref}<br/>"
                f"<strong>Étape:</strong> {schedule.name}<br/>"
                f"<strong>Montant:</strong> {schedule.amount_fixed:,.2f} €<br/>"
                f"<strong>Client:</strong> {chantier.client.name}<br/>"
                f"<strong>Lots concernés:</strong> {lot_names}<br/>"
                f"<strong>Devis de référence:</strong> {quote_name}<br/>"
                f"<strong>Date:</strong> {date_str}</p>"
            )
            
            # Poster le message principal
            subject_text = f"💰 Facture {invoice_ref} générée"
            message = chantier.message_post(
                body=message_body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
                subject=subject_text
            )
            
            # Attacher le PDF de la facture
            self._attach_invoice_pdf(message, invoice, invoice_ref)
            
        except Exception as e:
            _logger.error(f"Erreur lors du logging de la facture: {e}")

    def _attach_invoice_pdf(self, message, invoice, invoice_ref):
        """
        Attacher le PDF de la facture au message
        
        Args:
            message: Record du message
            invoice: Record de account.move
            invoice_ref: Référence de la facture
        """
        try:
            # Générer le PDF de la facture avec le report BLG si disponible sinon fallback standard
            report_xmlid = 'construction_base.chantier_invoice_template'
            try:
                pdf_tuple = self.env['ir.actions.report']._render_qweb_pdf(report_xmlid, [invoice.id])
            except Exception:
                pdf_tuple = self.env['ir.actions.report']._render_qweb_pdf('account.report_invoice', [invoice.id])
            pdf_content = pdf_tuple[0]

            # Encodage base64 requis par ir.attachment
            pdf_b64 = base64.b64encode(pdf_content)

            # Créer la pièce jointe et lier à la facture (modèle cible cohérent)
            attachment = self.env['ir.attachment'].create({
                'name': f"{invoice_ref}.pdf",
                'type': 'binary',
                'datas': pdf_b64,
                'res_model': 'account.move',
                'res_id': invoice.id,
                'mimetype': 'application/pdf',
            })

            # Lier la pièce jointe au message déjà posté sur le chantier
            message.attachment_ids = [(6, 0, [attachment.id])]
            
        except Exception as e:
            _logger.warning(f"Impossible de générer le PDF pour la facture {invoice.id}: {e}")
            # Informer dans le même fil (chantier) que le PDF n'a pas été généré
            message.sudo().write({'body': message.body + "<br/><em>⚠️ PDF non généré automatiquement. Imprimez depuis la facture.</em>"})

    def get_invoice_schedule_summary(self, chantier_id):
        """
        Obtenir un résumé du planning de facturation d'un chantier
        
        Args:
            chantier_id: ID du chantier
            
        Returns:
            dict: Résumé du planning
        """
        chantier = self.env['construction.chantier'].browse(chantier_id)
        
        if not chantier.exists():
            return {'success': False, 'message': 'Chantier introuvable'}
        
        schedules = chantier.invoice_schedule_ids
        
        summary = {
            'success': True,
            'chantier_name': chantier.name,
            'progress': chantier.progress,
            'total_schedules': len(schedules),
            'planned_count': len(schedules.filtered(lambda s: s.state == 'planned')),
            'ready_count': len(schedules.filtered(lambda s: s.state == 'ready')),
            'invoiced_count': len(schedules.filtered(lambda s: s.state == 'invoiced')),
            'paid_count': len(schedules.filtered(lambda s: s.state == 'paid')),
            'total_amount': sum(schedules.mapped('amount_fixed')),
            'schedules': []
        }
        
        for schedule in schedules.sorted('sequence'):
            summary['schedules'].append({
                'id': schedule.id,
                'name': schedule.name,
                'state': schedule.state,
                'trigger_percentage': schedule.trigger_percentage,
                'amount_percentage': schedule.amount_percentage,
                'amount_fixed': schedule.amount_fixed,
                'is_advance_payment': schedule.is_advance_payment,
                'is_triggered': schedule.is_triggered,
                'invoice_id': schedule.invoice_id.id if schedule.invoice_id else False,
                'invoice_name': schedule.invoice_id.name if schedule.invoice_id else False,
            })
        
        return summary

    def trigger_advance_payment(self, chantier_id):
        """
        Déclencher manuellement l'acompte de signature
        
        Args:
            chantier_id: ID du chantier
            
        Returns:
            dict: Résultat de l'opération
        """
        chantier = self.env['construction.chantier'].browse(chantier_id)
        
        if not chantier.exists():
            return {'success': False, 'message': 'Chantier introuvable'}
        
        advance_payments = chantier.invoice_schedule_ids.filtered(
            lambda s: s.is_advance_payment and s.state == 'planned'
        )
        
        if not advance_payments:
            return {'success': False, 'message': 'Aucun acompte de signature en attente'}
        
        triggered_count = 0
        for payment in advance_payments:
            payment.write({
                'state': 'ready',
                'is_triggered': True
            })
            triggered_count += 1
        
        chantier.message_post(
            body=f"📝 {triggered_count} acompte(s) de signature déclenché(s) manuellement",
            message_type='notification'
        )
        
        return {
            'success': True,
            'triggered_count': triggered_count,
            'message': f'{triggered_count} acompte(s) de signature déclenché(s)'
        } 