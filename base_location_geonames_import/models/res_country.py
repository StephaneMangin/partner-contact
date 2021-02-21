# Copyright 2017 Franco Tampieri, Freelancer http://franco.tampieri.info
# Copyright 2021 Stéphane Mangin <stephane.mangin@freesbee.fr>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCountry(models.Model):

    _inherit = "res.country"

    geonames_state_name_column = fields.Integer("Geonames State Name Column")
    geonames_state_code_column = fields.Integer("Geonames State Code Column")
    geonames_borough_name_column = fields.Integer("Geonames Borough Name Column")
    geonames_borough_code_column = fields.Integer("Geonames Borough Code Column")
