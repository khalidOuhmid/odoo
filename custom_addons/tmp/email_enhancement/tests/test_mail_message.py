# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestMailMessage(TransactionCase):
    """Tests pour le module email_enhancement"""

    def setUp(self):
        super().setUp()
        # Créer un partenaire de test
        self.test_partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'partner@example.com',
        })
        
        # Créer un message de test
        self.test_message = self.env['mail.message'].create({
            'model': 'res.partner',
            'res_id': self.test_partner.id,
            'message_type': 'comment',
            'subtype_id': self.env.ref('mail.mt_comment').id,
            'body': 'Test message body',
            'subject': 'Test Subject',
            'partner_ids': [(6, 0, [self.test_partner.id])],
        })

    def test_create_reply_message(self):
        """Test de création d'un message de réponse"""
        # Créer une réponse
        reply_message = self.env['mail.message'].create_reply_message(
            parent_message_id=self.test_message.id,
            body='Reply message body',
            subject='Re: Test Subject',
            partner_ids=[self.test_partner.id]
        )
        
        # Vérifications
        self.assertTrue(reply_message.exists())
        self.assertEqual(reply_message.parent_id, self.test_message)
        self.assertEqual(reply_message.body, 'Reply message body')
        self.assertEqual(reply_message.subject, 'Re: Test Subject')

    def test_get_reply_context(self):
        """Test de récupération du contexte pour une réponse"""
        context = self.test_message.get_reply_context()
        
        # Vérifications
        self.assertIn('default_model', context)
        self.assertIn('default_res_ids', context)
        self.assertIn('default_parent_id', context)
        self.assertIn('default_subject', context)
        
        self.assertEqual(context['default_model'], 'res.partner')
        self.assertEqual(context['default_res_ids'], [self.test_partner.id])
        self.assertEqual(context['default_parent_id'], self.test_message.id)
        self.assertEqual(context['default_subject'], 'Re: Test Subject')
