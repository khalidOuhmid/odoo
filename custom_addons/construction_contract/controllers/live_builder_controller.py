"""
Live Builder Controller
Handles the interactive contract builder interface
"""

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError, AccessError
from dateutil.relativedelta import relativedelta
from werkzeug.exceptions import NotFound
from ..config.contract_constants import DEFAULT_RETENTION_RATE
import json


class ContractLiveBuilderController(http.Controller):
    """
    Interactive Contract Builder Controller

    Provides live contract editing interface with:
    - Real-time preview rendering
    - Contract creation from wizard data
    - Manual HTML editing support
    """

    @http.route('/contract/live-builder', type='http', auth='user', website=True)
    def live_builder(self, chantier_id=None, subcontractor_id=None, template_id=None, **kwargs):
        env = request.env
        user = env.user
        if not (user.has_group('construction_contract.group_construction_pilote') or user.has_group('base.group_system')):
            raise AccessError(_("You do not have access to the contract builder."))
        if not chantier_id:
            raise NotFound(_("Chantier parameter is missing."))
        chantier = env['construction.chantier'].browse(int(chantier_id))
        if not chantier.exists():
            raise NotFound(_("Chantier not found."))
        subcontractors = env['res.partner'].search(
            [('contact_type', '=', 'sous_traitant')],
            order='name asc'
        )
        templates = env['construction.contract.template'].search(
            [('active', '=', True)],
            order='sequence, name'
        )
        default_subcontractor_id = int(subcontractor_id) if subcontractor_id else (
            chantier.subcontractor_ids[:1].id if chantier.subcontractor_ids else False
        )
        default_template_id = int(template_id) if template_id else (templates[:1].id if templates else False)
        today = fields.Date.context_today(user)
        default_values = {
            'contract_date': fields.Date.to_string(today),
            'start_date': fields.Date.to_string(today),
            'end_date': fields.Date.to_string(today + relativedelta(months=1)),
            'retention_rate': DEFAULT_RETENTION_RATE,
            'subcontractor_id': default_subcontractor_id,
            'template_id': default_template_id,
            'lot_ids': chantier.lots_ids.ids,
            'generate_deliverables': True,
            'send_immediately': False,
        }
        builder_config = json.dumps({
            'chantier_id': chantier.id,
            'render_url': '/contract/live-builder/render',
            'create_url': '/contract/live-builder/create',
        })
        values = {
            'chantier': chantier,
            'subcontractors': subcontractors,
            'templates': templates,
            'default_values': default_values,
            'builder_config': builder_config,
        }
        return request.render('construction_contract.contract_live_builder_page', values)

    @http.route('/contract/live-builder/render', type='json', auth='user')
    def render_preview(self, payload=None):
        env = request.env
        payload = payload or {}
        wizard = None
        try:
            wizard = self._create_wizard_from_payload(env, payload)
            html_content = env['construction.contract.template.renderer'].render_preview_from_wizard(wizard)
            return {'status': 'success', 'html': html_content}
        except (ValidationError, UserError) as error:
            message = getattr(error, 'name', str(error))
            return {'status': 'error', 'message': message}
        except Exception as error:
            return {'status': 'error', 'message': str(error)}
        finally:
            if wizard:
                wizard.unlink()

    @http.route('/contract/live-builder/create', type='json', auth='user')
    def create_contract(self, payload=None):
        env = request.env
        payload = payload or {}
        send_now = bool(payload.get('send_immediately'))
        wizard = None
        try:
            wizard = self._create_wizard_from_payload(env, payload)
            action = wizard.action_create_contract()
            contract_id = action.get('res_id')
            contract = env['construction.contract'].browse(contract_id)
            manual_html = payload.get('manual_html')
            if manual_html:
                contract.custom_html_override = manual_html
            contract.action_generate_pdf()
            if send_now:
                contract.action_send_for_signature()
            redirect_url = f"/web#id={contract_id}&model=construction.contract&view_type=form"
            return {'status': 'success', 'contract_id': contract_id, 'redirect_url': redirect_url}
        except (ValidationError, UserError) as error:
            message = getattr(error, 'name', str(error))
            return {'status': 'error', 'message': message}
        except Exception as error:
            return {'status': 'error', 'message': str(error)}
        finally:
            if wizard:
                wizard.unlink()

    def _create_wizard_from_payload(self, env, payload):
        """
        Create a contract.creation.wizard record from live builder payload.

        Args:
            env: Odoo environment
            payload (dict): Form data from frontend

        Returns:
            contract.creation.wizard: Created wizard record
        """

        def _clean_id(value):
            try:
                value_int = int(value)
                return value_int or False
            except (TypeError, ValueError):
                return False

        lot_ids = [int(lot) for lot in (payload.get('lot_ids') or []) if lot]
        wizard_vals = {
            'chantier_id': _clean_id(payload.get('chantier_id')),
            'subcontractor_id': _clean_id(payload.get('subcontractor_id')),
            'template_id': _clean_id(payload.get('template_id')),
            'start_date': payload.get('start_date'),
            'end_date': payload.get('end_date'),
            'contract_date': payload.get('contract_date'),
            'retention_rate': float(payload.get('retention_rate') or DEFAULT_RETENTION_RATE),
            'generate_deliverables': bool(payload.get('generate_deliverables', True)),
            'send_immediately': False,
            'lot_ids': [(6, 0, lot_ids)],
        }
        return env['contract.creation.wizard'].create(wizard_vals)

