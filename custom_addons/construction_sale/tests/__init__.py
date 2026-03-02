# -*- coding: utf-8 -*-
# Existing tests
from . import test_construction_sale
from . import test_margin_calculation
from . import test_metre_calculation
from . import test_lot_sections
from . import test_security

# Shared fixtures
from . import common

# New test suites
from .unit import test_sale_order
from .unit import test_sale_order_line
from .unit import test_construction_lot
from .integration import test_create_from_spa
from .integration import test_search_products_spa
from .integration import test_quote_lifecycle
