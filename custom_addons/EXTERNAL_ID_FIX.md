# External ID Fix for document.archive Model

## Issue Fixed ✅

**Error**: `No matching record found for external id 'blggroupe_contact_extension.model_document_archive'`

**Root Cause**: Incorrect external ID format for model references in security file.

## Understanding Odoo External ID Generation

### Automatic Model External IDs
When Odoo loads a model, it automatically creates external IDs following this pattern:
- Model: `'document.archive'` → External ID: `model_document_archive`
- Model: `'res.partner'` → External ID: `model_res_partner` (in base module)
- Model: `'lot.category'` → External ID: `model_lot_category` (in defining module)

### Module-Prefixed vs Auto-Generated IDs
- **Auto-generated**: `model_document_archive` (for models in current module)
- **Module-prefixed**: `base.model_res_partner` (for models in other modules)
- **Module-prefixed**: `blggroupe_lots.model_lot_category` (for models in other modules)

## Fix Applied ✅

**File**: `blggroupe_contact_extension/security/ir.model.access.csv`

### Before (Incorrect):
```csv
access_document_archive_user,access.document.archive.user,blggroupe_contact_extension.model_document_archive,base.group_user,1,0,0,0
```

### After (Correct):
```csv
access_document_archive_user,access.document.archive.user,model_document_archive,base.group_user,1,0,0,0
```

## Final Security File Configuration ✅

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_res_partner_doc_conductrice,access.res.partner.doc.conductrice,base.model_res_partner,blggroupe_contact_extension.group_conductrice_travaux,1,1,0,0
access_res_partner_doc_directeur,access.res.partner.doc.directeur,base.model_res_partner,blggroupe_contact_extension.group_directeur_general,1,1,1,0
access_document_archive_user,access.document.archive.user,model_document_archive,base.group_user,1,0,0,0
access_document_archive_conductrice,access.document.archive.conductrice,model_document_archive,blggroupe_contact_extension.group_conductrice_travaux,1,1,1,0
access_document_archive_directeur,access.document.archive.directeur,model_document_archive,blggroupe_contact_extension.group_directeur_general,1,1,1,1
access_document_archive_admin,access.document.archive.admin,model_document_archive,base.group_system,1,1,1,1
access_lot_category_extension,access.lot.category.extension,blggroupe_lots.model_lot_category,blggroupe_contact_extension.group_conductrice_travaux,1,0,0,0
```

## Validation Results ✅

- ✅ All validation tests passing
- ✅ Correct external ID format used
- ✅ All dependencies properly configured
- ✅ Security configuration valid

## Status: Ready for Installation 🚀

The external ID issue has been resolved. The module should now install successfully.
