# Copyright 2021 Creu Blanca
# Copyright 2024 BLG Groupe - Odoo 18 Migration
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Quoted Reply",
    "summary": """
        Reply to messages with quoted original content""",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Creu Blanca,Odoo Community Association (OCA),BLG Groupe",
    "website": "https://github.com/OCA/social",
    "depends": ["mail"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "mail_quoted_reply/static/src/core/**/*.js",
        ],
    },
}
