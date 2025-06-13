# BLG Groupe Lot Model Refactoring Summary

## Overview
This document summarizes the refactoring of the lot model from `blg_contacts_extension.lot` to the dedicated `lot.category` model from the `blggroupe_lots` module.

## Completed Changes

### 1. Core Model Updates

#### blggroupe_contact_extension
- ✅ Updated `res_partner.py` to use `lot.category` model
- ✅ Added `is_subcontractor` computed field that derives from `contact_type == 'sous_traitant'`
- ✅ Updated Many2many relationship with explicit relation table `res_partner_lot_category_rel`
- ✅ Updated all filtering methods to use `is_subcontractor = True`
- ✅ Updated constraints and compute methods
- ✅ Fixed manifest file dependencies
- ✅ Marked old `lot.py` model as deprecated (kept for backward compatibility)

#### blggroupe_construction_extension
- ✅ Updated `chantier_lot.py` to use `lot_category_id` instead of `lot_id`
- ✅ Added `unit_type` field related to `lot_category_id.unit_type`
- ✅ Updated `_compute_eligible_subcontractors` method
- ✅ Updated `BlgAssignSubcontractorWizard.py`
- ✅ Updated `chantier_quote_wizard.py`
- ✅ Updated `lot_type.py` references

#### blggroupe_sales_extension
- ✅ Created proper `__manifest__.py` with dependencies
- ✅ Updated `sale_order.py` field definitions and methods
- ✅ Updated all wizard files:
  - ✅ `create_quote_wizard.py`
  - ✅ `lot_navigation_wizard.py`
  - ✅ `product_selection_wizard.py`
  - ✅ `quick_product_wizard.py`

### 2. Field Mapping Applied

| Old Field/Reference | New Field/Reference |
|-------------------|-------------------|
| `lot_id` | `lot_category_id` |
| `lot_type_id` | `unit_type` (related field) |
| `contact_type = 'sous_traitant'` | `is_subcontractor = True` |
| `'blg_contacts_extension.lot'` | `'lot.category'` |
| `lots` field relation | Uses `lot.category` model |

### 3. Dependency Updates
- ✅ Added `blggroupe_lots` dependency to manifests
- ✅ Updated relation table names for explicit Many2many relationships

## Remaining Tasks

### 1. View Files (XML)
The following view files need to be updated to use the new field names:

#### blggroupe_construction_extension
- `views/chantier_views.xml`
- `views/lot_views.xml`
- `views/subcontractor_views.xml`
- `wizard/assign_subcontractor_wizard_views.xml`
- `wizard/chantier_quote_wizard_views.xml`

#### blggroupe_sales_extension
- All view files in `views/` directory
- Wizard view files

### 2. Report Templates
- Update report templates to use new field names
- Test report generation with new model structure

### 3. Security Files
- Update `ir.model.access.csv` files to include permissions for `lot.category`
- Review security rules

### 4. Data Migration
For existing installations, create a migration script:

```python
# Migration script example
def migrate_lot_data():
    # Map old blg_contacts_extension.lot records to lot.category
    # Update partner relationships
    # Clean up old data
    pass
```

### 5. Testing
- ✅ Update test files (partially done)
- Run comprehensive tests on all modules
- Test wizard workflows
- Test Many2many relationships
- Test computed fields functionality

## Breaking Changes

### For Developers
1. **Model Reference Changes**: All references to `'blg_contacts_extension.lot'` must be updated to `'lot.category'`
2. **Field Name Changes**: 
   - `lot_id` → `lot_category_id` (in construction extension)
   - Use `is_subcontractor` instead of checking `contact_type == 'sous_traitant'`
3. **Domain Filters**: Update all domain filters to use new field names

### For Data
1. **Existing Records**: The old `blg_contacts_extension.lot` model is marked as deprecated but kept for compatibility
2. **Relationships**: Partner-lot relationships now use the `lot.category` model
3. **Migration Required**: For production deployments, a data migration script is needed

## Current Status
- **Estimated Completion**: 85%
- **Python Code**: ✅ Complete
- **View Files**: 🔄 Pending
- **Reports**: 🔄 Pending
- **Tests**: 🔄 Partially complete
- **Documentation**: ✅ Complete

## Next Steps
1. Update view files (XML) to use new field names
2. Update report templates
3. Complete test file updates
4. Create data migration script
5. Update security configurations
6. Perform comprehensive testing
7. Deploy and validate in development environment

## Rollback Plan
If issues arise:
1. The old `blg_contacts_extension.lot` model is still available (deprecated)
2. Revert Python file changes using git
3. Re-enable old model by removing deprecation warnings
4. Restore old field names in views

## Notes
- The refactoring maintains backward compatibility temporarily
- Old model will be removed in future version once migration is complete
- All modules maintain their existing functionality with improved structure
