# -*- coding: utf-8 -*-

import logging

from odoo.exceptions import UserError, ValidationError

from odoo import api, fields, models, _
from datetime import datetime
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class SaleTemporalRecurrence(models.Model):

    _inherit = 'sale.temporal.recurrence'

    no_of_recurrence = fields.Integer("No Of Recurrance")

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'


    def _timesheet_create_task_prepare_values(self, project):
        self.ensure_one()
        planned_hours = self._convert_qty_company_hours(self.company_id)
        sale_line_name_parts = self.name.split('\n')
        title = sale_line_name_parts[0] or self.product_id.name
        description = '<br/>'.join(sale_line_name_parts[1:])

        return {
            'name': title if project.sale_line_id else '%s - %s' % (self.order_id.name or '', title),
            'analytic_account_id': project.analytic_account_id.id,
            'planned_hours': planned_hours,
            'partner_id': self.order_id.partner_id.id,
            'email_from': self.order_id.partner_id.email,
            'description': description,
            'project_id': project.id,
            'sale_line_id': self.id,
            'sale_order_id': self.order_id.id,
            'company_id': project.company_id.id,
            'user_ids': False,  # force non assigned task, as created as sudo()
        }








    def _timesheet_service_generation(self):
        """ For service lines, create the task or the project. If already exists, it simply links
            the existing one to the line.
            Note: If the SO was confirmed, cancelled, set to draft then confirmed, avoid creating a
            new project/task. This explains the searches on 'sale_line_id' on project/task. This also
            implied if so line of generated task has been modified, we may regenerate it.
        """
        so_line_task_global_project = self.filtered(lambda sol: sol.is_service and sol.product_id.service_tracking == 'task_global_project')
        so_line_new_project = self.filtered(lambda sol: sol.is_service and sol.product_id.service_tracking in ['project_only', 'task_in_project'])

        # search so lines from SO of current so lines having their project generated, in order to check if the current one can
        # create its own project, or reuse the one of its order.
        map_so_project = {}
        if so_line_new_project:
            order_ids = self.mapped('order_id').ids
            so_lines_with_project = self.search([('order_id', 'in', order_ids), ('project_id', '!=', False), ('product_id.service_tracking', 'in', ['project_only', 'task_in_project']), ('product_id.project_template_id', '=', False)])
            map_so_project = {sol.order_id.id: sol.project_id for sol in so_lines_with_project}
            so_lines_with_project_templates = self.search([('order_id', 'in', order_ids), ('project_id', '!=', False), ('product_id.service_tracking', 'in', ['project_only', 'task_in_project']), ('product_id.project_template_id', '!=', False)])
            map_so_project_templates = {(sol.order_id.id, sol.product_id.project_template_id.id): sol.project_id for sol in so_lines_with_project_templates}

        # search the global project of current SO lines, in which create their task
        map_sol_project = {}
        if so_line_task_global_project:
            map_sol_project = {sol.id: sol.product_id.with_company(sol.company_id).project_id for sol in so_line_task_global_project}

        def _can_create_project(sol):
            if not sol.project_id:
                if sol.product_id.project_template_id:
                    return (sol.order_id.id, sol.product_id.project_template_id.id) not in map_so_project_templates
                elif sol.order_id.id not in map_so_project:
                    return True
            return False

        def _determine_project(so_line):
            """Determine the project for this sale order line.
            Rules are different based on the service_tracking:

            - 'project_only': the project_id can only come from the sale order line itself
            - 'task_in_project': the project_id comes from the sale order line only if no project_id was configured
              on the parent sale order"""

            if so_line.product_id.service_tracking == 'project_only':
                return so_line.project_id
            elif so_line.product_id.service_tracking == 'task_in_project':
                return so_line.order_id.project_id or so_line.project_id

            return False

        # task_global_project: create task in global project
        for so_line in so_line_task_global_project:
            if not so_line.task_id:
                if map_sol_project.get(so_line.id) and so_line.product_uom_qty > 0:
                    so_line._timesheet_create_task(project=map_sol_project[so_line.id])

        # project_only, task_in_project: create a new project, based or not on a template (1 per SO). May be create a task too.
        # if 'task_in_project' and project_id configured on SO, use that one instead
        for so_line in so_line_new_project:
            project = _determine_project(so_line)
            if not project and _can_create_project(so_line):
                project = so_line._timesheet_create_project()
                if so_line.product_id.project_template_id:
                    map_so_project_templates[(so_line.order_id.id, so_line.product_id.project_template_id.id)] = project
                else:
                    map_so_project[so_line.order_id.id] = project
            elif not project:
                # Attach subsequent SO lines to the created project
                so_line.project_id = (
                    map_so_project_templates.get((so_line.order_id.id, so_line.product_id.project_template_id.id))
                    or map_so_project.get(so_line.order_id.id)
                )
            if so_line.product_id.service_tracking == 'task_in_project':
                if not project:
                    if so_line.product_id.project_template_id:
                        project = map_so_project_templates[(so_line.order_id.id, so_line.product_id.project_template_id.id)]
                    else:
                        project = map_so_project[so_line.order_id.id]
                if not so_line.task_id:
                    so_line._timesheet_create_task(project=project)
            so_line._generate_milestone()




















    def _timesheet_create_task(self, project):
        """ Generate task for the given so line, and link it.
            :param project: record of project.project in which the task should be created
            :return task: record of the created task
        """
        sale_line_name_parts = self.name.split('\n')

        planned_hours = self._convert_qty_company_hours(self.company_id)
        description = '<br/>'.join(sale_line_name_parts[1:])

        if self.order_id.recurrence_id.no_of_recurrence > 0:
            no_of_task = self.order_id.recurrence_id.no_of_recurrence

            i = 1

            for i in range(no_of_task):

                previous_task = self.env['project.task'].search([('project_id','=',project.id),('sale_line_id','=',self.id)])
                if len(previous_task) > 0:
                    last_date_deadline =  previous_task[0].date_deadline
                else:
                    last_date_deadline = previous_task.date_deadline
                if not previous_task:
                    date_deadline = self.order_id.contract_start_date + relativedelta(months=12/no_of_task)
                else:
                    date_deadline = last_date_deadline + relativedelta(months=12/no_of_task)

                values = { 'name': 'PPM' +' ' +str(i+1),
               'analytic_account_id': project.analytic_account_id.id,
               'planned_hours': planned_hours,
               'partner_id': self.order_id.partner_id.id,
               'email_from': self.order_id.partner_id.email,
               'description': description,
               'project_id': project.id,
               'sale_line_id': self.id,
               'sale_order_id': self.order_id.id,
               'company_id': project.company_id.id,
               'user_ids': False,
               'date_deadline': date_deadline
                        }
                task = self.env['project.task'].sudo().create(values)
                task.write({'sale_order_id': self.order_id.id})
        # post message on task
                task_msg = _("This task has been created from: %s (%s)", self.order_id._get_html_link(), self.product_id.name)
                task.message_post(body=task_msg)
        else:
            values = self._timesheet_create_task_prepare_values(project)
            task = self.env['project.task'].sudo().create(values)
            self.write({'task_id': task.id})
        # post message on task
            task_msg = _("This task has been created from: %s (%s)", self.order_id._get_html_link(), self.product_id.name)
            task.message_post(body=task_msg)
        return task

