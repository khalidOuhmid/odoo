# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class BlgDocument(models.Model):
    """
    Manages all documents related to construction projects.
    Includes automatic reminders for expiring documents.
    """
    _name = 'blg.document'
    _description = 'Project Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Document Name', required=True)
    chantier_id = fields.Many2one('blg.chantier', string='Project')
    partner_id = fields.Many2one('res.partner', string='Related Partner')
    lot_id = fields.Many2one('blg.chantier.lot', string='Work Section')

    document_type = fields.Selection([
        ('quote', 'Quote'),
        ('contract', 'Contract'),
        ('insurance', 'Insurance'),
        ('kbis', 'KBIS Extract'),
        ('urssaf', 'URSSAF Certificate'),
        ('id', 'ID Document'),
        ('specs', 'Technical Specifications'),
        ('plan', 'Plan'),
        ('schedule', 'Schedule'),
        ('other', 'Other')
    ], string='Document Type', required=True)

    file = fields.Binary('File', required=True)
    filename = fields.Char('Filename')
    
    expiry_date = fields.Date('Expiry Date')
    description = fields.Text('Description')
    
    state = fields.Selection([
        ('valid', 'Valid'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected')
    ], string='Status', compute='_compute_state', store=True)

    @api.depends('expiry_date')
    def _compute_state(self):
        """Compute document state based on expiry date"""
        today = fields.Date.today()
        for doc in self:
            if not doc.expiry_date:
                doc.state = 'valid'
            elif doc.expiry_date < today:
                doc.state = 'expired'
            elif doc.expiry_date <= today + timedelta(days=30):
                doc.state = 'expiring'
            else:
                doc.state = 'valid'

    @api.model
    def check_expiring_documents(self):
        """Cron job to send reminders for expiring documents"""
        # Find documents expiring in 7 days
        date_limit = fields.Date.today() + timedelta(days=7)
        expiring_docs = self.search([
            ('expiry_date', '<=', date_limit),
            ('expiry_date', '>=', fields.Date.today()),
            ('state', '!=', 'expired')
        ])
        
        for doc in expiring_docs:
            # Send notification to project manager
            if doc.chantier_id and doc.chantier_id.user_ids:
                for user in doc.chantier_id.user_ids:
                    doc.activity_schedule(
                        'mail.mail_activity_data_warning',
                        user_id=user.id,
                        note=f"Document '{doc.name}' expires on {doc.expiry_date}"
                    )
