# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Import prioritaire: nouveau wizard requis par les vues
from . import create_purchase_line_wizard

# Imports des autres wizards (robuste aux erreurs pour ne pas bloquer le chargement)
try:
    from . import force_stage_wizard
    from . import lot_subquote_wizard
    from . import lot_subcontractor_assign_wizard
    from . import lot_document_wizard
    from . import create_task_planning
    from . import quote_selection_wizard
    from . import document_upload_wizard
    from . import invoice_schedule_wizard
    from . import contract_generation_wizard
    from . import invoice_setup_wizard
    from . import lot_select_wizard
    from . import multi_lot_contract_wizard
except Exception as e:
    _logger.error("Erreur lors de l'import des wizards complémentaires: %s", e)