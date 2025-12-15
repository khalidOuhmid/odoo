
import odoo
from odoo import api, SUPERUSER_ID

def check_website_payment(env):
    # Check module state
    module = env['ir.module.module'].search([('name', '=', 'website_payment')])
    print(f"Module website_payment state: {module.state if module else 'Not found'}")

    # Check asset
    asset = env['ir.asset'].search([('path', '=', 'website_payment/static/src/snippets/s_donation/000.js')])
    print(f"Asset website_payment.s_donation_000_js found: {len(asset)}")
    if asset:
        print(f"Asset active: {asset.active}")

if __name__ == "__main__":
    try:
        registry = odoo.registry(odoo.tools.config['db_name'])
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            check_website_payment(env)
    except Exception as e:
        print(f"Error: {e}")
