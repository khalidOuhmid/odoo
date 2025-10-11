{
    'name': 'Email Enhancement',
    'version': '18.0.1.0.0',
    'category': 'Mail',
    'summary': 'Amélioration de l\'interface du chatter pour les emails',
    'description': """
        Module d'amélioration de l'interface du chatter Odoo :
        - Ouverture directe du full composer lors du clic sur "Envoyer un message"
        - Ajout d'un bouton "Reply" sur les messages pour une vraie réponse
        - Amélioration de l'expérience utilisateur pour les emails
    """,
    'author': 'Odoo Developer',
    'website': 'https://www.odoo.com',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'email_enhancement/static/src/js/chatter_patch.js',
            'email_enhancement/static/src/js/message_actions_patch.js',
            'email_enhancement/static/src/scss/chatter_enhanced.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
