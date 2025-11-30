#!/usr/bin/env python3
"""Script to update construction_contract module views"""
import xmlrpc.client

# Odoo connection parameters
url = 'http://localhost:8069'
db = 'blgtest'
username = 'admin'  # Change if needed
password = 'admin'  # Change if needed

try:
    # Authenticate
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    
    if not uid:
        print("Authentication failed! Check username/password")
        exit(1)
    
    print(f"Authenticated as user ID: {uid}")
    
    # Get models proxy
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
    
    # Find the module
    module_ids = models.execute_kw(db, uid, password,
        'ir.module.module', 'search',
        [[('name', '=', 'construction_contract')]])
    
    if not module_ids:
        print("Module construction_contract not found!")
        exit(1)
    
    print(f"Found module ID: {module_ids[0]}")
    
    # Upgrade the module
    print("Upgrading module...")
    models.execute_kw(db, uid, password,
        'ir.module.module', 'button_immediate_upgrade',
        [module_ids])
    
    print("Module upgraded successfully!")
    print("Views have been reloaded from XML files.")
    
except Exception as e:
    print(f"Error: {e}")
    exit(1)
