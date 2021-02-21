# Copyright 2021 Stéphane Mangin
# @author: Stéphane Mangin <stephane.mangin@freesbee.fr>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Borough(models.Model):
    _name = 'res.country.borough'
    _description = 'Borough'
    _order = 'code, name'

    name = fields.Char("Name", size=128, required=True)
    code = fields.Char("Code", required=True)
    city_ids = fields.One2many(
        "res.city",
        "borough_id",
        string="Cities",
        help="Cities of the related borough",
    )
    department_id = fields.Many2one(
        "res.country.department",
        string="State",
        help="Department of the borough",
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        help="State of the related department",
    )
    country_id = fields.Many2one(
        "res.country",
        related="state_id.country_id",
        string="Country",
        help="Country of the related borough",
        store=True,
    )

    # _sql_constraints = [
    #     (
    #         "code_uniq",
    #         "unique (code)",
    #         "You cannot have two boroughs with the same code!",
    #     )
    # ]

    @api.depends("name", "code")
    def name_get(self):
        res = []
        for rec in self:
            dname = "{} ({})".format(rec.name, rec.code)
            res.append((rec.id, dname))
        return res
