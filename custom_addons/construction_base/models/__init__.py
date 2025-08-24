# -*- coding: utf-8 -*-

# Modèles de base (pas de dépendances)
from . import chapter
from . import stage
from . import tag
from . import visit
from . import document
from . import res_company
from . import res_partner
from . import sale_order
from . import sale_order_line_extension
from . import purchase_order
from . import purchase_order_line
from . import lot_template
from . import invoice_type
from . import planning
from . import subcontractor_contract
from . import services
from . import mail_thread

# Modèles avec dépendances (après les modèles de base)
from . import chantier
from . import lot_extension
