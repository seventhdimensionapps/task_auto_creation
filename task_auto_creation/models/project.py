# -*- coding: utf-8 -*-

import logging

from odoo.exceptions import UserError, ValidationError

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class Project(models.Model):
    _inherit = 'project.project'
    property_name = fields.Char(
        string='Property Name'
    )
    contract_reference = fields.Char(
        string='Contract Reference'
    )
    sale_order_counts = fields.Integer(compute='project_sale_order_count')
    product_lines = fields.One2many('project.sale.order', 'project_id')

    @api.model_create_multi
    def create(self, vals_list):
        result = super(Project, self).create(vals_list)
        vals = {}
        if result.sale_order_id and result.sale_order_id.contract_reference:
            vals.update({
                'name': result.sale_order_id.name + "/" + result.sale_order_id.contract_reference,
            })
        if result.sale_order_id.user_id:
            vals.update({
                'user_id': result.sale_order_id.user_id.id,
            })
        if result.sale_order_id.contract_start_date:
            vals.update({
                'date_start': result.sale_order_id.contract_start_date,
                'date': result.sale_order_id.contract_end_date,
            })
        if result.sale_order_id.property_name:
            vals.update({
                'property_name': result.sale_order_id.property_name,
            })
        if result.sale_order_id.contract_reference:
            vals.update({
                'contract_reference': result.sale_order_id.contract_reference,
            })
        result.write(vals)
        return result

    def create_sale_order(self):
        vals = {}
        so_lines = []
        vals.update({
            'partner_id': self.partner_id.id,
            'contract_reference': self.contract_reference,
            'property_name': self.property_name,
            'project_id': self.id,
        })
        sale_order = self.env['sale.order'].sudo().create(vals)
        for line in self.product_lines:
            so_lines.append((0, 0,{
                'product_template_id':line.product_tmpl_po_id,
                'name':line.name,
                'product_uom_qty':line.product_uom_qty_po,
                'price_unit': line.price_unit_po,
                'discount': line.discount_po,
                'customer_lead': 0.00,
                'order_id': sale_order.id,
                'product_id':line.product_tmpl_po_id.product_variant_id.id,
            }))
        sale_order.write({
            'order_line': so_lines
        })

    def show_sale_order(self):
        action = {
            "name": _("Sale orders"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "tree,form",
            "domain": [("project_id", "=", self.id)],
        }
        return action

    def project_sale_order_count(self):
        for rec in self:
            sale_orders = self.env['sale.order'].sudo().search([('project_id', '=', rec.id)])
            if sale_orders:
                project_sale_order_count = len(sale_orders)
                rec.sale_order_counts = project_sale_order_count
            else:
                rec.sale_order_counts = 0

