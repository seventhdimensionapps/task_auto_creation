# -*- coding: utf-8 -*-

import logging

from odoo.exceptions import UserError, ValidationError

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    pricelist = fields.Many2one('product.pricelist',string='Pricelist')
    pricelist_descriptoion = fields.Text(string='Pricelist Description')

    @api.model_create_multi
    def create(self, vals_list):
        result = super(AccountMove, self).create(vals_list)
        vals = {}
        if result.invoice_origin:
            order = self.env['sale.order'].search([('name', '=', result.invoice_origin)])
            if order:
                vals.update({
                    'pricelist': order.pricelist_id.id,
                    'pricelist_descriptoion': order.pricelist_id.description
                })
        result.write(vals)
        return result
