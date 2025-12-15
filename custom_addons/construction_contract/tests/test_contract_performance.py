# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from .common import ContractTestMixin
import time
import logging

_logger = logging.getLogger(__name__)

@tagged('post_install', '-at_install', 'construction_contract_perf')
class TestContractPerformance(TransactionCase, ContractTestMixin):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpContractData()

    def test_perf_01_pdf_generation_time(self):
        """SC_PERF_01 – Temps de génération PDF"""
        start_time = time.time()
        
        # Generate PDF
        try:
            self.contract.action_generate_pdf()
        except ImportError:
            return # Skip if WeasyPrint missing
            
        duration = time.time() - start_time
        _logger.info(f"PDF Generation took {duration:.2f}s")
        
        # Assert reasonable time (e.g. < 3s, but give leeway for CI)
        self.assertLess(duration, 5.0, "PDF Generation took too long (> 5s)")
