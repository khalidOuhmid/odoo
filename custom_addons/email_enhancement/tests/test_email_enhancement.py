# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('email_enhancement')
class TestEmailEnhancement(TransactionCase):
    """Tests pour le module email_enhancement"""

    def setUp(self):
        super().setUp()
        
        # Créer un utilisateur de test
        self.test_user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser',
            'email': 'test@example.com',
        })
        
        # Créer un partenaire de test
        self.test_partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'partner@example.com',
        })
        
        # Créer un message de test
        self.test_message = self.env['mail.message'].create({
            'subject': 'Test Message',
            'body': '<p>Contenu du message de test</p>',
            'message_type': 'comment',
            'model': 'res.partner',
            'res_id': self.test_partner.id,
            'author_id': self.test_user.partner_id.id,
        })

    def test_create_reply_message_success(self):
        """Test la création d'une réponse à un message"""
        reply = self.env['mail.message'].create_reply_message(
            parent_message_id=self.test_message.id,
            body='<p>Ceci est une réponse</p>',
            subject='Re: Test Message',
            partner_ids=[self.test_partner.id]
        )
        
        self.assertTrue(reply.exists(), "Le message de réponse doit être créé")
        self.assertEqual(reply.parent_id.id, self.test_message.id, "Le parent_id doit être correct")
        self.assertEqual(reply.model, self.test_message.model, "Le model doit être hérité du parent")
        self.assertEqual(reply.res_id, self.test_message.res_id, "Le res_id doit être hérité du parent")
        self.assertIn('Re:', reply.subject, "Le sujet doit contenir 'Re:'")

    def test_create_reply_message_nonexistent_parent(self):
        """Test la gestion d'erreur pour un message parent inexistant"""
        with self.assertRaises(UserError):
            self.env['mail.message'].create_reply_message(
                parent_message_id=99999,  # ID inexistant
                body='<p>Réponse à un message inexistant</p>'
            )

    def test_create_reply_message_default_subject(self):
        """Test la génération automatique du sujet"""
        # Message sans sujet
        message_no_subject = self.env['mail.message'].create({
            'body': '<p>Message sans sujet</p>',
            'message_type': 'comment',
            'model': 'res.partner',
            'res_id': self.test_partner.id,
        })
        
        reply = self.env['mail.message'].create_reply_message(
            parent_message_id=message_no_subject.id,
            body='<p>Réponse automatique</p>'
        )
        
        self.assertEqual(reply.subject, 'Re: Message', "Le sujet par défaut doit être 'Re: Message'")

    def test_get_reply_context(self):
        """Test la génération du contexte pour une réponse"""
        context = self.test_message.get_reply_context()
        
        self.assertEqual(context['default_model'], self.test_message.model)
        self.assertEqual(context['default_res_ids'], [self.test_message.res_id])
        self.assertEqual(context['default_parent_id'], self.test_message.id)
        self.assertIn('Re:', context['default_subject'])
        self.assertEqual(context['default_message_type'], 'comment')

    def test_compose_message_reply_context(self):
        """Test l'extension du wizard de composition pour les réponses"""
        # Créer un contexte de réponse
        context = {
            'default_parent_id': self.test_message.id,
            'default_model': self.test_message.model,
            'default_res_ids': [self.test_message.res_id],
        }
        
        # Créer le wizard avec le contexte
        wizard = self.env['mail.compose.message'].with_context(**context).create({
            'subject': 'Test Reply',
            'body': '<p>Ceci est une réponse de test</p>',
        })
        
        self.assertEqual(wizard.parent_message_id.id, self.test_message.id)
        self.assertIn(self.test_user.partner_id.id, wizard.partner_ids.ids)

    def test_reply_email_threading(self):
        """Test que les réponses créent un vrai thread email avec headers appropriés"""
        # Créer un message avec message_id (simule un email entrant)
        original_message = self.env['mail.message'].create({
            'subject': 'Test Email Original',
            'body': '<p>Message original</p>',
            'message_type': 'email',
            'model': 'res.partner',
            'res_id': self.test_partner.id,
            'author_id': self.test_user.partner_id.id,
            'message_id': '<original-123@example.com>',  # Simule un vrai email
        })
        
        # Créer une réponse
        reply = self.env['mail.message'].create_reply_message(
            parent_message_id=original_message.id,
            body='<p>Ceci est une vraie réponse</p>',
            subject='Re: Test Email Original',
            partner_ids=[self.test_partner.id]
        )
        
        # Vérifications
        self.assertTrue(reply.exists(), "Le message de réponse doit être créé")
        self.assertEqual(reply.parent_id.id, original_message.id, "La réponse doit être liée au message original")
        self.assertIn('Re:', reply.subject, "Le sujet doit contenir 'Re:'")
        
        # Vérifier que c'est bien un thread
        self.assertEqual(reply.model, original_message.model)
        self.assertEqual(reply.res_id, original_message.res_id)

    def test_compose_message_email_headers(self):
        """Test que le wizard de composition ajoute les bons headers pour les réponses"""
        # Créer un message email original avec message_id
        original_message = self.env['mail.message'].create({
            'subject': 'Original Email',
            'body': '<p>Original content</p>',
            'message_type': 'email',
            'model': 'res.partner',
            'res_id': self.test_partner.id,
            'author_id': self.test_user.partner_id.id,
            'message_id': '<original-456@example.com>',
        })
        
        # Créer le wizard de composition avec contexte de réponse
        context = {
            'default_parent_id': original_message.id,
            'default_model': 'res.partner',
            'default_res_ids': [self.test_partner.id],
        }
        
        wizard = self.env['mail.compose.message'].with_context(**context).create({
            'subject': 'Re: Original Email',
            'body': '<p>Ma réponse</p>',
            'partner_ids': [(6, 0, [self.test_partner.id])],
        })
        
        # Vérifier que le parent_message_id est correctement défini
        self.assertEqual(wizard.parent_message_id.id, original_message.id)
        
        # Vérifier la préparation des mail_values
        mail_values = wizard._prepare_mail_values([self.test_partner.id])
        
        # Vérifier que les headers de threading sont présents
        if self.test_partner.id in mail_values:
            headers = mail_values[self.test_partner.id]
            self.assertIn('reply_to_message_id', headers)
            self.assertEqual(headers['reply_to_message_id'], '<original-456@example.com>')

    def test_message_post_integration(self):
        """Test l'intégration avec message_post"""
        # Simuler une réponse créée via message_post
        reply = self.test_partner.message_post(
            body='<p>Réponse via message_post</p>',
            subject='Re: Test Integration',
            parent_id=self.test_message.id,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        
        self.assertTrue(reply.exists())
        self.assertEqual(reply.parent_id.id, self.test_message.id)
        self.assertEqual(reply.model, 'res.partner')
        self.assertEqual(reply.res_id, self.test_partner.id)
