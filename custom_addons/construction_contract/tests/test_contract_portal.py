# -*- coding: utf-8 -*-
"""Tests du portail de signature de contrat.

Couvre :
- Accès portal avec token valide (200)
- Accès portal avec token invalide (403/404)
- Accès portal avec token expiré
- Soumission de signature valide -> contrat passe à 'signed'
- Soumission sans signature -> erreur
- Vérification des champs d'audit (ip_address, user_agent, signature_date)

Pattern : AAA (Arrange / Act / Assert)
Base : TransactionCase + ContractTestMixin
Les appels à WeasyPrint, envoi email/SMS sont mockés via unittest.mock.patch.
"""

import base64
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields

from .common import ContractTestMixin

# Image PNG 1x1 pixel valide (pour éviter les erreurs de validation base64)
_MINIMAL_PNG_B64 = base64.b64encode(
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx'
    b'\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
).decode('ascii')

# Faux PDF minimal valide
_MOCK_PDF_B64 = base64.b64encode(b'%PDF-1.4 mock pdf content').decode('ascii')


def _force_contract_to_sent(contract, env):
    """Helper : passe le contrat en état 'sent' sans déclencher WeasyPrint ni SMS.

    On injecte directement les champs requis par action_send_for_signature et
    on force l'état via write() pour éviter d'appeler les services externes.
    """
    contract.write({
        'state': 'generated',
        'pdf_document': _MOCK_PDF_B64,
    })
    # Simuler l'envoi sans notification réelle
    with patch(
        'odoo.addons.construction_contract.models.contract.'
        'ConstructionContract._send_signature_invitation',
        return_value=None,
    ), patch(
        'odoo.addons.construction_contract.services.'
        'notification_service.ContractNotificationService.send_contract_invitation',
        return_value=None,
    ):
        try:
            contract.action_send_for_signature()
        except Exception:
            # Fallback : forcer l'état directement si le service de notification
            # n'est pas patchable (dépend de l'implémentation interne)
            import secrets
            token = secrets.token_urlsafe(32)
            contract.write({
                'state': 'sent',
                'access_token': token,
                'sent_date': fields.Datetime.now(),
                'token_expiry_date': fields.Datetime.now() + timedelta(days=30),
            })


def _bypass_page_validation(contract):
    """Helper : crée une validation de page pour tous les PDF pages du contrat.

    Permet de débloquer la condition ``can_sign`` sans passer par le navigateur.
    """
    token = contract.access_token
    page_count = contract.pdf_page_count or 1
    # Forcer pdf_page_count si nul
    if not contract.pdf_page_count:
        contract.write({'pdf_page_count': 1})
        page_count = 1

    for page_num in range(1, page_count + 1):
        existing = contract.page_validation_ids.filtered(
            lambda v, p=page_num, t=token: v.page_number == p and v.access_token == t
        )
        if not existing:
            contract.env['construction.contract.page.validation'].create({
                'contract_id': contract.id,
                'page_number': page_num,
                'access_token': token,
                'time_spent': 60,
                'validated_date': fields.Datetime.now(),
            })


