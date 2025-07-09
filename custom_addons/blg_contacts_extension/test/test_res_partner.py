"""
Tests unitaires pour le module Partner Document Management.

Ce module contient des tests pour toutes les fonctionnalités principales du système
de gestion de documents des partenaires, notamment:
- Calcul et validation des statuts de documents
- Contraintes sur les types de documents et les permissions
- Actions sur les documents (validation, rejet, prévisualisation)
- Gestion des notifications d'expiration
- Archivage de documents
- Filtrage des sous-traitants

Auteur: BLG IT Team
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, AccessError
from datetime import date, timedelta, datetime
from unittest.mock import patch, MagicMock
from dateutil.relativedelta import relativedelta
import base64


@tagged('post_install', '-at_install')
class TestResPartner(TransactionCase):
    """Tests pour les fonctionnalités de gestion de documents des partenaires."""

    def setUp(self):
        """Configuration des données de test."""
        super(TestResPartner, self).setUp()
        
        # Créer des utilisateurs avec différents niveaux d'accès
        self.user_admin = self.env.ref('base.user_admin')
        
        # Créer un groupe de test pour conductrice_travaux
        self.group_conductrice = self.env['res.groups'].create({
            'name': 'Conductrice Travaux',
            'implied_ids': [(4, self.env.ref('base.group_user').id)],
        })
        self.env['ir.model.data'].create({
            'name': 'group_conductrice_travaux',
            'module': 'blg_contacts_extension',
            'model': 'res.groups',
            'res_id': self.group_conductrice.id,
        })
        
        # Créer un utilisateur standard
        self.user_standard = self.env['res.users'].create({
            'name': 'Standard User',
            'login': 'standard_user',
            'email': 'standard@test.com',
            'groups_id': [(4, self.env.ref('base.group_user').id)],
        })
        
        # Créer un utilisateur conductrice
        self.user_conductrice = self.env['res.users'].create({
            'name': 'Conductrice',
            'login': 'conductrice',
            'email': 'conductrice@test.com',
            'groups_id': [(4, self.group_conductrice.id)],
        })
        
        # Créer un lot (corps de métier)
        self.lot = self.env['blg_contacts_extension.lot'].create({
            'name': 'Test Lot',
            'code': 'TL',
        })
        
        # Créer un partenaire de test (sous-traitant)
        self.partner = self.env['res.partner'].create({
            'name': 'Test Subcontractor',
            'email': 'test@example.com',
            'contact_type': 'sous_traitant',
            'lots': [(4, self.lot.id)],
        })
        
        # Créer un partenaire de test qui n'est pas sous-traitant
        self.non_subcontractor = self.env['res.partner'].create({
            'name': 'Regular Partner',
            'email': 'regular@example.com',
            'contact_type': 'customer',
        })
        
        # Préparer un fichier PDF de test
        self.sample_pdf_data = base64.b64encode(b'%PDF-1.5\nTest PDF content\n%%EOF')
        
        # Date actuelle pour les tests
        self.today = date.today()
        
        # Définir les dates pour les tests d'expiration
        self.expired_date = self.today - timedelta(days=1)
        self.expiring_soon_date = self.today + timedelta(days=15)  # dans les 30 jours
        self.valid_date = self.today + timedelta(days=60)  # plus de 30 jours

    def _upload_test_document(self, partner, doc_type, expiry_date=None, manual_status='to_check'):
        """
        Helper pour uploader un document de test.
        
        Args:
            partner: Partenaire pour lequel uploader le document
            doc_type: Type de document (identity_card, URSSAF, KBIS, insurance, RIB)
            expiry_date: Date d'expiration du document
            manual_status: Statut manuel (to_check, valid, rejected)
        """
        values = {
            f'document_{doc_type}': self.sample_pdf_data,
            f'document_{doc_type}_filename': f'test_{doc_type}.pdf',
            f'document_{doc_type}_manual_status': manual_status
        }
        
        # Ajouter la date d'expiration si applicable et si le type de document a une expiration
        if expiry_date and doc_type != 'RIB':
            values[f'document_{doc_type}_expiry'] = expiry_date
            
        partner.write(values)

    def test_01_document_status_computation_missing(self):
        """Test le calcul du statut 'missing' quand aucun document n'est présent."""
        self.assertEqual(self.partner.document_identity_card_status, 'missing')
        self.assertEqual(self.partner.document_URSSAF_status, 'missing')
        self.assertEqual(self.partner.document_KBIS_status, 'missing')
        self.assertEqual(self.partner.document_insurance_status, 'missing')
        self.assertEqual(self.partner.document_RIB_status, 'missing')
        self.assertFalse(self.partner.has_expired_documents)
        self.assertFalse(self.partner.has_expiring_documents)

    def test_02_document_status_computation_valid(self):
        """Test le calcul du statut 'valid' après upload d'un document valide."""
        # Upload un document avec une date d'expiration valide (> 30 jours)
        self._upload_test_document(self.partner, 'identity_card', self.valid_date, 'valid')
        
        self.assertEqual(self.partner.document_identity_card_status, 'valid')
        self.assertFalse(self.partner.has_expired_documents)
        self.assertFalse(self.partner.has_expiring_documents)

    def test_03_document_status_computation_expiring(self):
        """Test le calcul du statut 'expiring' pour un document qui va bientôt expirer."""
        # Upload un document qui expire bientôt (< 30 jours)
        self._upload_test_document(self.partner, 'identity_card', self.expiring_soon_date, 'valid')
        
        self.assertEqual(self.partner.document_identity_card_status, 'expiring')
        self.assertFalse(self.partner.has_expired_documents)
        self.assertTrue(self.partner.has_expiring_documents)

    def test_04_document_status_computation_expired(self):
        """Test le calcul du statut 'expired' pour un document expiré."""
        # Upload un document avec une date d'expiration dépassée
        self._upload_test_document(self.partner, 'identity_card', self.expired_date, 'valid')
        
        self.assertEqual(self.partner.document_identity_card_status, 'expired')
        self.assertTrue(self.partner.has_expired_documents)
        self.assertFalse(self.partner.has_expiring_documents)

    def test_05_document_status_computation_to_check(self):
        """Test le calcul du statut 'to_check' pour un nouveau document uploadé."""
        # Upload un document qui est en attente de vérification
        self._upload_test_document(self.partner, 'identity_card', self.valid_date)
        
        self.assertEqual(self.partner.document_identity_card_status, 'to_check')
        self.assertFalse(self.partner.has_expired_documents)
        self.assertFalse(self.partner.has_expiring_documents)

    def test_06_document_status_computation_rejected(self):
        """Test le calcul du statut 'rejected' pour un document rejeté."""
        # Upload un document puis le marquer comme rejeté
        self._upload_test_document(self.partner, 'identity_card', self.valid_date, 'rejected')
        
        self.assertEqual(self.partner.document_identity_card_status, 'rejected')
        self.assertFalse(self.partner.has_expired_documents)
        self.assertFalse(self.partner.has_expiring_documents)

    def test_07_document_constraints_file_type(self):
        """Test la contrainte sur le type de fichier (PDF uniquement)."""
        # Essayer d'uploader un document non-PDF
        with self.assertRaises(ValidationError):
            self.partner.write({
                'document_identity_card': base64.b64encode(b'Not a PDF'),
                'document_identity_card_filename': 'test.txt'
            })

    def test_08_document_constraints_sous_traitant_only(self):
        """Test la contrainte que les documents ne peuvent être uploadés que pour les sous-traitants."""
        # Essayer d'uploader un document pour un non-sous-traitant
        with self.assertRaises(ValidationError):
            self.non_subcontractor.write({
                'document_identity_card': self.sample_pdf_data,
                'document_identity_card_filename': 'test_identity_card.pdf'
            })

    def test_09_document_access_rights(self):
        """Test les droits d'accès pour les documents."""
        # Utilisateur standard ne devrait pas avoir accès
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.partner.with_user(self.user_standard).preview_document()
            
        # Utilisateur conductrice devrait avoir accès
        self._upload_test_document(self.partner, 'identity_card', self.valid_date)
        self.env.context = dict(self.env.context, doc_type='identity_card')
        result = self.partner.with_user(self.user_conductrice).preview_document()
        self.assertEqual(result['type'], 'ir.actions.act_url')

    def test_10_validate_document(self):
        """Test la validation d'un document."""
        self._upload_test_document(self.partner, 'identity_card', self.valid_date)
        
        # Valider le document
        self.env.context = dict(self.env.context, doc_type='identity_card')
        result = self.partner.with_user(self.user_admin).validate_document()
        
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'success')
        
        # Vérifier que le statut est maintenant 'valid'
        self.assertEqual(self.partner.document_identity_card_manual_status, 'valid')

    def test_11_reset_document_validation(self):
        """Test la réinitialisation d'un document validé à 'to_check'."""
        # D'abord valider un document
        self._upload_test_document(self.partner, 'identity_card', self.valid_date, 'valid')
        
        # Réinitialiser à "à vérifier"
        self.env.context = dict(self.env.context, doc_type='identity_card', reset=True)
        result = self.partner.with_user(self.user_admin).validate_document()
        
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['params']['type'], 'info')
        
        # Vérifier que le statut est maintenant 'to_check'
        self.assertEqual(self.partner.document_identity_card_manual_status, 'to_check')

    def test_12_reject_document(self):
        """Test le rejet d'un document."""
        self._upload_test_document(self.partner, 'identity_card', self.valid_date)
        
        # Rejeter le document
        self.env.context = dict(self.env.context, doc_type='identity_card', 
                               rejection_reason='Test rejection reason')
        
        # Mock l'envoi d'email pour éviter les dépendances externes
        with patch('odoo.addons.blg_contacts_extension.models.document_email_utils.send_document_notification',
                  return_value=True):
            result = self.partner.with_user(self.user_admin).reject_document()
        
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'warning')
        
        # Vérifier que le statut est maintenant 'rejected'
        self.assertEqual(self.partner.document_identity_card_manual_status, 'rejected')

    def test_13_upload_token_generation(self):
        """Test la génération d'un token d'upload sécurisé."""
        with patch('odoo.addons.blg_contacts_extension.models.res_partner.base64.b64encode',
                  return_value=b'test_token'):
            with patch('odoo.addons.blg_contacts_extension.models.res_partner.os.urandom',
                      return_value=b'random_bytes'):
                
                # Configurer le paramètre système web.base.url
                self.env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://test.example.com')
                
                # Générer le token
                result = self.partner._generate_upload_token_details()
                
                # Vérifier que le token a été généré et sauvegardé
                self.assertTrue(self.partner.upload_token)
                self.assertTrue(self.partner.token_expiration)
                self.assertTrue(result.startswith('http://test.example.com/documents/upload/'))

    def test_14_generate_and_send_rejection_email(self):
        """Test l'envoi d'un email de rejet de document."""
        # Mock l'envoi d'email
        with patch('odoo.addons.blg_contacts_extension.models.document_email_utils.send_document_notification',
                  return_value=True) as mock_send:
            self.partner._generate_and_send_rejection_email('Carte d\'identité', 'Document illisible')
            
            # Vérifier que la méthode d'envoi d'email a été appelée avec les bons paramètres
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertEqual(args[0], self.partner)
            self.assertEqual(args[1], 'rejection')
            self.assertEqual(kwargs['doc_name'], 'Carte d\'identité')
            self.assertEqual(kwargs['rejection_reason'], 'Document illisible')

    def test_15_send_expiry_email(self):
        """Test l'envoi d'un email de notification d'expiration."""
        # Configuration pour le test
        doc_config = {
            'name': 'Carte d\'identité',
            'last_notif_field': 'last_notif_expiry_identity_card'
        }
        expiry_date = self.today + timedelta(days=10)
        
        # Mock l'envoi d'email
        with patch('odoo.addons.blg_contacts_extension.models.document_email_utils.send_document_notification',
                  return_value=True) as mock_send:
            self.partner._send_expiry_email(doc_config, expiry_date, "sur le point d'expirer", False)
            
            # Vérifier que la méthode d'envoi d'email a été appelée avec les bons paramètres
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertEqual(args[0], self.partner)
            self.assertEqual(args[1], 'expiry')
            self.assertEqual(kwargs['doc_config'], doc_config)
            self.assertEqual(kwargs['expiry_date'], expiry_date)
            self.assertEqual(kwargs['status'], "sur le point d'expirer")
            self.assertEqual(kwargs['is_expired'], False)

    def test_16_action_send_missing_documents_email(self):
        """Test l'action d'envoi d'email pour les documents manquants."""
        # Configuration pour avoir des documents manquants
        with patch('odoo.addons.blg_contacts_extension.models.document_email_utils.send_document_notification',
                  return_value=True) as mock_send:
            result = self.partner.action_send_missing_documents_email()
            
            # Vérifier que la notification est correcte
            self.assertEqual(result['type'], 'ir.actions.client')
            self.assertEqual(result['tag'], 'display_notification')
            self.assertEqual(result['params']['type'], 'success')
            
            # Vérifier que l'email a été envoyé
            mock_send.assert_called_once()

    def test_17_action_send_missing_documents_email_no_email(self):
        """Test l'action d'envoi d'email pour partenaire sans email."""
        # Partenaire sans email
        self.partner.email = False
        
        result = self.partner.action_send_missing_documents_email()
        
        # Vérifier que la notification d'erreur est correcte
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'danger')

    def test_18_action_send_rib_request_email(self):
        """Test l'action d'envoi d'email pour demander un RIB."""
        with patch('odoo.addons.blg_contacts_extension.models.document_email_utils.send_document_notification',
                  return_value=True) as mock_send:
            result = self.partner.action_send_rib_request_email()
            
            # Vérifier que la notification est correcte
            self.assertEqual(result['type'], 'ir.actions.client')
            self.assertEqual(result['tag'], 'display_notification')
            self.assertEqual(result['params']['type'], 'success')
            
            # Vérifier que l'email a été envoyé avec le contexte RIB
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            self.assertEqual(args[0], self.partner)
            self.assertEqual(args[1], 'rib_request')

    def test_19_check_document_expiry(self):
        """Test la vérification d'expiration des documents."""
        # Créer un document qui expire bientôt
        self._upload_test_document(self.partner, 'identity_card', self.expiring_soon_date, 'valid')
        
        # Simuler l'exécution de la tâche cron
        with patch('odoo.addons.blg_contacts_extension.models.res_partner.ResPartner._send_expiry_email') as mock_send:
            self.partner.check_document_expiry()
            
            # Vérifier que la méthode d'envoi d'email a été appelée
            mock_send.assert_called()

    def test_20_archive_document(self):
        """Test l'archivage d'un document lorsqu'un nouveau est uploadé."""
        # D'abord uploader un document
        self._upload_test_document(self.partner, 'identity_card', self.valid_date)
        
        # Capturer l'ID du document archive avant le changement
        doc_archives_before = self.env['document.archive'].search_count([
            ('partner_id', '=', self.partner.id)
        ])
        
        # Uploader un nouveau document (devrait archiver l'ancien)
        new_pdf_data = base64.b64encode(b'%PDF-1.5\nNew PDF content\n%%EOF')
        self.partner.write({
            'document_identity_card': new_pdf_data,
            'document_identity_card_filename': 'new_identity_card.pdf'
        })
        
        # Vérifier qu'un document a été archivé
        doc_archives_after = self.env['document.archive'].search_count([
            ('partner_id', '=', self.partner.id)
        ])
        
        self.assertEqual(doc_archives_after, doc_archives_before + 1)

    def test_21_view_archive_document(self):
        """Test la visualisation d'un document archivé."""
        # Créer un document archivé de test
        archive = self.env['document.archive'].create({
            'name': 'Test Archive.pdf',
            'document': self.sample_pdf_data,
            'document_type': 'identity_card',
            'partner_id': self.partner.id,
        })
        
        # Configurer le contexte pour simuler l'action depuis la vue
        self.env.context = dict(self.env.context, active_id=archive.id)
        
        # Tester la méthode d'affichage
        result = self.partner.action_view_document()
        
        # Vérifier que l'URL est générée correctement
        self.assertEqual(result['type'], 'ir.actions.act_url')
        self.assertTrue('/web/content?model=document.archive&field=document&id=' in result['url'])

    def test_22_get_all_subcontractors(self):
        """Test la récupération de tous les sous-traitants."""
        # Créer quelques sous-traitants supplémentaires
        self.env['res.partner'].create({
            'name': 'Subcontractor 2',
            'contact_type': 'sous_traitant',
        })
        self.env['res.partner'].create({
            'name': 'Subcontractor 3',
            'contact_type': 'sous_traitant',
        })
        
        # Récupérer tous les sous-traitants
        subcontractors = self.env['res.partner'].get_all_subcontractors()
        
        # Vérifier qu'il y a au moins 3 sous-traitants (incluant celui créé dans setUp)
        self.assertGreaterEqual(len(subcontractors), 3)

    def test_23_get_subcontractors_by_document_status(self):
        """Test le filtrage des sous-traitants par statut de document."""
        # Créer un sous-traitant avec un document expiré
        expired_partner = self.env['res.partner'].create({
            'name': 'Expired Doc Partner',
            'contact_type': 'sous_traitant',
        })
        self._upload_test_document(expired_partner, 'identity_card', self.expired_date, 'valid')
        
        # Récupérer les sous-traitants avec documents expirés
        expired_subcontractors = self.env['res.partner'].get_subcontractors_by_document_status('expired')
        
        # Vérifier que notre sous-traitant avec document expiré est dans la liste
        self.assertIn(expired_partner, expired_subcontractors)

    def test_24_get_subcontractors_by_lot(self):
        """Test le filtrage des sous-traitants par lot."""
        # Créer un autre lot
        other_lot = self.env['blg_contacts_extension.lot'].create({
            'name': 'Other Lot',
            'code': 'OL',
        })
        
        # Créer un sous-traitant associé au nouveau lot
        other_partner = self.env['res.partner'].create({
            'name': 'Other Lot Partner',
            'contact_type': 'sous_traitant',
            'lots': [(4, other_lot.id)],
        })
        
        # Récupérer les sous-traitants du lot initial
        lot_subcontractors = self.env['res.partner'].get_subcontractors_by_lot(self.lot.id)
        
        # Vérifier que notre sous-traitant initial est dans la liste mais pas le nouveau
        self.assertIn(self.partner, lot_subcontractors)
        self.assertNotIn(other_partner, lot_subcontractors)

    def test_25_filter_subcontractors(self):
        """Test le filtrage combiné des sous-traitants."""
        # Créer un autre lot
        other_lot = self.env['blg_contacts_extension.lot'].create({
            'name': 'Filter Test Lot',
            'code': 'FTL',
        })
        
        # Créer un sous-traitant avec document expiré dans le lot spécifique
        test_partner = self.env['res.partner'].create({
            'name': 'Filter Test Partner',
            'contact_type': 'sous_traitant',
            'lots': [(4, other_lot.id)],
        })
        self._upload_test_document(test_partner, 'identity_card', self.expired_date, 'valid')
        
        # Filtrer par lot ET statut expiré
        filtered = self.env['res.partner'].filter_subcontractors(
            status='expired', 
            lot_id=other_lot.id
        )
        
        # Vérifier que notre partenaire de test est dans les résultats
        self.assertIn(test_partner, filtered)
        
        # Filtrer par type de document spécifique
        filtered_by_doc = self.env['res.partner'].filter_subcontractors(
            status='expired', 
            document_type='identity_card'
        )
        
        # Vérifier que notre partenaire de test est dans les résultats
        self.assertIn(test_partner, filtered_by_doc)

    def test_26_auto_expiry_dates(self):
        """Test la définition automatique des dates d'expiration pour certains documents."""
        # Uploader un document URSSAF sans date d'expiration (devrait être auto-définie)
        self.partner.write({
            'document_URSSAF': self.sample_pdf_data,
            'document_URSSAF_filename': 'test_urssaf.pdf',
        })
        
        # Vérifier que la date d'expiration a bien été définie automatiquement
        self.assertIsNotNone(self.partner.document_URSSAF_expiry)
        
        # Pour URSSAF, la date d'expiration est aujourd'hui + 6 mois
        expected_date = fields.Date.today() + relativedelta(months=6)
        self.assertEqual(self.partner.document_URSSAF_expiry, expected_date)

    def test_27_filename_standardization(self):
        """Test la standardisation des noms de fichiers lors de l'upload."""
        # Uploader un document avec un nom de fichier personnalisé
        self.partner.write({
            'document_identity_card': self.sample_pdf_data,
            'document_identity_card_filename': 'custom_name.pdf',
        })
        
        # Vérifier que le nom du fichier a été normalisé
        expected_name = f"CNI - {self.partner.name}.pdf"
        self.assertEqual(self.partner.document_identity_card_filename, expected_name)
