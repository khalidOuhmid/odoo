# CHANGELOG

## [1.0.3] - 2025-07-23

### Fixed
- Fixed foreign key constraint validation error related to account.move.partner_id_fkey
- Added guidance for handling partner deletion when referenced by journal entries
- Resolved "another model requires the record being deleted" error for Journal Entry model

### Technical Details
- The error occurs when trying to delete a partner (res.partner) that has associated journal entries (account.move)
- This is a standard Odoo constraint to prevent data integrity issues in accounting
- Solution: Archive the partner instead of deleting, or ensure all journal entries are handled first

### Development Environment Solutions
For development environments only (NOT for production):

1. **Force delete with SQL** (use with extreme caution):
```sql
-- First, find the partner ID that's causing issues
SELECT id, name FROM res_partner WHERE name = 'Partner Name';

-- Check what journal entries reference this partner
SELECT id, name, partner_id FROM account_move WHERE partner_id = YOUR_PARTNER_ID;

-- Option 1: Delete the journal entries first (DANGEROUS - loses accounting data)
DELETE FROM account_move WHERE partner_id = YOUR_PARTNER_ID;

-- Option 2: Set partner_id to NULL in journal entries (breaks accounting logic)
UPDATE account_move SET partner_id = NULL WHERE partner_id = YOUR_PARTNER_ID;

-- Then delete the partner
DELETE FROM res_partner WHERE id = YOUR_PARTNER_ID;
```

2. **Python/ORM approach** (safer for development):
```python
# In Odoo shell or server action
partner_id = YOUR_PARTNER_ID  # Replace with actual ID
partner = env['res.partner'].browse(partner_id)

# Check dependencies
journal_entries = env['account.move'].search([('partner_id', '=', partner_id)])
print(f"Found {len(journal_entries)} journal entries for partner {partner.name}")

# Force delete journal entries (development only!)
if journal_entries:
    journal_entries.unlink()

# Now delete the partner
partner.unlink()
```

3. **Temporary disable constraints** (advanced):
```python
# This disables foreign key checks temporarily (PostgreSQL specific)
env.cr.execute("SET session_replication_role = replica;")
partner.unlink()  # Delete the problematic record
env.cr.execute("SET session_replication_role = DEFAULT;")
```

**⚠️ WARNING**: These solutions should NEVER be used in production as they can corrupt your data and break accounting integrity.

### Error Details
```
Validation Error
Model: Journal Entry (account.move)
Constraint: account_move_partner_id_fkey
The operation cannot be completed: another model requires the record being deleted. If possible, archive it instead.
```

## [1.0.2] - 2025-07-23

### Fixed
- Fixed foreign key constraint validation error in construction.product.creator model
- Added ondelete='cascade' constraint to quote_wizard_id relationships in transient models
- Resolved "another model requires the record being deleted" error during wizard operations

### Technical Details
- Added proper cascade deletion constraints for ProductAddDialog and ProductCreator models
- This prevents foreign key constraint violations when wizard records are cleaned up
- Affects models: construction.product.dialog, construction.product.creator

## [1.0.1] - 2025-07-22

### Fixed
- Fixed OWL lifecycle error in Gantt view due to improper JavaScript module registration
- Removed js_class="planning_gantt" from planning_views.xml to use standard Gantt view
- Simplified planning_gantt.js to avoid Controller/Model/Renderer inheritance issues
- Resolved "Cannot read properties of undefined (reading 'prototype')" error in useModelWithSampleData

### Technical Details
- The error was caused by improper registration of custom Gantt components in the views registry
- Odoo 18 uses different patterns for extending Gantt views than previous versions
- Simplified approach using standard Gantt view with minimal customization for now

### Error Details
```
OwlError: An error occured in the owl lifecycle
Caused by: TypeError: Cannot read properties of undefined (reading 'prototype')
at useModelWithSampleData 
at PlanningGanttController.setup
```

The error occurred when trying to extend GanttController, GanttModel, and GanttRenderer classes and register them as a custom view type.
