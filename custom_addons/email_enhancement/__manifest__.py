{
    'name': 'Chatter Enhanced',
    'version': '18.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Extension du chatter avec interface Gmail-like',
    'description': """
        Extension du chatter Odoo
        ========================

        * Bouton Reply sur chaque message
        * Ouverture directe de la fenêtre de composition d'email
        * Interface améliorée similaire à Gmail/Outlook
        * Gestion avancée des réponses en thread
    """,
    'author': 'Ton nom',
    'depends': ['mail', 'web'],
    'data': [],
    'demo': [],
    'images': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'email_enhancement/static/src/js/chatter_enhanced.js',
            'email_enhancement/static/src/scss/chatter_enhanced.scss',
        ],
    },
}
