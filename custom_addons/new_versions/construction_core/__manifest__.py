# __manifest__.py
{
    'name': 'Construction Core',
    'version': '18.0.1.0.0',
    'category': 'Construction',
    'summary': 'Core functionality for construction management modules',
    'description': """
        Core module providing shared functionality for construction management:
        - Document management mixins
        - Base services and utilities
        - Common business logic
        - Notification system
    """,
    'author': 'BLG GROUPE',
    'website': 'https://www.votre-site.com',
    'depends': ['base', 'mail', 'portal'],
    'data': [
        'data/email_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
