# Copyright 2021 Stéphane Mangin
# @author: Stéphane Mangin <stephane.mangin@freesbee.fr>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Department(models.Model):
    _name = 'res.country.department'
    _description = 'Department'
    _order = 'code, name'

    name = fields.Char("Name", size=128, required=True)
    code = fields.Char("Code", required=True)
    borough_ids = fields.One2many(
        "res.country.borough",
        "department_id",
        string="Boroughs",
        help="Boroughs of the department",
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        help="State of the department",
    )
    country_id = fields.Many2one(
        "res.country",
        related="state_id.country_id",
        string="Country",
        help="Country of the related borough",
        store=True,
    )

    _sql_constraints = [
        (
            "code_uniq",
            "unique (code)",
            "You cannot have two departments with the same code!",
        )
    ]

    @api.depends("name", "code")
    def name_get(self):
        res = []
        for rec in self:
            dname = "{} ({})".format(rec.name, rec.code)
            res.append((rec.id, dname))
        return res
