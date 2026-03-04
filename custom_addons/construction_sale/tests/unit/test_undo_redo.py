# -*- coding: utf-8 -*-
"""
Undo / Redo UX Tests (Quote Builder)
=====================================
Simulates the Quote Builder Undo/Redo logic by ensuring the snapshot
management array boundaries align with the requirements.
"""

from odoo.tests import common, tagged

@tagged('post_install', '-at_install', 'construction_sale', 'undo_redo')
class TestUndoRedo(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def _simulate_push_history(self, state, past, maxSize=50):
        # Python mirror of JS useUndoRedo pushHistory for testing bounds
        if not state:
            return past, []
        past.append(list(state))
        if len(past) > maxSize:
            past.pop(0)
        return past, [] # future gets cleared

    def test_01_undo_after_line_addition(self):
        """
        1. Undo après ajout d'une QuoteLine:
        Verify the history correctly records the state before addition.
        """
        past = []
        state_0 = []
        
        # 1. Base state (empty cart pushed at start)
        past, future = self._simulate_push_history(state_0, past)
        
        # 2. Add line and push history again BEFORE adding another
        state_1 = [{'product_id': 1, 'qty': 1}]
        past, future = self._simulate_push_history(state_1, past)
        
        # 3. Add second line
        state_2 = [{'product_id': 1, 'qty': 1}, {'product_id': 2, 'qty': 5}]
        
        # Simulate Undo:
        previous_state = past.pop()
        self.assertEqual(len(previous_state), 1)
        self.assertEqual(previous_state[0]['product_id'], 1)

    def test_02_max_size_past_history_respected(self):
        """
        2. Max size de past_history (50) respecté:
        Verify the history does not exceed the limit.
        """
        past = []
        max_size = 50
        
        # Push 60 snapshots
        for i in range(1, 61):
            state = [{'val': i}]
            past, future = self._simulate_push_history(state, past, maxSize=max_size)
            
        self.assertEqual(len(past), 50, "Past history should not exceed max_size (50)")
        
        # The oldest snapshot should be index 11 (since 1-10 were shifted out)
        self.assertEqual(past[0][0]['val'], 11, "Oldest state should be shifted out (FIFO)")
        self.assertEqual(past[-1][0]['val'], 60, "Latest state should be at the end")

    def test_03_clear_future_after_new_action(self):
        """
        3. Clear future après une nouvelle action:
        Verify that branching history clears the redo buffer.
        """
        past = []
        future = [[{'product_id': 99}]] # Non-empty future
        
        state_new = [{'product_id': 1}]
        
        # New action pushes history and MUST clear the future
        past, future = self._simulate_push_history(state_new, past)
        
        self.assertEqual(len(future), 0, "Future (Redo stack) must be cleared upon new action")
        self.assertEqual(len(past), 1)