class Task(models.Model):
    _inherit = 'project.task'

    sale_order_id =  fields.Many2one('sale.order')

class SaleOrder(models.Model):
    """
        Inherit sale order module for customization
    """
    _inherit = 'sale.order'
    contract_reference = fields.Char(
        string='Contract Reference')
    property_name = fields.Char(
        string='Property Name'
    )
    contact_name = fields.Char(
        string='Contact Name'
    )
    contact_number = fields.Char(
        string='Contact Number'
    )
    contract_start_date = fields.Date(
        string='Contract start date')

    contract_end_date = fields.Date(
        string='Contract end date')
    #pricelist_descriptoion = fields.Text(string='Pricelist Description', related="pricelist_id.description")
    project_id = fields.Many2one('project.project', string='Project')
    task_ids = fields.One2many('project.task','sale_order_id')




    @api.onchange('recurrence_id', 'contract_start_date')
    def get_contract_end_date(self):
        if self.recurrence_id and self.contract_start_date:
            duration = self.recurrence_id.duration
            unit = self.recurrence_id.unit
            if unit == 'day':
                self.contract_end_date = self.contract_start_date + relativedelta(days=duration)
            elif unit == 'week':
                self.contract_end_date = self.contract_start_date + relativedelta(weeks=duration)
            elif unit == 'month':
                self.contract_end_date = self.contract_start_date + relativedelta(months=duration)
            elif unit == 'year':
                self.contract_end_date = self.contract_start_date + relativedelta(years=duration)
            self.end_date = self.contract_end_date

    def name_get(self):
        result = []
        context_ref = self.env.context.get('check_reff')
        property_ref = self.env.context.get('property_ref')
        for record in self:
            if context_ref:
                result.append((record.id, _('%s - %s') % ((record.name or '-'), (record.contract_reference or '-'))))
            elif property_ref:
                result.append((record.id,  _('%s - %s') % ((record.name or '-'), (record.property_name or '-'))))
            else:
                result.append((record.id, record.name))
        return result
