# -*- coding: utf-8 -*-

import logging

from odoo.exceptions import UserError, ValidationError

from odoo import api, fields, models, _
from datetime import datetime
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    """
        Inherit sale order module for customization
    """
    _inherit = 'helpdesk.ticket'

    sale_cont_id = fields.Many2one('sale.order', string='Order',
                                   domain="[('partner_id', '=', partner_id), ('state','=', 'sale')]")
    sale_pr_id = fields.Many2one('sale.order', string='Order property', domain="[('partner_id', '=', partner_id)]")
    property_name = fields.Char(
        string='Property Name',
        required=False)
    other_number = fields.Char(
        string='Other number',
        required=False)
    block_number = fields.Char(
        string='Block number',
        required=False)

    @api.onchange("sale_cont_id")
    def set_sale_pr_id(self):
        self.property_name = self.sale_cont_id.property_name