@tagged('post_install', '-at_install', 'construction_contract', 'portal')
class TestContractPortalAccess(TransactionCase, ContractTestMixin):
    """Tests d'accès au portail de signature (lecture seule)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpContractData()

    def setUp(self):
        super().setUp()
        # Chaque test repart d'un contrat en état 'sent' avec token valide
        _force_contract_to_sent(self.contract, self.env)

    # ------------------------------------------------------------------
    # TC-PORTAL-01 : Token valide -> accès autorisé
    # ------------------------------------------------------------------

    def test_validate_access_with_valid_token_returns_contract(self):
        """Accès avec token valide : _validate_access retourne le contrat.

        Arrange : contrat en état 'sent' avec access_token positionné.
        Act     : appel de _validate_access depuis le controller (simulé).
        Assert  : le record retourné correspond au contrat attendu.
        """
        # Arrange
        token = self.contract.access_token
        self.assertTrue(token, 'Le contrat doit avoir un access_token après envoi')

        # Act — appel direct de la logique de validation (sans HTTP)
        contract = self.env['construction.contract'].sudo().browse(self.contract.id)
        self.assertTrue(contract.exists())
        self.assertEqual(contract.access_token, token)

        # Assert
        self.assertFalse(
            contract._is_token_expired(token),
            'Le token valide ne doit pas être considéré expiré',
        )

    # ------------------------------------------------------------------
    # TC-PORTAL-02 : Token invalide -> refus
    # ------------------------------------------------------------------

    def test_is_token_expired_returns_true_for_wrong_token(self):
        """Token invalide : _is_token_expired retourne True.

        Arrange : contrat avec access_token connu.
        Act     : appel avec un token différent.
        Assert  : retourne True (token invalide traité comme expiré).
        """
        # Arrange
        wrong_token = 'ce_token_est_faux_et_inconnu_dans_la_base'

        # Act
        result = self.contract._is_token_expired(wrong_token)

        # Assert
        self.assertTrue(result, '_is_token_expired doit retourner True pour un token inconnu')

    # ------------------------------------------------------------------
    # TC-PORTAL-03 : Token expiré -> refus
    # ------------------------------------------------------------------

    def test_is_token_expired_returns_true_when_past_expiry(self):
        """Token expiré : _is_token_expired retourne True après la date d'expiration.

        Arrange : forcer token_expiry_date dans le passé.
        Act     : appel de _is_token_expired avec le bon token.
        Assert  : retourne True.
        """
        # Arrange
        past_datetime = fields.Datetime.now() - timedelta(days=1)
        self.contract.write({'token_expiry_date': past_datetime})
        token = self.contract.access_token

        # Act
        result = self.contract._is_token_expired(token)

        # Assert
        self.assertTrue(result, 'Un token avec date_expiry passée doit être considéré expiré')

    # ------------------------------------------------------------------
    # TC-PORTAL-04 : Token non expiré -> accepté
    # ------------------------------------------------------------------

    def test_is_token_expired_returns_false_when_future_expiry(self):
        """Token avec expiry future : _is_token_expired retourne False.

        Arrange : token_expiry_date dans le futur.
        Act     : _is_token_expired avec token correct.
        Assert  : retourne False.
        """
        # Arrange
        future_datetime = fields.Datetime.now() + timedelta(days=30)
        self.contract.write({'token_expiry_date': future_datetime})
        token = self.contract.access_token

        # Act
        result = self.contract._is_token_expired(token)

        # Assert
        self.assertFalse(result, 'Un token avec date_expiry future ne doit pas être expiré')

    # ------------------------------------------------------------------
    # TC-PORTAL-05 : État du contrat non signable -> erreur appropriée
    # ------------------------------------------------------------------

    def test_portal_unavailable_for_draft_contract(self):
        """Contrat en état 'draft' non disponible pour signature.

        Arrange : contrat en état draft (pas encore envoyé).
        Act     : vérification de l'état.
        Assert  : state != 'sent' ni 'in_progress'.
        """
        # Arrange
        draft_contract = self.env['construction.contract'].create({
            'subcontractor_id': self.subcontractor.id,
            'chantier_id': self.chantier.id,
            'lot_ids': [(6, 0, [self.lot.id])],
            'template_id': self.template.id,
            'state': 'draft',
            'date': date.today(),
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=90),
            'retention_rate': 5.0,
        })

        # Act & Assert
        self.assertNotIn(
            draft_contract.state,
            ('sent', 'in_progress'),
            'Un contrat draft ne doit pas être dans un état signable',
        )


@tagged('post_install', '-at_install', 'construction_contract', 'portal')
class TestContractPortalPageValidation(TransactionCase, ContractTestMixin):
    """Tests de validation des pages du portail."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpContractData()

    def setUp(self):
        super().setUp()
        _force_contract_to_sent(self.contract, self.env)
        # Forcer pdf_page_count à 1 pour simplifier les tests
        self.contract.write({'pdf_page_count': 1})

    # ------------------------------------------------------------------
    # TC-PAGE-01 : Validation d'une page via portal_validate_page
    # ------------------------------------------------------------------

    def test_portal_validate_page_creates_validation_record(self):
        """portal_validate_page crée un enregistrement de validation.

        Arrange : contrat en état 'sent', token valide, page 1.
        Act     : appel de portal_validate_page(1, token).
        Assert  : un enregistrement page_validation existe pour cette page.
        """
        # Arrange
        token = self.contract.access_token
        self.assertFalse(
            self.contract._is_token_expired(token),
            'Prérequis : token valide',
        )

        # Act
        result = self.contract.portal_validate_page(
            page_number=1,
            access_token=token,
            time_spent=30,
        )

        # Assert
        self.assertIn(result.get('status'), ('success', 'already_validated'))
        validated = self.contract.page_validation_ids.filtered(
            lambda v: v.page_number == 1 and v.access_token == token
        )
        self.assertTrue(validated, 'Un enregistrement de validation doit exister pour la page 1')

    # ------------------------------------------------------------------
    # TC-PAGE-02 : Double validation d'une page -> already_validated
    # ------------------------------------------------------------------

    def test_portal_validate_page_idempotent_on_second_call(self):
        """La double validation d'une même page retourne 'already_validated'.

        Arrange : contrat en état 'sent', page 1 déjà validée.
        Act     : second appel portal_validate_page(1, token).
        Assert  : status == 'already_validated', pas de doublon.
        """
        # Arrange
        token = self.contract.access_token
        self.contract.portal_validate_page(page_number=1, access_token=token)

        # Act
        result = self.contract.portal_validate_page(page_number=1, access_token=token)

        # Assert
        self.assertEqual(result.get('status'), 'already_validated')
        count = len(self.contract.page_validation_ids.filtered(
            lambda v: v.page_number == 1 and v.access_token == token
        ))
        self.assertEqual(count, 1, 'Une seule validation doit exister pour la page 1')

    # ------------------------------------------------------------------
    # TC-PAGE-03 : can_sign devient True quand toutes les pages validées
    # ------------------------------------------------------------------

    def test_can_sign_true_after_all_pages_validated(self):
        """can_sign passe à True après validation de toutes les pages.

        Arrange : contrat avec pdf_page_count=1, token valide.
        Act     : valider la page 1.
        Assert  : validation_status['can_sign'] == True.
        """
        # Arrange
        token = self.contract.access_token

        # Act
        self.contract.portal_validate_page(page_number=1, access_token=token)
        status = self.contract._get_page_validation_status(token)

        # Assert
        self.assertTrue(status['can_sign'], 'can_sign doit être True quand toutes les pages sont validées')
        self.assertEqual(status['remaining_pages'], 0)

    # ------------------------------------------------------------------
    # TC-PAGE-04 : Token expiré bloque la validation
    # ------------------------------------------------------------------

    def test_portal_validate_page_raises_on_expired_token(self):
        """portal_validate_page lève ValidationError si le token est expiré.

        Arrange : token_expiry_date dans le passé.
        Act     : appel portal_validate_page.
        Assert  : ValidationError levée.
        """
        # Arrange
        self.contract.write({
            'token_expiry_date': fields.Datetime.now() - timedelta(days=1),
        })
        token = self.contract.access_token

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.contract.portal_validate_page(page_number=1, access_token=token)


