# config/notification_templates.py
"""
Templates de notification standardisés pour tous les modules.
Centralise les messages et formats de notification.
"""

from datetime import datetime

# =============== TEMPLATES EMAIL ===============

EMAIL_TEMPLATES = {
    'document_missing': {
        'subject': "{{company_name}} - Documents manquants",
        'body_html': """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #875A7B;">Bonjour {{partner_name}},</h2>

            <p>Dans le cadre de notre collaboration, nous avons besoin des documents suivants :</p>

            <ul style="background: #f8f9fa; padding: 15px; border-left: 4px solid #875A7B;">
                {% for doc in missing_documents %}
                <li style="margin: 5px 0;"><strong>{{doc}}</strong></li>
                {% endfor %}
            </ul>

            <p>📧 Vous pouvez nous les envoyer par email ou via notre portail partenaire.</p>

            {% if upload_link %}
            <p style="text-align: center; margin: 20px 0;">
                <a href="{{upload_link}}" 
                   style="background: #875A7B; color: white; padding: 10px 20px; 
                          text-decoration: none; border-radius: 5px;">
                    📤 Téléverser mes documents
                </a>
            </p>
            {% endif %}

            <p>Merci de nous transmettre ces documents dans les meilleurs délais.</p>

            <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
            <p style="font-size: 12px; color: #666;">
                Cordialement,<br/>
                L'équipe {{company_name}}<br/>
                <em>Ce message a été envoyé automatiquement.</em>
            </p>
        </div>
        """,
        'variables': ['partner_name', 'company_name', 'missing_documents', 'upload_link']
    },

    'document_expiry': {
        'subject': "{{company_name}} - Documents expirant bientôt",
        'body_html': """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #d97826;">⚠️ Bonjour {{partner_name}},</h2>

            <p>Nous vous informons que certains de vos documents vont expirer prochainement :</p>

            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <thead>
                    <tr style="background: #f8f9fa;">
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Document</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Expire dans</th>
                    </tr>
                </thead>
                <tbody>
                    {% for doc_type, days in expiring_documents.items() %}
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">{{doc_type}}</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">
                            {% if days <= 7 %}
                                <span style="color: #d32f2f; font-weight: bold;">{{days}} jour(s) ⚠️</span>
                            {% else %}
                                {{days}} jour(s)
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <p>Merci de renouveler ces documents et de nous transmettre les nouvelles versions.</p>

            <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
            <p style="font-size: 12px; color: #666;">
                Cordialement,<br/>
                L'équipe {{company_name}}
            </p>
        </div>
        """,
        'variables': ['partner_name', 'company_name', 'expiring_documents']
    },

    'state_change': {
        'subject': "{{record_name}} - Changement d'état",
        'body_html': """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #28a745;">Changement d'état</h2>

            <p>L'enregistrement <strong>{{record_name}}</strong> a changé d'état :</p>

            <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p style="margin: 0; font-size: 16px;">
                    <span style="color: #666;">{{old_state}}</span> 
                    <span style="font-size: 20px;">→</span> 
                    <span style="color: #28a745; font-weight: bold;">{{new_state}}</span>
                </p>
            </div>

            {% if comment %}
            <p><strong>Commentaire :</strong> {{comment}}</p>
            {% endif %}

            <p style="font-size: 12px; color: #666;">
                Changement effectué le {{change_date}} par {{changed_by}}
            </p>
        </div>
        """,
        'variables': ['record_name', 'old_state', 'new_state', 'comment', 'change_date', 'changed_by']
    }
}

# =============== TEMPLATES NOTIFICATION UI ===============

UI_NOTIFICATIONS = {
    'success': {
        'icon': '✅',
        'color': 'success',
        'sticky': False,
        'duration': 3000
    },
    'warning': {
        'icon': '⚠️',
        'color': 'warning',
        'sticky': False,
        'duration': 5000
    },
    'error': {
        'icon': '❌',
        'color': 'danger',
        'sticky': True,
        'duration': 0
    },
    'info': {
        'icon': 'ℹ️',
        'color': 'info',
        'sticky': False,
        'duration': 4000
    }
}

# =============== MESSAGES STANDARDS ===============

