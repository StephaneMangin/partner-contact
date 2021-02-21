# Copyright 2014-2016 Akretion (Alexis de Lattre
#                     <alexis.delattre@akretion.com>)
# Copyright 2014 Lorenzo Battistini <lorenzo.battistini@agilebg.com>
# Copyright 2017 Eficent Business and IT Consulting Services, S.L.
#                <contact@eficent.com>
# Copyright 2018 Aitor Bouzas <aitor.bouzas@adaptivecity.com>
# Copyright 2016-2020 Tecnativa - Pedro M. Baeza
# Copyright 2021 Stéphane Mangin <stephane.mangin@freesbee.fr>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import csv
import io
import logging
import os
import tempfile
import zipfile

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class CityZipGeonamesImport(models.TransientModel):
    _name = "city.zip.geonames.import"
    _description = "Import City Zips from Geonames"

    country_ids = fields.Many2many("res.country", string="Countries")

    letter_case = fields.Selection(
        [("unchanged", "Unchanged"), ("title", "Title Case"), ("upper", "Upper Case")],
        string="Letter Case",
        default="unchanged",
        help="Converts retreived city and state names to Title Case "
        "(upper case on each first letter of a word) or Upper Case "
        "(all letters upper case).",
    )

    @api.model
    def transform_name(self, name):
        """Override it for transforming name (if needed)
        :param city: Original name
        :param country: Country record
        :return: Transformed name
        """
        res = name
        if self.letter_case == "title":
            res = name.title()
        elif self.letter_case == "upper":
            res = name.upper()
        return res

    @api.model
    def _domain_search_city_zip(self, row, city_id=False):
        domain = [("name", "=", row[1])]
        if city_id:
            domain += [("city_id", "=", city_id)]
        return domain

    @api.model
    def select_state(self, row, country):
        code = row[country.geonames_state_code_column or 4]
        return self.env["res.country.state"].search(
            [("country_id", "=", country.id), ("code", "=", code)], limit=1
        )

    @api.model
    def select_borough(self, row, state_id):
        # This has to be done by SQL for performance reasons avoiding
        # left join with ir_translation on the translatable field "name"
        self.env.cr.execute(
            "SELECT id, name FROM res_borough "
            "WHERE name = %s AND code= %s AND state_id = %s LIMIT 1",
            (self.transform_name(row[7]), row[8], state_id),
        )
        row_borough = self.env.cr.fetchone()
        return (row_borough[0], row_borough[1]) if row_borough else (False, False)

    @api.model
    def select_city(self, row, borough_id, state_id, country_id):
        # This has to be done by SQL for performance reasons avoiding
        # left join with ir_translation on the translatable field "name"
        self.env.cr.execute(
            "SELECT id, name FROM res_city "
            "WHERE name = %s AND borough_id = %s AND state_id = %s AND country_id = %s LIMIT 1",
            (self.transform_name(row[2]), borough_id, state_id, country_id),
        )
        row_city = self.env.cr.fetchone()
        return (row_city[0], row_city[1]) if row_city else (False, False)

    @api.model
    def select_zip(self, row, country, state_id):
        city_id, _ = self.select_city(row, country, state_id)
        return self.env["res.city.zip"].search(
            self._domain_search_city_zip(row, city_id)
        )

    @api.model
    def prepare_state(self, row, country):
        return {
            "name": row[country.geonames_state_name_column or 3],
            "code": row[country.geonames_state_code_column or 4],
            "country_id": country.id,
        }

    @api.model
    def prepare_borough(self, row, country, state_id):
        name = row[country.geonames_borough_name_column or 5]
        code = row[country.geonames_borough_code_column or 6]
        if name and code:
            return {
                "name": name,
                "code": code,
                "state_id": state_id,
                "country_id": country.id,
            }

    @api.model
    def prepare_city(self, row, borough_id, state_id, country):
        vals = {
            "name": self.transform_name(row[2]),
            "borough_id": borough_id,
            "state_id": state_id,
            "country_id": country.id,
        }
        return vals

    @api.model
    def prepare_zip(self, row, city_id):
        vals = {
            "name": row[1],
            "city_id": city_id,
        }
        return vals

    @api.model
    def get_and_parse_csv(self, country):
        country_code = country.code
        config_url = self.env["ir.config_parameter"].get_param(
            "geonames.url", default="http://download.geonames.org/export/zip/%s.zip"
        )
        url = config_url % country_code
        logger.info("Starting to download %s" % url)
        res_request = requests.get(url)
        if res_request.status_code != requests.codes.ok:
            raise UserError(
                _("Got an error %d when trying to download the file %s.")
                % (res_request.status_code, url)
            )

        f_geonames = zipfile.ZipFile(io.BytesIO(res_request.content))
        tempdir = tempfile.mkdtemp(prefix="odoo")
        f_geonames.extract("%s.txt" % country_code, tempdir)

        data_file = open(
            os.path.join(tempdir, "%s.txt" % country_code), "r", encoding="utf-8"
        )
        data_file.seek(0)
        reader = csv.reader(data_file, delimiter="	")
        parsed_csv = [row for i, row in enumerate(reader)]
        data_file.close()
        logger.info("The geonames zipfile has been decompressed")
        return parsed_csv

    def _create_states(self, parsed_csv, search_states, max_import, country):
        # States
        state_vals_list = []
        state_dict = {}
        for i, row in enumerate(parsed_csv):
            if max_import and i == max_import:
                break
            state = self.select_state(row, country) if search_states else False
            if not state:
                state_vals = self.prepare_state(row, country)
                if state_vals not in state_vals_list:
                    state_vals_list.append(state_vals)
            else:
                state_dict[state.code] = state.id

        created_states = self.env["res.country.state"].create(state_vals_list)
        for i, vals in enumerate(state_vals_list):
            state_dict[vals["code"]] = created_states[i].id
        return state_dict

    def _create_boroughs(
        self, parsed_csv, search_boroughs, max_import, state_dict, country
    ):
        # Boroughs
        borough_vals_list = []
        borough_dict = {}
        for i, row in enumerate(parsed_csv):
            if max_import and i == max_import:
                break
            state_id = state_dict[row[country.geonames_state_code_column or 4]]
            borough_id, borough_name = (
                self.select_borough(row, country, state_id)
                if search_boroughs
                else (False, False)
            )
            if not borough_id:
                borough_vals = self.prepare_borough(row, country, state_id)
                if borough_vals and borough_vals not in borough_vals_list:
                    borough_vals_list.append(borough_vals)
            else:
                borough_dict[(borough_name, state_id)] = borough_id
        ctx = dict(self.env.context)
        ctx.pop("lang", None)  # make sure no translation is added
        # print(borough_vals_list)
        created_boroughs = self.env["res.borough"].with_context(ctx).create(borough_vals_list)
        for i, vals in enumerate(borough_vals_list):
            borough_dict[vals["code"]] = created_boroughs[i].id
        return borough_dict

    def _create_cities(
        self, parsed_csv, search_cities, max_import, borough_dict, state_dict, country
    ):
        # Cities
        city_vals_list = []
        city_dict = {}
        for i, row in enumerate(parsed_csv):
            if max_import and i == max_import:
                break
            borough_id = borough_dict.get(row[country.geonames_borough_code_column or 8], False)
            state_id = state_dict[row[country.geonames_state_code_column or 4]]
            city_id, city_name = (
                self.select_city(row, country, borough_id, state_id)
                if search_cities
                else (False, False)
            )
            if not city_id:
                city_vals = self.prepare_city(row, borough_id, state_id, country)
                if city_vals not in city_vals_list:
                    city_vals_list.append(city_vals)
            else:
                city_dict[(city_name, borough_id)] = city_id
        ctx = dict(self.env.context)
        ctx.pop("lang", None)  # make sure no translation is added
        created_cities = self.env["res.city"].with_context(ctx).create(city_vals_list)
        for i, vals in enumerate(city_vals_list):
            city_dict[(vals["name"], vals["state_id"])] = created_cities[i].id
        return city_dict

    def run_import(self):
        for country in self.country_ids:
            parsed_csv = self.get_and_parse_csv(country)
            self._process_csv(parsed_csv, country)
        return True

    def _process_csv(self, parsed_csv, country):
        state_model = self.env["res.country.state"]
        zip_model = self.env["res.city.zip"]
        res_city_model = self.env["res.city"]
        res_borough_model = self.env["res.borough"]
        # Store current record list
        old_zips = set(zip_model.search([("city_id.country_id", "=", country.id)]).ids)
        search_zips = len(old_zips) > 0
        old_cities = set(res_city_model.search([("country_id", "=", country.id)]).ids)
        search_cities = len(old_cities) > 0
        old_boroughs = set(res_borough_model.search([("country_id", "=", country.id)]).ids)
        search_boroughs = len(old_boroughs) > 0
        current_states = state_model.search([("country_id", "=", country.id)])
        search_states = len(current_states) > 0
        max_import = self.env.context.get("max_import", 0)
        logger.info("Starting to create the boroughs, cities and/or city zip entries")

        # Pre-create states, boroughs, townships and cities
        state_dict = self._create_states(parsed_csv, search_states, max_import, country)
        borough_dict = self._create_boroughs(
            parsed_csv, search_boroughs, max_import, state_dict, country
        )
        city_dict = self._create_cities(
            parsed_csv, search_cities, max_import, borough_dict, state_dict, country
        )

        # Zips
        zip_vals_list = []
        for i, row in enumerate(parsed_csv):
            if max_import and i == max_import:
                break
            # Don't search if there aren't any records
            zip_code = False
            state_id = state_dict[row[country.geonames_state_code_column or 4]]
            if search_zips:
                zip_code = self.select_zip(row, country, state_id)
            if not zip_code:
                city_id = city_dict[
                    (self.transform_name(row[2]), state_id)
                ]
                zip_vals = self.prepare_zip(row, city_id)
                if zip_vals not in zip_vals_list:
                    zip_vals_list.append(zip_vals)
            else:
                old_zips.remove(zip_code.id)

        self.env["res.city.zip"].create(zip_vals_list)
        if not max_import:
            if old_zips:
                logger.info("removing city zip entries")
                self.env["res.city.zip"].browse(list(old_zips)).unlink()
                logger.info(
                    "%d city zip entries deleted for country %s"
                    % (len(old_zips), country.name)
                )
            old_cities -= set(city_dict.values())
            if old_cities:
                logger.info("removing city entries")
                self.env["res.city"].browse(list(old_cities)).unlink()
                logger.info(
                    "%d res.city entries deleted for country %s"
                    % (len(old_cities), country.name)
                )
            old_boroughs -= set(borough_dict.values())
            if old_boroughs:
                logger.info("removing borough entries")
                self.env["res.borough"].browse(list(old_boroughs)).unlink()
                logger.info(
                    "%d res.borough entries deleted for country %s"
                    % (len(old_boroughs), country.name)
                )
        logger.info(
            "The wizard to create boroughs, cities and/or city zip entries from "
            "geonames has been successfully completed."
        )
        return True