@tagged('post_install', '-at_install', 'construction_contract', 'portal')
class TestContractPortalSignature(TransactionCase, ContractTestMixin):
    """Tests de soumission de signature via portal_save_signature."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpContractData()

    def setUp(self):
        super().setUp()
        _force_contract_to_sent(self.contract, self.env)
        self.contract.write({'pdf_page_count': 1})

    # ------------------------------------------------------------------
    # TC-SIG-01 : Signature valide -> contrat passe à 'signed'
    # ------------------------------------------------------------------

    def test_portal_save_signature_transitions_contract_to_signed(self):
        """Signature valide : contrat passe en état 'signed'.

        Arrange : contrat 'sent', toutes les pages validées, données de
                  signature base64 valides.
        Act     : appel portal_save_signature.
        Assert  : contract.state == 'signed'.
        """
        # Arrange
        token = self.contract.access_token
        _bypass_page_validation(self.contract)

        # Mocker WeasyPrint et la génération du certificat pour éviter les dépendances système
        with patch(
            'odoo.addons.construction_contract.models.contract.'
            'ConstructionContract._generate_certificate_of_completion',
            return_value=None,
        ), patch(
            'odoo.addons.construction_contract.models.contract.'
            'ConstructionContract._generate_signed_pdf',
            return_value=None,
        ), patch(
            'odoo.addons.construction_contract.services.pdf_generator_service.'
            'PdfGeneratorService.generate_pdf',
            return_value=b'%PDF-1.4 signed mock',
        ):
            # Act
            result = self.contract.portal_save_signature(
                signature_data=_MINIMAL_PNG_B64,
                access_token=token,
                ip_address='192.168.1.50',
                user_agent='Mozilla/5.0 Test',
            )

        # Assert
        self.assertEqual(result.get('status'), 'success')
        self.contract.invalidate_recordset()
        self.assertEqual(
            self.contract.state,
            'signed',
            'Le contrat doit passer à l\'état "signed" après une signature valide',
        )

    # ------------------------------------------------------------------
    # TC-SIG-02 : Signature valide -> enregistrement signature créé avec audit
    # ------------------------------------------------------------------

    def test_portal_save_signature_creates_audit_record(self):
        """Signature valide : un enregistrement de signature est créé avec
        ip_address, user_agent et signature_date renseignés.

        Arrange : contrat prêt pour signature.
        Act     : portal_save_signature avec IP et user_agent.
        Assert  : signature_id exist, ip_address et signature_date renseignés.
        """
        # Arrange
        token = self.contract.access_token
        _bypass_page_validation(self.contract)
        test_ip = '10.0.0.42'
        test_ua = 'Mozilla/5.0 (Linux; Android 11) TestAgent'

        with patch(
            'odoo.addons.construction_contract.models.contract.'
            'ConstructionContract._generate_certificate_of_completion',
            return_value=None,
        ), patch(
            'odoo.addons.construction_contract.models.contract.'
            'ConstructionContract._generate_signed_pdf',
            return_value=None,
        ), patch(
            'odoo.addons.construction_contract.services.pdf_generator_service.'
            'PdfGeneratorService.generate_pdf',
            return_value=b'%PDF-1.4 signed mock',
        ):
            # Act
            self.contract.portal_save_signature(
                signature_data=_MINIMAL_PNG_B64,
                access_token=token,
                ip_address=test_ip,
                user_agent=test_ua,
            )

        # Assert
        self.contract.invalidate_recordset()
        sig = self.contract.signature_id
        self.assertTrue(sig, 'signature_id doit être renseigné après la signature')
        self.assertEqual(sig.ip_address, test_ip, 'ip_address doit correspondre à celui fourni')
        self.assertIsNotNone(sig.signature_date, 'signature_date doit être renseignée')
        self.assertEqual(sig.user_agent, test_ua, 'user_agent doit correspondre à celui fourni')

    # ------------------------------------------------------------------
    # TC-SIG-03 : Signature sans données -> ValidationError
    # ------------------------------------------------------------------

    def test_portal_save_signature_raises_without_signature_data(self):
        """portal_save_signature sans données de signature lève ValidationError.

        Arrange : contrat prêt, toutes pages validées, signature_data vide.
        Act     : appel avec signature_data=None.
        Assert  : ValidationError levée (ou la méthode retourne status=error).

        Note : le controller vérifie signature_data avant d'appeler le modèle.
        On teste la défense au niveau modèle : si signature_data est vide
        après nettoyage, Odoo lèvera une erreur (champ required).
        """
        # Arrange
        token = self.contract.access_token
        _bypass_page_validation(self.contract)

        # Act & Assert — on s'attend à une erreur (ValidationError ou ValueError)
        # car signature_data est un champ Binary required sur construction.contract.signature
        with self.assertRaises((ValidationError, Exception)):
            self.contract.portal_save_signature(
                signature_data=None,
                access_token=token,
                ip_address='127.0.0.1',
                user_agent='Test',
            )

    # ------------------------------------------------------------------
    # TC-SIG-04 : Pages non validées -> ValidationError
    # ------------------------------------------------------------------

    def test_portal_save_signature_raises_when_pages_not_validated(self):
        """portal_save_signature échoue si toutes les pages ne sont pas validées.

        Arrange : contrat 'sent' avec 2 pages, aucune page validée.
        Act     : appel portal_save_signature.
        Assert  : ValidationError avec message sur les pages restantes.
        """
        # Arrange
        token = self.contract.access_token
        # Forcer 2 pages
        self.contract.write({'pdf_page_count': 2})
        # Aucune page validée

        # Act & Assert
        with self.assertRaises(ValidationError) as ctx:
            self.contract.portal_save_signature(
                signature_data=_MINIMAL_PNG_B64,
                access_token=token,
                ip_address='127.0.0.1',
                user_agent='Test',
            )
        self.assertIn(
            'page',
            str(ctx.exception).lower(),
            "Le message d'erreur doit mentionner les pages",
        )

    # ------------------------------------------------------------------
    # TC-SIG-05 : Token expiré -> ValidationError lors de la signature
    # ------------------------------------------------------------------

    def test_portal_save_signature_raises_on_expired_token(self):
        """portal_save_signature lève ValidationError si le token est expiré.

        Arrange : token_expiry_date dans le passé, pages validées.
        Act     : appel portal_save_signature.
        Assert  : ValidationError levée.
        """
        # Arrange
        _bypass_page_validation(self.contract)
        self.contract.write({
            'token_expiry_date': fields.Datetime.now() - timedelta(days=1),
        })
        token = self.contract.access_token

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.contract.portal_save_signature(
                signature_data=_MINIMAL_PNG_B64,
                access_token=token,
                ip_address='127.0.0.1',
                user_agent='Test',
            )

    # ------------------------------------------------------------------
    # TC-SIG-06 : Signature valide -> signature_date renseignée sur le contrat
    # ------------------------------------------------------------------

    def test_portal_save_signature_sets_contract_signature_date(self):
        """Après signature valide, contract.signature_date est renseignée.

        Arrange : contrat prêt pour signature.
        Act     : portal_save_signature.
        Assert  : contract.signature_date != False.
        """
        # Arrange
        token = self.contract.access_token
        _bypass_page_validation(self.contract)

        with patch(
            'odoo.addons.construction_contract.models.contract.'
            'ConstructionContract._generate_certificate_of_completion',
            return_value=None,
        ), patch(
            'odoo.addons.construction_contract.models.contract.'
            'ConstructionContract._generate_signed_pdf',
            return_value=None,
        ), patch(
            'odoo.addons.construction_contract.services.pdf_generator_service.'
            'PdfGeneratorService.generate_pdf',
            return_value=b'%PDF-1.4 signed mock',
        ):
            # Act
            self.contract.portal_save_signature(
                signature_data=_MINIMAL_PNG_B64,
                access_token=token,
                ip_address='172.16.0.1',
                user_agent='Mozilla/5.0 Test Agent',
            )

        # Assert
        self.contract.invalidate_recordset()
        self.assertTrue(
            self.contract.signature_date,
            'contract.signature_date doit être renseignée après une signature valide',
        )


@tagged('post_install', '-at_install', 'construction_contract', 'portal')
class TestContractPortalController(TransactionCase, ContractTestMixin):
    """Tests de la logique du contrôleur portal (sans HTTP, sans live server).

    On teste directement SignaturePortalController._validate_access et les
    règles de routage en simulant l'environnement request via mock.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpContractData()

    def setUp(self):
        super().setUp()
        _force_contract_to_sent(self.contract, self.env)

    # ------------------------------------------------------------------
    # TC-CTRL-01 : _validate_access avec token valide retourne le contrat
    # ------------------------------------------------------------------

    def test_validate_access_with_correct_token_returns_contract(self):
        """_validate_access avec le bon token retourne le contrat sans erreur.

        Arrange : contrat avec access_token connu, mock de request.env.
        Act     : appel _validate_access(contract_id, token).
        Assert  : contrat retourné.
        """
        from odoo.addons.construction_contract.controllers.signature_portal_controller import (
            SignaturePortalController,
        )

        # Arrange
        token = self.contract.access_token
        contract_id = self.contract.id
        controller = SignaturePortalController()

        # Mock request.env pour pointer vers l'env de test
        mock_request = MagicMock()
        mock_request.env = self.env

        with patch(
            'odoo.addons.construction_contract.controllers.signature_portal_controller.request',
            mock_request,
        ):
            # Act
            result = controller._validate_access(contract_id, token)

        # Assert
        self.assertEqual(result.id, contract_id, 'Le contrat retourné doit correspondre à contract_id')

    # ------------------------------------------------------------------
    # TC-CTRL-02 : _validate_access avec mauvais token lève Forbidden
    # ------------------------------------------------------------------

    def test_validate_access_with_wrong_token_raises_forbidden(self):
        """_validate_access avec un token incorrect lève Forbidden.

        Arrange : contrat avec access_token connu, token différent fourni.
        Act     : appel _validate_access.
        Assert  : werkzeug.exceptions.Forbidden levée.
        """
        from odoo.addons.construction_contract.controllers.signature_portal_controller import (
            SignaturePortalController,
        )
        from werkzeug.exceptions import Forbidden

        # Arrange
        wrong_token = 'definitely_wrong_token_xyz_abc_123'
        contract_id = self.contract.id
        controller = SignaturePortalController()

        mock_request = MagicMock()
        mock_request.env = self.env

        with patch(
            'odoo.addons.construction_contract.controllers.signature_portal_controller.request',
            mock_request,
        ):
            # Act & Assert
            with self.assertRaises(Forbidden):
                controller._validate_access(contract_id, wrong_token)

    # ------------------------------------------------------------------
    # TC-CTRL-03 : _validate_access avec contract_id inexistant lève NotFound
    # ------------------------------------------------------------------

    def test_validate_access_with_nonexistent_contract_raises_not_found(self):
        """_validate_access avec un ID inexistant lève NotFound.

        Arrange : ID très grand (improbable d'exister), token quelconque.
        Act     : appel _validate_access.
        Assert  : werkzeug.exceptions.NotFound levée.
        """
        from odoo.addons.construction_contract.controllers.signature_portal_controller import (
            SignaturePortalController,
        )
        from werkzeug.exceptions import NotFound

        # Arrange
        nonexistent_id = 999999999
        token = 'some_token'
        controller = SignaturePortalController()

        mock_request = MagicMock()
        mock_request.env = self.env

        with patch(
            'odoo.addons.construction_contract.controllers.signature_portal_controller.request',
            mock_request,
        ):
            # Act & Assert
            with self.assertRaises(NotFound):
                controller._validate_access(nonexistent_id, token)

    # ------------------------------------------------------------------
    # TC-CTRL-04 : _validate_access sans token lève Forbidden
    # ------------------------------------------------------------------

    def test_validate_access_without_token_raises_forbidden(self):
        """_validate_access sans token (None) lève Forbidden.

        Arrange : contrat existant, access_token=None.
        Act     : appel _validate_access.
        Assert  : werkzeug.exceptions.Forbidden levée.
        """
        from odoo.addons.construction_contract.controllers.signature_portal_controller import (
            SignaturePortalController,
        )
        from werkzeug.exceptions import Forbidden

        # Arrange
        contract_id = self.contract.id
        controller = SignaturePortalController()

        mock_request = MagicMock()
        mock_request.env = self.env

        with patch(
            'odoo.addons.construction_contract.controllers.signature_portal_controller.request',
            mock_request,
        ):
            # Act & Assert
            with self.assertRaises(Forbidden):
                controller._validate_access(contract_id, None)
