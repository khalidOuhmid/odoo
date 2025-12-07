# Document Validation Integration - Implementation Summary

## Overview

This document describes the implementation of Task 10: "Intégration Documents Sous-Traitant" from the BTPVision ERP specification. The implementation provides comprehensive document compliance checking for subcontractors before contract creation.

## Components Implemented

### 1. Validation Documents Service (Task 10.1)

**File:** `construction_contract/services/validation_documents_service.py`

A new service following SOLID principles that provides centralized document validation logic:

#### Key Methods:

- **`check_subcontractor_compliance(partner_id)`**
  - Validates all required documents (URSSAF, KBIS, Insurance)
  - Returns comprehensive compliance status with details
  - Skips validation for internal employees
  - Returns dict with: `is_compliant`, `missing_documents`, `expired_documents`, `expiring_documents`, `rejected_documents`, `details`

- **`get_expiring_documents(days_threshold=30)`**
  - Retrieves all subcontractors with documents expiring within threshold
  - Returns list of partners with expiring document details
  - Includes days until expiry for each document

- **`get_compliance_dashboard_data()`**
  - Generates comprehensive dashboard statistics
  - Categorizes partners: compliant, non-compliant, expiring soon
  - Provides counts for missing, expired, and rejected documents

- **`get_non_compliant_message(partner_id)`**
  - Generates detailed, user-friendly error messages
  - Lists all missing, expired, and rejected documents
  - Used for validation error display

### 2. Contract Validation Extension (Task 10.2)

**File:** `construction_contract/models/contract.py`

Enhanced the `_check_subcontractor_documents()` constraint method:

#### Changes:

- Replaced manual validation logic with validation service calls
- Provides detailed error messages listing specific document issues
- Maintains SIRET number validation
- Blocks contract creation if any required document is non-compliant

#### Error Message Format:

```
Le sous-traitant [Name] n'est pas conforme :

Documents manquants :
  • Attestation URSSAF
  • Extrait KBIS

Documents expirés :
  • Attestation d'assurance

Veuillez mettre à jour les documents avant de créer un contrat.
```

### 3. Expiring Documents Alert Cron (Task 10.3)

**Files:**
- `construction_contract/data/document_expiry_cron.xml`
- `construction_contract/models/contract.py` (method: `_cron_alert_expiring_documents()`)

Weekly cron job that monitors and alerts about expiring documents:

#### Features:

- **Runs weekly** to check documents expiring within 30 days
- **Notifies Responsable Administratif** via email with complete summary
- **Notifies Gestionnaires de Chantier** via activities on their specific sites
- **Creates activities** on impacted construction sites with 7-day deadline
- **Comprehensive logging** of all actions

#### Notification Recipients:

1. **Administrative Team (Email)**
   - Receives summary of all expiring documents
   - Grouped by subcontractor
   - Includes expiry dates and days remaining

2. **Site Managers (Activities)**
   - Receives activity on their construction sites
   - Only for subcontractors working on their sites
   - Activity type: Warning
   - Deadline: 7 days from alert

### 4. Compliance Dashboard (Task 10.4)

**File:** `construction_contract/views/compliance_dashboard_views.xml`

Comprehensive dashboard for monitoring subcontractor document compliance:

#### Views Implemented:

##### Kanban View
- Visual card-based layout
- Color-coded status badges (green/yellow/red)
- Document status for URSSAF, KBIS, Insurance
- Expiry dates displayed
- Quick action button: "Demander MAJ" (Request Update)
- Overall compliance indicator

##### List View
- Tabular format with all document statuses
- Color-coded rows (red=expired, yellow=expiring, green=compliant)
- Sortable columns
- Expiry dates visible

##### Search/Filter Options
- **By Status:**
  - Documents Expirés
  - Expire Bientôt (30j)
  - Conformes
  
- **By Document Type:**
  - URSSAF Expiré/Expire Bientôt
  - KBIS Expiré/Expire Bientôt
  - Assurance Expirée/Expire Bientôt

- **Group By:**
  - Statut URSSAF
  - Statut KBIS
  - Statut Assurance

#### Menu Location

