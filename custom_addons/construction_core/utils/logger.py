# -*- coding: utf-8 -*-
"""
Production-grade structured logger for Construction modules.

Rules enforced:
- %s lazy formatting only — never f-strings in log calls (avoids eager string
  interpolation when the log level is filtered out).
- Consistent [BLG][CATEGORY][EVENT] prefix makes grepping Odoo.sh logs trivial:
    grep '\[BLG\]\[STAGE\]'   → all stage transitions
    grep '\[BLG\]\[FINANCE\]' → all financial alerts
    grep '\[BLG\]\[ERROR\]'   → all caught business errors

Usage
-----
    from odoo.addons.construction_core.utils.logger import get_logger

    _logger = get_logger(__name__)

    # Standard levels (pass-through to stdlib logger)
    _logger.info("Message %s", value)
    _logger.warning("Message %s", value)
    _logger.error("Message %s", value)

    # Semantic helpers (structured context auto-injected)
    _logger.stage_transition(chantier, 'T75', 'LR')
    _logger.stage_transition(chantier, 'REC', 'VT', forced=True)
    _logger.financial_alert(lot, "MARGE NEGATIVE", -500.0, percent=-5.2)
    _logger.overbilling(lot, 115.0)
    _logger.compliance_check(partner, "URSSAF", passed=False)
    _logger.business_error(chantier, "action_move_to_next_stage", exc)
    _logger.email_event("CHANTIER_CREATED", "name=Tour Eiffel id=42")
"""

import logging


class ConstructionLogger:
    """
    Thin wrapper over stdlib Logger.

    Provides structured semantic methods for common business events while
    enforcing %s lazy formatting on all log calls.
    """

    PREFIX = "BLG"

    def __init__(self, name: str):
        self._log = logging.getLogger(name)

    # ------------------------------------------------------------------
    # Standard levels — identical API to stdlib, %s formatting enforced
    # ------------------------------------------------------------------

    def debug(self, msg, *args, **kwargs):
        self._log.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._log.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._log.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        """Log at ERROR level and include the current exception traceback."""
        self._log.exception(msg, *args, **kwargs)

    # ------------------------------------------------------------------
    # Semantic business-event helpers
    # ------------------------------------------------------------------

    def stage_transition(self, record, from_code, to_code, forced=False):
        """
        Log a stage transition.

        :param record:    the chantier recordset (used for id)
        :param from_code: source stage code  (str)
        :param to_code:   target stage code  (str)
        :param forced:    True if bypass_stage_validation was used
        """
        verb = "FORCED" if forced else "OK"
        self._log.warning(
            "[%s][STAGE][%s] %s → %s | model=%s id=%s",
            self.PREFIX, verb, from_code, to_code,
            record._name, record.id,
        ) if forced else self._log.info(
            "[%s][STAGE][%s] %s → %s | model=%s id=%s",
            self.PREFIX, verb, from_code, to_code,
            record._name, record.id,
        )

    def financial_alert(self, record, label, amount, percent=None):
        """
        Log a financial anomaly (negative margin, budget overrun, etc.).
        Always emitted at CRITICAL level — will appear in Odoo.sh error stream.

        :param record:  the concerned recordset (lot, chantier…)
        :param label:   short description e.g. "MARGE NEGATIVE"
        :param amount:  monetary value in EUR (float)
        :param percent: optional percentage (float)
        """
        if percent is not None:
            self._log.critical(
                "[%s][FINANCE][ALERT] %s | model=%s id=%s | amount=%.2f EUR | percent=%.1f%%",
                self.PREFIX, label, record._name, record.id, amount, percent,
            )
        else:
            self._log.critical(
                "[%s][FINANCE][ALERT] %s | model=%s id=%s | amount=%.2f EUR",
                self.PREFIX, label, record._name, record.id, amount,
            )

    def overbilling(self, record, completion_pct):
        """
        Shorthand for over-billing detection (US-COR-005).

        :param record:          the lot recordset
        :param completion_pct:  current completion percentage (float > 100)
        """
        self._log.critical(
            "[%s][FINANCE][OVERBILLING] Lot %s completion=%.1f%% exceeds 100%% | id=%s",
            self.PREFIX, getattr(record, 'code', '?'), completion_pct, record.id,
        )

    def compliance_check(self, record, check_name, passed):
        """
        Log a compliance / prerequisite check result.

        :param record:      the record being checked (partner, lot…)
        :param check_name:  label e.g. "URSSAF", "KBIS", "CCTP_UPLOADED"
        :param passed:      True = OK, False = FAIL
        """
        level = "OK" if passed else "FAIL"
        log_fn = self._log.info if passed else self._log.warning
        log_fn(
            "[%s][COMPLIANCE][%s] %s | model=%s id=%s",
            self.PREFIX, level, check_name, record._name, record.id,
        )

    def business_error(self, record_or_name, action, exc):
        """
        Log a caught exception that shouldn't crash the app but must be traced.

        :param record_or_name: recordset or plain string model name
        :param action:         method/action name e.g. "action_generate_po"
        :param exc:            the exception instance
        """
        model = (
            record_or_name._name
            if hasattr(record_or_name, '_name')
            else str(record_or_name)
        )
        rid = record_or_name.id if hasattr(record_or_name, 'id') else '?'
        self._log.error(
            "[%s][ERROR] action=%s | model=%s id=%s | %s: %s",
            self.PREFIX, action, model, rid, type(exc).__name__, exc,
        )

    def email_event(self, event, details=""):
        """
        Log an email-automation event.

        :param event:   short event token e.g. "CHANTIER_CREATED", "REMINDER_J7"
        :param details: free-text context (use %s safe values — no f-strings)
        """
        self._log.info("[%s][MAIL][%s] %s", self.PREFIX, event, details)

    def wizard_action(self, wizard_name, action, record=None):
        """
        Log a wizard action execution (audit trail).

        :param wizard_name: e.g. "ForceStageWizard"
        :param action:      e.g. "action_force_stage"
        :param record:      optional target recordset
        """
        if record is not None:
            self._log.info(
                "[%s][WIZARD][%s] action=%s | model=%s id=%s",
                self.PREFIX, wizard_name, action, record._name, record.id,
            )
        else:
            self._log.info(
                "[%s][WIZARD][%s] action=%s",
                self.PREFIX, wizard_name, action,
            )


def get_logger(name: str) -> ConstructionLogger:
    """
    Factory — drop-in replacement for ``logging.getLogger(__name__)``.

    Example::

        from odoo.addons.construction_core.utils.logger import get_logger
        _logger = get_logger(__name__)
    """
    return ConstructionLogger(name)