STANDARD_MESSAGES = {
    # Messages de succès
    'success': {
        'document_uploaded': "Document {{document_name}} téléversé avec succès",
        'state_changed': "État changé vers '{{new_state}}'",
        'email_sent': "Email envoyé à {{recipient}}",
        'record_created': "{{record_type}} créé avec succès",
        'record_updated': "{{record_type}} mis à jour",
        'record_deleted': "{{record_type}} supprimé",
        'validation_passed': "Validation réussie",
        'operation_completed': "Opération terminée avec succès"
    },

    # Messages d'erreur
    'error': {
        'access_denied': "Droits insuffisants pour cette opération",
        'record_not_found': "Enregistrement introuvable",
        'invalid_data': "Données invalides : {{details}}",
        'constraint_violation': "Contrainte violée : {{constraint}}",
        'operation_failed': "Échec de l'opération : {{reason}}",
        'file_too_large': "Fichier trop volumineux (max: {{max_size}}MB)",
        'invalid_file_type': "Type de fichier non autorisé",
        'missing_required_field': "Champ requis manquant : {{field_name}}",
        'duplicate_record': "Enregistrement déjà existant"
    },

    # Messages d'avertissement
    'warning': {
        'document_expiring': "{{document_name}} expire dans {{days}} jour(s)",
        'approaching_deadline': "Échéance proche : {{deadline}}",
        'partial_completion': "Opération partiellement réussie",
        'data_incomplete': "Données incomplètes",
        'threshold_exceeded': "Seuil dépassé : {{threshold}}",
        'configuration_missing': "Configuration manquante"
    },

    # Messages d'information
    'info': {
        'no_records_found': "Aucun enregistrement trouvé",
        'processing_in_progress': "Traitement en cours...",
        'backup_completed': "Sauvegarde terminée",
        'maintenance_mode': "Mode maintenance activé",
        'feature_deprecated': "Cette fonctionnalité est dépréciée"
    }
}


# =============== FONCTIONS UTILITAIRES ===============

def format_message(message_key, message_type='info', **kwargs):
    """
    Formate un message standard avec les variables fournies.

    Args:
        message_key (str): Clé du message dans STANDARD_MESSAGES
        message_type (str): Type de message (success, error, warning, info)
        **kwargs: Variables à remplacer dans le message

    Returns:
        str: Message formaté
    """
    try:
        template = STANDARD_MESSAGES[message_type][message_key]
        return template.format(**kwargs)
    except KeyError:
        return f"Message non trouvé : {message_type}.{message_key}"


def create_notification_response(message_type, message, title=None, **kwargs):
    """
    Crée une réponse de notification standardisée.

    Args:
        message_type (str): Type de notification
        message (str): Message à afficher
        title (str): Titre optionnel
        **kwargs: Paramètres additionnels

    Returns:
        dict: Réponse de notification Odoo
    """
    config = UI_NOTIFICATIONS.get(message_type, UI_NOTIFICATIONS['info'])

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': title or message_type.title(),
            'message': f"{config['icon']} {message}",
            'type': config['color'],
            'sticky': config['sticky'],
            **kwargs
        }
    }


def prepare_email_context(template_key, **variables):
    """
    Prépare le contexte pour un template email.

    Args:
        template_key (str): Clé du template email
        **variables: Variables du template

    Returns:
        dict: Contexte préparé
    """
    template = EMAIL_TEMPLATES.get(template_key, {})

    context = {
        'template': template,
        'datetime': datetime.now(),
        'today': datetime.now().date(),
    }

    # Ajouter les variables fournies
    context.update(variables)

    # Ajouter les variables par défaut si manquantes
    if 'company_name' not in context:
        context['company_name'] = "Votre Société"

    return context


# =============== VALIDATION DES TEMPLATES ===============

def validate_template_variables(template_key, variables):
    """
    Valide que toutes les variables requises sont fournies.

    Args:
        template_key (str): Clé du template
        variables (dict): Variables fournies

    Returns:
        tuple: (is_valid, missing_variables)
    """
    template = EMAIL_TEMPLATES.get(template_key)
    if not template:
        return False, [f"Template '{template_key}' introuvable"]

    required_vars = template.get('variables', [])
    missing = [var for var in required_vars if var not in variables]

    return len(missing) == 0, missing
