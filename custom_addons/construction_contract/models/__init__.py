# -*- coding: utf-8 -*-
"""
Models package
Contains all database models and business logic
"""

# Core models
from . import contract
from . import contract_template
from . import contract_signature
from . import contract_deliverable
from . import contract_document
from . import contract_page_validation
from . import urssaf_code

# Extensions to other modules
from . import chantier_extension
from . import res_partner_extension
from . import purchase_order
from . import lot_extension

# Mixins (if needed)
# from .mixins import legal_compliance_mixin
# from .mixins import pdf_generation_mixin
