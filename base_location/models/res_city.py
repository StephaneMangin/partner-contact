# Copyright 2018 Aitor Bouzas <aitor.bouzas@adaptivecity.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class City(models.Model):
    _inherit = "res.city"

    zip_ids = fields.One2many("res.city.zip", "city_id", string="Zips in this city")
    borough_id = fields.Many2one('res.country.borough', 'Borough')
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

    _sql_constraints = [
        (
            "name_state_country_borough_uniq",
            "UNIQUE(name, borough_id, state_id, country_id)",
            "You already have a city with that name in the same state and borough."
            "The city must have a unique name within "
            "it's borough, it's state and it's country",
        )
    ]
