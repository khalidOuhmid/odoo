# -*- coding: utf-8 -*-
"""
Document Validation Service

This service provides methods to check subcontractor document compliance,
track expiring documents, and generate compliance dashboard data.
"""

from odoo import models, fields, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class ValidationDocumentsService(models.AbstractModel):
    """
    Service for validating subcontractor documents and compliance.
    
    This service follows SOLID principles and provides a centralized
    location for all document validation logic.
    """
    _name = 'construction.validation.documents.service'
    _description = 'Document Validation Service'

    # Document types that require validation for subcontractors
    REQUIRED_DOCUMENTS = ['URSSAF', 'KBIS', 'insurance']

    def check_subcontractor_compliance(self, partner_id):
        """
        Check if a subcontractor has all required documents valid.
        
        Args:
            partner_id: res.partner record or ID
            
        Returns:
            dict: {
                'is_compliant': bool,
                'missing_documents': list of document names,
                'expired_documents': list of document names,
                'expiring_documents': list of document names (within 30 days),
                'rejected_documents': list of document names,
                'details': dict with detailed status per document
            }
        """
        if isinstance(partner_id, int):
            partner = self.env['res.partner'].browse(partner_id)
        else:
            partner = partner_id
            
        if not partner.exists():
            raise ValidationError(_("Partner not found"))
        
        # Skip validation for internal employees
        if partner.contact_type == 'employee':
            return {
                'is_compliant': True,
                'missing_documents': [],
                'expired_documents': [],
                'expiring_documents': [],
                'rejected_documents': [],
                'details': {}
            }
        
        missing_documents = []
        expired_documents = []
        expiring_documents = []
        rejected_documents = []
        details = {}
        
        # Check each required document
        for doc_type in self.REQUIRED_DOCUMENTS:
            status_field = f'document_{doc_type}_status'
            manual_status_field = f'document_{doc_type}_manual_status'
            expiry_field = f'document_{doc_type}_expiry'
            
            if not hasattr(partner, status_field):
                continue
                
            status = getattr(partner, status_field, 'missing')
            manual_status = getattr(partner, manual_status_field, 'to_check')
            expiry_date = getattr(partner, expiry_field, False)
            
            doc_display_name = self._get_document_display_name(doc_type)
            
            details[doc_type] = {
                'status': status,
                'manual_status': manual_status,
                'expiry_date': expiry_date,
                'display_name': doc_display_name
            }
            
            if status == 'missing':
                missing_documents.append(doc_display_name)
            elif status == 'expired':
                expired_documents.append(doc_display_name)
            elif status == 'expiring':
                expiring_documents.append(doc_display_name)
            elif manual_status == 'rejected':
                rejected_documents.append(doc_display_name)
        
        # Partner is compliant if no missing, expired, or rejected documents
        is_compliant = not (missing_documents or expired_documents or rejected_documents)
        
        return {
            'is_compliant': is_compliant,
            'missing_documents': missing_documents,
            'expired_documents': expired_documents,
            'expiring_documents': expiring_documents,
            'rejected_documents': rejected_documents,
            'details': details
        }

    def get_expiring_documents(self, days_threshold=30):
        """
        Get all subcontractors with documents expiring within the threshold.
        
        Args:
            days_threshold: Number of days to look ahead (default: 30)
            
        Returns:
            list: List of dicts with partner info and expiring documents
        """
        threshold_date = date.today() + timedelta(days=days_threshold)
        expiring_partners = []
        
        # Search for subcontractors
        subcontractors = self.env['res.partner'].search([
            ('contact_type', '=', 'sous_traitant')
        ])
        
        for partner in subcontractors:
            expiring_docs = []
            
            for doc_type in self.REQUIRED_DOCUMENTS:
                expiry_field = f'document_{doc_type}_expiry'
                status_field = f'document_{doc_type}_status'
                
                if not hasattr(partner, expiry_field):
                    continue
                    
                expiry_date = getattr(partner, expiry_field, False)
                status = getattr(partner, status_field, 'missing')
                
                if expiry_date and expiry_date <= threshold_date and expiry_date >= date.today():
                    doc_display_name = self._get_document_display_name(doc_type)
                    days_until_expiry = (expiry_date - date.today()).days
                    
                    expiring_docs.append({
                        'document_type': doc_type,
                        'document_name': doc_display_name,
                        'expiry_date': expiry_date,
                        'days_until_expiry': days_until_expiry,
                        'status': status
                    })
            
            if expiring_docs:
                expiring_partners.append({
                    'partner_id': partner.id,
                    'partner_name': partner.name,
                    'partner_email': partner.email,
                    'expiring_documents': expiring_docs
                })
        
        return expiring_partners

    def get_compliance_dashboard_data(self):
        """
        Generate comprehensive compliance dashboard data.
        
        Returns:
            dict: Dashboard data with statistics and partner lists
        """
        subcontractors = self.env['res.partner'].search([
            ('contact_type', '=', 'sous_traitant')
        ])
        
        compliant_partners = []
        non_compliant_partners = []
        expiring_soon_partners = []
        
        stats = {
            'total_subcontractors': len(subcontractors),
            'compliant_count': 0,
            'non_compliant_count': 0,
            'expiring_soon_count': 0,
            'missing_documents_count': 0,
            'expired_documents_count': 0,
            'rejected_documents_count': 0,
        }
        
        for partner in subcontractors:
            compliance = self.check_subcontractor_compliance(partner)
            
            partner_data = {
                'id': partner.id,
                'name': partner.name,
                'email': partner.email,
                'phone': partner.phone,
                'compliance': compliance
            }
            
            if compliance['is_compliant']:
                if compliance['expiring_documents']:
                    expiring_soon_partners.append(partner_data)
                    stats['expiring_soon_count'] += 1
                else:
                    compliant_partners.append(partner_data)
                    stats['compliant_count'] += 1
            else:
                non_compliant_partners.append(partner_data)
                stats['non_compliant_count'] += 1
                stats['missing_documents_count'] += len(compliance['missing_documents'])
                stats['expired_documents_count'] += len(compliance['expired_documents'])
                stats['rejected_documents_count'] += len(compliance['rejected_documents'])
        
        return {
            'stats': stats,
            'compliant_partners': compliant_partners,
            'non_compliant_partners': non_compliant_partners,
            'expiring_soon_partners': expiring_soon_partners,
        }

    def _get_document_display_name(self, doc_type):
        """
        Get the display name for a document type.
        
        Args:
            doc_type: Document type key (e.g., 'URSSAF', 'KBIS', 'insurance')
            
        Returns:
            str: Display name in French
        """
        display_names = {
            'URSSAF': 'Attestation URSSAF',
            'KBIS': 'Extrait KBIS',
            'insurance': 'Attestation d\'assurance',
            'identity_card': 'Carte d\'identité',
            'RIB': 'RIB'
        }
        return display_names.get(doc_type, doc_type.upper())

    def get_non_compliant_message(self, partner_id):
        """
        Generate a detailed error message for non-compliant subcontractors.
        
        Args:
            partner_id: res.partner record or ID
            
        Returns:
            str: Formatted error message
        """
        compliance = self.check_subcontractor_compliance(partner_id)
        
        if compliance['is_compliant']:
            return ""
        
        if isinstance(partner_id, int):
            partner = self.env['res.partner'].browse(partner_id)
        else:
            partner = partner_id
        
        message_parts = [
            _("Le sous-traitant %s n'est pas conforme :") % partner.name,
            ""
        ]
        
        if compliance['missing_documents']:
            message_parts.append(_("Documents manquants :"))
            for doc in compliance['missing_documents']:
                message_parts.append(f"  • {doc}")
            message_parts.append("")
        
        if compliance['expired_documents']:
            message_parts.append(_("Documents expirés :"))
            for doc in compliance['expired_documents']:
                message_parts.append(f"  • {doc}")
            message_parts.append("")
        
        if compliance['rejected_documents']:
            message_parts.append(_("Documents rejetés :"))
            for doc in compliance['rejected_documents']:
                message_parts.append(f"  • {doc}")
            message_parts.append("")
        
        message_parts.append(_("Veuillez mettre à jour les documents avant de créer un contrat."))
        
        return "\n".join(message_parts)
