# BLG Contacts Extension - Subcontractor Management

## Overview

The BLG Contacts Extension module provides comprehensive subcontractor document management and integration with construction projects for Odoo 18. This module has been completely refactored following SOLID principles and clean architecture patterns.

## Features

### 🔄 Document Lifecycle Management
- **Automated Status Tracking**: Documents automatically transition between states (valid, expiring, expired, missing, rejected)
- **Expiration Monitoring**: 30-day advance warnings for expiring documents
- **Version Control**: Complete archive system for document history
- **Validation Workflow**: Manual validation with approval/rejection capabilities

### 📧 Intelligent Notifications
- **Automated Email Alerts**: Expiry notifications, rejection notices, and document requests
- **Frequency Control**: Smart notification throttling to prevent spam
- **Secure Upload Links**: Time-limited tokens for secure document uploads
- **Portal Integration**: Subcontractor portal for document submission

### 🏗️ Construction Integration
- **Lot Management**: Integration with standardized construction lots
- **Project Assignment**: Automatic subcontractor matching based on specializations
- **Availability Tracking**: Real-time availability for project assignments
- **Performance Metrics**: Document compliance tracking per project

### 🔒 Security & Compliance
- **Role-Based Access**: Granular permissions for different user types
- **Audit Trail**: Complete logging of document changes and access
- **Data Retention**: Configurable archive retention policies
- **File Validation**: PDF-only uploads with size restrictions

## Architecture

### SOLID Principles Implementation

#### Single Responsibility Principle (SRP)
- **DocumentFieldsMixin**: Handles field definitions only
- **DocumentValidationMixin**: Manages validation logic only  
- **DocumentNotificationMixin**: Handles notifications only
- **SubcontractorMixin**: Manages subcontractor-specific features

#### Open/Closed Principle (OCP)
- **Extensible Configuration**: New document types can be added via `document_config.py`
- **Plugin Architecture**: New mixins can be added without modifying existing code
- **Service Pattern**: Services can be extended or replaced independently

#### Liskov Substitution Principle (LSP)
- **Abstract Mixins**: All mixins follow consistent interfaces
- **Service Contracts**: Services implement predictable interfaces

#### Interface Segregation Principle (ISP)
- **Focused Mixins**: Each mixin provides specific functionality
- **Service Separation**: Document, notification, and archive services are separate

#### Dependency Inversion Principle (DIP)
- **Service Layer**: Business logic depends on service abstractions
- **Configuration-Driven**: Implementation details configured externally

### Clean Architecture Layers

```
┌─────────────────────────────────────────┐
│              Presentation               │
│          (Views, Controllers)           │
├─────────────────────────────────────────┤
│             Application                 │
│        (Services, Use Cases)            │
├─────────────────────────────────────────┤
│               Domain                    │
│         (Models, Mixins)                │
├─────────────────────────────────────────┤
│            Infrastructure               │
│      (Database, Email, File System)     │
└─────────────────────────────────────────┘
```

## Technical Stack

### Core Technologies
- **Odoo 18**: Base framework
- **Python 3.8+**: Programming language
- **PostgreSQL**: Database
- **Bootstrap 5**: Frontend framework

### Design Patterns
- **Mixin Pattern**: Composable functionality
- **Service Layer**: Business logic separation
- **Observer Pattern**: Event-driven notifications
- **Strategy Pattern**: Configurable document types

## Installation

### Prerequisites
- Odoo 18.0 or higher
- `construction_lots` module installed
- Python dependencies: `python-dateutil`

### Installation Steps

1. **Clone the Module**
   ```bash
   cd /path/to/odoo/addons
   git clone [repository-url] blg_contacts_extension
   ```

2. **Install Dependencies**
   ```bash
   pip install python-dateutil
   ```

3. **Update Module List**
   - Go to Apps → Update Apps List

4. **Install Module**
   - Search for "BLG Contacts Extension"
   - Click Install

### Configuration

#### 1. System Parameters
Configure in Settings → Technical → System Parameters:

```
blg_contacts_extension.expiry_warning_days = 30
blg_contacts_extension.max_file_size_mb = 10
blg_contacts_extension.token_validity_days = 7
blg_contacts_extension.notification_batch_size = 100
blg_contacts_extension.archive_retention_days = 365
```

#### 2. Email Templates
Templates are automatically created during installation:
- Document Expired Notification
- Document Expiring Soon Notification  
- Document Rejected Notification
- Missing Documents Request

#### 3. Cron Jobs
Configure automated tasks:
- **Document Expiry Check**: Daily at 8:00 AM
- **Archive Cleanup**: Weekly on Sundays

## Usage Guide

### For Administrators

#### Managing Document Types
Document types are configured in `models/document_config.py`:

```python
DOCUMENT_TYPES = {
    'new_document': {
        'key': 'new_document',
        'display_name': "New Document Type",
        'display_name_fr': "Nouveau Type de Document",
        'content_field': 'document_new_document',
        'filename_field': 'document_new_document_filename',
        'expiry_field': 'document_new_document_expiry',  # Optional
        'status_field': 'document_new_document_status',
        'manual_status_field': 'document_new_document_manual_status',
        'has_expiry': True,
        'required': True,
        'sort_order': 6,
    }
}
```

#### User Permissions
Configure user groups:
- **System Administrator**: Full access
- **Construction Manager**: Document validation and project management
- **General Director**: All permissions including archive restoration

