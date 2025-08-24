# -*- coding: utf-8 -*-
"""
Gestion des emails entrants pour création automatique de chantiers
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import re

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def _routing_handle_bounce(self, email_message, message_dict):
        """Gestion des emails entrants pour création automatique de chantiers"""
        super()._routing_handle_bounce(email_message, message_dict)
        
        # Vérifier si l'email est destiné à la création de chantier
        self._handle_construction_project_creation(email_message, message_dict)

    def _handle_construction_project_creation(self, email_message, message_dict):
        """Gère la création automatique de chantiers depuis les emails"""
        try:
            # Vérifier si l'email est destiné à la création de chantier
            if not self._is_construction_project_email(email_message):
                return

            # Extraire les informations du chantier depuis l'email
            project_data = self._extract_project_data_from_email(email_message, message_dict)
            
            if not project_data:
                _logger.warning("Impossible d'extraire les données du projet depuis l'email")
                return

            # Créer le chantier
            chantier = self._create_construction_project(project_data)
            
            if chantier:
                _logger.info(f"Chantier créé automatiquement: {chantier.name} (ID: {chantier.id})")
                
                # Créer une activité pour notifier l'utilisateur
                self._create_notification_activity(chantier, email_message)
                
        except Exception as e:
            _logger.error(f"Erreur lors de la création automatique du chantier: {str(e)}")

    def _is_construction_project_email(self, email_message):
        """Vérifie si l'email est destiné à la création de chantier"""
        # Adresse email dédiée pour les appels d'offre
        construction_email = self.env['ir.config_parameter'].sudo().get_param(
            'construction_base.construction_project_email', 
            'appel-doffre@blggroupe.com'
        )
        
        # Vérifier si l'email est destiné à cette adresse
        if hasattr(email_message, 'to') and construction_email in email_message.to:
            return True
            
        # Vérifier dans le sujet
        if hasattr(email_message, 'subject'):
            subject = email_message.subject.lower()
            keywords = ['appel d\'offre', 'appel doffre', 'projet construction', 'chantier']
            if any(keyword in subject for keyword in keywords):
                return True
                
        return False

    def _extract_project_data_from_email(self, email_message, message_dict):
        """Extrait les données du projet depuis l'email"""
        project_data = {
            'name': '',
            'client': None,
            'description': '',
            'address': '',
            'city': '',
            'zip_code': '',
            'phone': '',
        }
        
        try:
            # Nom du projet = sujet de l'email
            if hasattr(email_message, 'subject'):
                project_data['name'] = email_message.subject.strip()
            
            # Description = contenu de l'email
            if hasattr(email_message, 'body'):
                project_data['description'] = email_message.body.strip()
            
            # Extraire les informations du client depuis l'email
            client_data = self._extract_client_data_from_email(email_message)
            if client_data:
                project_data['client'] = client_data
            
            # Extraire l'adresse depuis le contenu de l'email
            address_data = self._extract_address_from_email_content(email_message.body)
            if address_data:
                project_data.update(address_data)
            
            # Extraire le téléphone
            phone = self._extract_phone_from_email_content(email_message.body)
            if phone:
                project_data['phone'] = phone
                
        except Exception as e:
            _logger.error(f"Erreur lors de l'extraction des données: {str(e)}")
            return None
            
        return project_data

    def _extract_client_data_from_email(self, email_message):
        """Extrait les informations du client depuis l'email"""
        try:
            # Chercher le client par email
            if hasattr(email_message, 'from'):
                email_from = email_message.from_
                client = self.env['res.partner'].search([
                    ('email', '=', email_from)
                ], limit=1)
                
                if client:
                    return client
                
                # Si pas trouvé, créer un nouveau client
                client_name = self._extract_name_from_email(email_from)
                if client_name:
                    client = self.env['res.partner'].create({
                        'name': client_name,
                        'email': email_from,
                        'is_company': True,
                    })
                    return client
                    
        except Exception as e:
            _logger.error(f"Erreur lors de l'extraction du client: {str(e)}")
            
        return None

    def _extract_name_from_email(self, email):
        """Extrait le nom depuis une adresse email"""
        if '@' in email:
            name_part = email.split('@')[0]
            # Remplacer les points et tirets par des espaces
            name_part = name_part.replace('.', ' ').replace('-', ' ').replace('_', ' ')
            # Capitaliser
            return ' '.join(word.capitalize() for word in name_part.split())
        return email

    def _extract_address_from_email_content(self, content):
        """Extrait l'adresse depuis le contenu de l'email"""
        address_data = {}
        
        try:
            if not content:
                return address_data
                
            # Patterns pour détecter les adresses
            # Code postal français
            zip_pattern = r'\b\d{5}\b'
            zip_match = re.search(zip_pattern, content)
            if zip_match:
                address_data['zip_code'] = zip_match.group()
            
            # Ville (après le code postal)
            if zip_match:
                after_zip = content[zip_match.end():zip_match.end()+50]
                city_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', after_zip)
                if city_match:
                    address_data['city'] = city_match.group().strip()
            
            # Adresse complète (lignes contenant des numéros)
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                # Chercher une ligne avec un numéro et des mots
                if re.search(r'\d+', line) and len(line.split()) > 2:
                    if not address_data.get('address'):
                        address_data['address'] = line
                        break
                        
        except Exception as e:
            _logger.error(f"Erreur lors de l'extraction de l'adresse: {str(e)}")
            
        return address_data

    def _extract_phone_from_email_content(self, content):
        """Extrait le numéro de téléphone depuis le contenu de l'email"""
        try:
            if not content:
                return None
                
            # Patterns pour les numéros de téléphone français
            phone_patterns = [
                r'\b0[1-9](\s?\d{2}){4}\b',  # 01 23 45 67 89
                r'\b0[1-9]\d{8}\b',          # 0123456789
                r'\+\d{2}\s?0[1-9](\s?\d{2}){4}\b',  # +33 1 23 45 67 89
            ]
            
            for pattern in phone_patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group()
                    
        except Exception as e:
            _logger.error(f"Erreur lors de l'extraction du téléphone: {str(e)}")
            
        return None

    def _create_construction_project(self, project_data):
        """Crée un nouveau chantier avec les données extraites"""
        try:
            # Vérifier que les données minimales sont présentes
            if not project_data.get('name'):
                _logger.warning("Nom du projet manquant")
                return None
                
            if not project_data.get('client'):
                _logger.warning("Client manquant")
                return None
            
            # Obtenir le stage "Appel d'offre" par défaut
            stage_ao = self.env['construction.stage'].search([
                ('code', '=', 'AO')
            ], limit=1)
            
            if not stage_ao:
                _logger.error("Stage 'Appel d'offre' non trouvé")
                return None
            
            # Créer le chantier
            chantier_vals = {
                'name': project_data['name'],
                'client': project_data['client'].id,
                'description': project_data.get('description', ''),
                'address': project_data.get('address', ''),
                'city': project_data.get('city', ''),
                'zip_code': project_data.get('zip_code', ''),
                'phone': project_data.get('phone', ''),
                'stage_id': stage_ao.id,
                'state': 'active',
            }
            
            chantier = self.env['construction.chantier'].create(chantier_vals)
            return chantier
            
        except Exception as e:
            _logger.error(f"Erreur lors de la création du chantier: {str(e)}")
            return None

    def _create_notification_activity(self, chantier, email_message):
        """Crée une activité pour notifier l'utilisateur de la création du chantier"""
        try:
            # Trouver l'utilisateur responsable des chantiers
            responsible_user = self.env['res.users'].search([
                ('groups_id', 'in', self.env.ref('construction_base.group_construction_manager').id)
            ], limit=1)
            
            if not responsible_user:
                return
            
            # Créer l'activité
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'res_model_id': self.env['ir.model']._get('construction.chantier').id,
                'res_id': chantier.id,
                'user_id': responsible_user.id,
                'summary': f'Nouveau chantier créé depuis email: {chantier.name}',
                'note': f"""
                Chantier créé automatiquement depuis un email.
                
                Nom: {chantier.name}
                Client: {chantier.client.name}
                Email source: {getattr(email_message, 'from_', 'Non disponible')}
                
                Veuillez vérifier et compléter les informations du chantier.
                """,
            })
            
            # Envoyer un email de confirmation au client si possible
            self._send_confirmation_email(chantier, email_message)
            
        except Exception as e:
            _logger.error(f"Erreur lors de la création de l'activité: {str(e)}")

    def _send_confirmation_email(self, chantier, email_message):
        """Envoie un email de confirmation au client"""
        try:
            # Vérifier si l'email automatique est activé
            auto_send = self.env['ir.config_parameter'].sudo().get_param(
                'construction_base.auto_send_confirmation_email', 
                'False'
            )
            
            if auto_send != 'True':
                return
            
            # Utiliser le template d'email
            template = self.env.ref('construction_base.email_template_construction_project_created')
            if template and chantier.client.email:
                template.send_mail(chantier.id, force_send=True)
                _logger.info(f"Email de confirmation envoyé pour le chantier {chantier.name}")
                
        except Exception as e:
            _logger.error(f"Erreur lors de l'envoi de l'email de confirmation: {str(e)}")
