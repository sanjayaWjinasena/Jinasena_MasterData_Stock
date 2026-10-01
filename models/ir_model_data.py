# -*- coding: utf-8 -*-
"""Bind our xmlids to already-existing warehouse/location DB rows.

Called from data/00_bind_xmlids.xml BEFORE CSV data files load. Fires on
both fresh install AND upgrade (pre_init_hook only fires on fresh install).

Reads our CSVs; for each row where a DB record already matches on
(name, company_id[, location_id]), registers our xmlid via ir.model.data
pointing at that record. CSV load then treats those rows as UPDATE
(no INSERT, no unique-constraint collision).
"""
import csv
import logging
import os
from odoo import api, models

_logger = logging.getLogger(__name__)

MODULE = 'Jinasena_MasterData_Stock'


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    @api.model
    def _jinasena_stock_bind_existing_rows(self):
        module_root = os.path.dirname(os.path.dirname(__file__))
        data_dir = os.path.join(module_root, 'data')

        self._jinasena_stock_bind_one(
            model='stock.warehouse',
            csv_path=os.path.join(data_dir, 'stock.warehouse.csv'),
            match_fields=[('name', 'name'), ('company_id', 'company_id/id')],
        )
        # v0.0.7: stock.location bind re-enabled. Match on (name, location_id,
        # company_id) — Odoo auto-creates WH/Stock, WH/Input, WH/Output etc.
        # per warehouse, so (name, company) alone is ambiguous when the same
        # warehouse name exists under both Jinasena companies.
        self._jinasena_stock_bind_one(
            model='stock.location',
            csv_path=os.path.join(data_dir, 'stock.location.csv'),
            match_fields=[
                ('name', 'name'),
                ('location_id', 'location_id/id'),
                ('company_id', 'company_id/id'),
            ],
        )
        return True

    @api.model
    def _jinasena_stock_bind_one(self, model, csv_path, match_fields):
        if not os.path.exists(csv_path):
            _logger.warning('[%s] CSV missing: %s', MODULE, csv_path)
            return
        IMD = self.sudo()
        Model = self.env[model].sudo()
        bound = 0
        skipped_existing = 0
        for row in _read_csv(csv_path):
            xmlid = row.get('id')
            if not xmlid:
                continue
            already = IMD.search([('module', '=', MODULE), ('name', '=', xmlid)], limit=1)
            if already:
                skipped_existing += 1
                continue
            domain = []
            skip = False
            for db_field, csv_col in match_fields:
                val = row.get(csv_col, '')
                if csv_col.endswith('/id'):
                    if val:
                        try:
                            res_id = self.env.ref(val).id
                        except Exception:
                            skip = True
                            break
                        domain.append((db_field, '=', res_id))
                    else:
                        domain.append((db_field, '=', False))
                else:
                    domain.append((db_field, '=', val or False))
            if skip:
                continue
            recs = Model.search(domain, limit=1)
            if not recs:
                continue
            IMD.create({
                'module': MODULE,
                'name': xmlid,
                'model': model,
                'res_id': recs.id,
                'noupdate': False,
            })
            bound += 1
        _logger.info('[%s] bound %s existing %s rows (%s xmlids already registered)',
                     MODULE, bound, model, skipped_existing)


def _read_csv(path):
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            yield row
