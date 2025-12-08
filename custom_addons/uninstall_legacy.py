# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)

def run_uninstall(env):
    print("STARTING HARD UNINSTALL (SQL MODE)")
    modules_to_remove = ['construction_base', 'blg_contacts_extension', 'construction_lots']
    
    # 1. Check existence
    env.cr.execute("SELECT name, state FROM ir_module_module WHERE name IN %s AND state != 'uninstalled'", (tuple(modules_to_remove),))
    rows = env.cr.fetchall()
    
    if not rows:
        print("No legacy modules found in installed state.")
        return

    print(f"Found modules to force-uninstall: {rows}")
    
    # 2. Force State via SQL
    env.cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE name IN %s", (tuple(modules_to_remove),))
    env.cr.commit()
    print("SQL UPDATE SUCCESSFUL. Registry should be clean on next restart.")

if __name__ == '__main__':
    if 'env' in locals():
        run_uninstall(env)