New menu item: **"Conformité Documents"** under Construction Contract menu (sequence 50)

Default filters: Shows expired and expiring documents by default

## Integration Points

### With blg_contacts_extension

The implementation leverages existing document fields from `blg_contacts_extension`:
- `document_URSSAF`, `document_URSSAF_status`, `document_URSSAF_expiry`
- `document_KBIS`, `document_KBIS_status`, `document_KBIS_expiry`
- `document_insurance`, `document_insurance_status`, `document_insurance_expiry`
- `document_*_manual_status` fields for validation workflow

### With construction_base

- Integrates with `construction.chantier` model
- Creates activities on construction sites
- Notifies site managers (gestionnaires)

### With construction_contract

- Validates documents before contract creation
- Blocks non-compliant contracts with detailed messages
- Provides compliance status in contract workflow

## Requirements Fulfilled

### Requirement 10.1
✅ Contract creation blocked if documents expired or missing
✅ Explicit error messages with document status details

### Requirement 10.2
✅ Detailed status per document in error message
✅ Clear indication of what needs to be updated

### Requirement 10.3
✅ Weekly cron checking documents expiring in 30 days
✅ Notifications to Responsable Administratif
✅ Notifications to Gestionnaires for their sites
✅ Activities created on impacted construction sites

### Requirement 10.4
✅ Compliance dashboard with kanban view
✅ Filters by document type and status
✅ Quick actions: request document update
✅ View details functionality

### Requirement 10.5
✅ Notifications when documents expire (via cron)
✅ Targeted notifications to relevant users

## Usage Examples

### For Gestionnaire de Chantier

1. **Creating a Contract:**
   - System automatically validates subcontractor documents
   - If non-compliant, receives detailed error message
   - Can view compliance dashboard to check status

2. **Receiving Alerts:**
   - Gets activity on construction site when documents expiring
   - Activity includes list of expiring documents
   - 7-day deadline to follow up

### For Responsable Administratif

1. **Monitoring Compliance:**
   - Access "Conformité Documents" menu
   - View all subcontractors with document issues
   - Filter by document type or status
   - Send update requests directly from dashboard

2. **Weekly Alerts:**
   - Receives email summary every week
   - Lists all subcontractors with expiring documents
   - Includes expiry dates and days remaining

## Technical Notes

### Service Pattern

The validation service follows the SOLID principle of Single Responsibility:
- Centralized validation logic
- Reusable across different contexts
- Easy to test and maintain
- No direct UI dependencies

### Error Handling

- Graceful handling of missing fields
- Skips validation for internal employees
- Comprehensive logging for debugging
- User-friendly error messages

### Performance Considerations

- Cron runs weekly (not daily) to reduce load
- Efficient queries using domain filters
- Computed fields cached where appropriate
- Batch processing of notifications

## Future Enhancements

Possible improvements for future iterations:

1. **Document Upload Portal**
   - Direct link in notifications to upload documents
   - Self-service document management for subcontractors

2. **Automated Reminders**
   - Escalating reminders at 60, 30, 15, 7 days before expiry
   - Configurable reminder schedules

3. **Document Validation Workflow**
   - Approval workflow for uploaded documents
   - Rejection with reasons
   - Version history

4. **Analytics Dashboard**
   - Compliance trends over time
   - Most common expired documents
   - Average response time to document requests

## Testing Recommendations

### Unit Tests
- Test `check_subcontractor_compliance()` with various document states
- Test `get_expiring_documents()` with different thresholds
- Test error message generation

### Integration Tests
- Test contract creation with non-compliant subcontractor
- Test cron execution and notification sending
- Test dashboard filters and search

### Manual Testing
1. Create subcontractor with expired URSSAF
2. Try to create contract → should block with message
3. Update document to valid
4. Create contract → should succeed
5. Set document to expire in 20 days
6. Run cron manually → should send alerts
7. Check compliance dashboard → should show in "Expiring Soon"

## Conclusion

The Document Validation Integration provides a comprehensive solution for ensuring subcontractor compliance before contract creation. It combines proactive monitoring (cron alerts), reactive validation (contract creation blocking), and visibility (compliance dashboard) to maintain document compliance across all construction projects.