### For Construction Managers

#### Document Validation Workflow
1. **Review Uploaded Documents**
   - Navigate to Contacts → Subcontractors
   - Open subcontractor record
   - Go to Documents tab

2. **Validate Documents**
   - Click "Validate" for approved documents
   - Click "Reject" with reason for non-compliant documents

3. **Send Notifications**
   - Use "Send Missing Documents Request" for incomplete submissions
   - System automatically sends expiry warnings

#### Project Assignment
1. **View Available Subcontractors**
   - Open construction project
   - Use "Available Subcontractors" computed field

2. **Filter by Specialization**
   - Filter subcontractors by lot/trade
   - Check document compliance status

### For Subcontractors (Portal)

#### Document Upload Process
1. **Receive Email Notification**
   - Click secure upload link in email

2. **Upload Documents**
   - Use web portal interface
   - Upload PDF files only
   - Set expiry dates where required

3. **Track Status**
   - Receive email confirmations
   - Check document status in portal

## API Reference

### Services

#### DocumentService
```python
# Validate document
result = self.env['document.service'].validate_document(
    partner_id=123,
    doc_type_key='identity_card',
    reset=False
)

# Reject document  
result = self.env['document.service'].reject_document(
    partner_id=123,
    doc_type_key='identity_card',
    rejection_reason='Invalid format'
)

# Send missing documents request
result = self.env['document.service'].send_missing_documents_request(
    partner_id=123
)
```

#### ArchiveService
```python
# Archive document version
archive = self.env['archive.service'].archive_document_version(
    partner_id=123,
    doc_type='identity_card',
    content=binary_content,
    filename='document.pdf',
    action_type='replacement'
)

# Cleanup old archives
stats = self.env['archive.service'].cleanup_old_archives(
    retention_days=365
)
```

### Models

#### Enhanced Partner Model
```python
# Get document summary
partner = self.env['res.partner'].browse(123)
summary = partner.get_document_summary()

# Check compliance status  
status = partner.get_document_compliance_status()

# Get related construction projects
chantiers = partner.get_related_chantiers()
```

## Customization

### Adding New Document Types

1. **Update Configuration**
   ```python
   # In models/document_config.py
   DOCUMENT_TYPES['custom_doc'] = {
       'key': 'custom_doc',
       'display_name': "Custom Document",
       # ... other configuration
   }
   ```

2. **Update Security**
   ```xml
   <!-- In security/ir.model.access.csv -->
   <!-- Add access rules for new fields -->
   ```

3. **Update Views**
   ```xml
   <!-- In views/res_partner_views.xml -->
   <!-- Add UI elements for new document type -->
   ```

### Extending Notification Logic

```python
class CustomNotificationMixin(models.AbstractModel):
    _name = 'custom.notification.mixin'
    _inherit = 'document.notification.mixin'
    
    def send_custom_notification(self, **kwargs):
        # Custom notification logic
        pass
```

## Troubleshooting

### Common Issues

#### 1. Document Fields Not Appearing
**Symptom**: Document fields missing in partner form
**Solution**: 
```python
# Restart Odoo server to reinitialize dynamic fields
# Or upgrade module to trigger field recreation
```

#### 2. Email Notifications Not Sending
**Symptom**: No notification emails received
**Checks**:
- Verify email server configuration
- Check partner email addresses
- Confirm notification settings not disabled
- Review email template configuration

#### 3. Archive Service Errors
**Symptom**: Document archiving fails
**Solution**:
```python
# Check database permissions
# Verify archive service registration
# Review error logs for specific issues
```

### Performance Optimization

#### 1. Database Indexing
```sql
-- Recommended indexes for performance
CREATE INDEX idx_partner_contact_type ON res_partner(contact_type);
CREATE INDEX idx_document_archive_date ON document_archive(archive_date);
CREATE INDEX idx_document_archive_partner ON document_archive(partner_id);
```

#### 2. Batch Processing
```python
# Process notifications in batches
batch_size = self.env['ir.config_parameter'].sudo().get_param(
    'blg_contacts_extension.notification_batch_size', 100
)
```

## Migration Guide

### From Previous Version

#### 1. Data Migration
The module includes automatic data migration:
- Lot relationships migrated to standardized model
- Document archives preserved
- Partner data maintained

#### 2. Custom Code Updates
If you have custom code:
```python
# Old way
partner.lots  # blg_contacts_extension.lot

# New way  
partner.lot_ids  # lot (from construction_lots)
```

## Contributing

### Development Setup
1. Fork the repository
2. Create feature branch
3. Follow coding standards (PEP 8, Odoo guidelines)
4. Add tests for new functionality
5. Submit pull request

### Code Style
- Use English for all docstrings and comments
- Follow SOLID principles
- Maintain clean architecture separation
- Add comprehensive logging

## Support

### Documentation
- Technical documentation: `/docs`
- API reference: This README
- Video tutorials: [Link to videos]

### Issue Reporting
Create issues on the repository with:
- Odoo version
- Module version  
- Steps to reproduce
- Error logs
- Expected vs actual behavior

## License

This module is licensed under LGPL-3. See LICENSE file for details.

## Changelog

### Version 18.0.1.0.0
- Complete refactoring with SOLID principles
- Clean architecture implementation
- Enhanced error handling and logging
- Improved performance and scalability
- Integration with construction_lots module
- Comprehensive test coverage
- Updated UI/UX following Odoo 18 guidelines 