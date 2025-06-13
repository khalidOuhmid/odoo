# -*- coding: utf-8 -*-

# Import basic models first (no dependencies)
# from . import mail_thread
# from . import res_partner
# from . import chantier_tag 
# from . import lot_type

# Import workflow models
from . import chapter
from . import stage

# Import main model (depends on many above, and is a dependency for models below)
from . import chantier

# Import relationship models (dependent on chantier)
# from . import document
# from . import visite

# Import dependent models (dependent on chantier and/or lot_type)
# from . import chantier_lot

