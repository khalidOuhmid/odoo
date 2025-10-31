# -*- coding: utf-8 -*-

from . import chantier
from . import chapter
from . import document
from . import invoice_type
from . import invoice_type_backup
from . import invoice_type_clean
from . import lot_extension
from . import lot_template
from . import mail_thread
from . import planning
from . import purchase_order_line
from . import purchase_order
from . import res_company
from . import res_partner
from . import sale_order_line_extension
from . import sale_order
from . import stage
from . import subcontractor_contract
from . import tag
from . import visit

# Services
from . import services

# New modular models - temporarily disabled due to AbstractModel issues
# from . import contract_factory
# from . import contract_builder
# from . import document_generator
# from . import contract_validator
# from . import multi_lot_handler
# from . import contract_orchestrator