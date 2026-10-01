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

        # v0.0.8: match on (code, company) not (name, company). Codes are
        # 3-5 char stable identifiers (PW-JM, CW-CM) that match CDB↔target
        # verbatim. Names drifted on 14 of 63 warehouses in v0.0.7, causing
        # new INSERTs → auto-child-location-create → barcode collisions on
        # existing target stock.location rows. Rows already bound by (name,
        # company) in v0.0.7 keep their binding (xmlid-existence skip at
        # line 51-53 below).
        self._jinasena_stock_bind_one(
            model='stock.warehouse',
            csv_path=os.path.join(data_dir, 'stock.warehouse.csv'),
            match_fields=[('code', 'code'), ('company_id', 'company_id/id')],
        )
        # v0.0.9: stock.location bind — two-pass strategy.
        # Pass 1: for rows with non-empty barcode, bind by (barcode, company_id).
        # These correspond to Odoo-auto-created WH/Stock etc. locations whose
        # (barcode, company_id) is enforced UNIQUE by stock_location_barcode_company_uniq.
        # Avoids chicken-and-egg where parent location_id xmlid isn't bound yet.
        # Pass 2: remaining (barcode-less) rows bind by (name, location_id, company_id).
        self._jinasena_stock_bind_one(
            model='stock.location',
            csv_path=os.path.join(data_dir, 'stock.location.csv'),
            match_fields=[('barcode', 'barcode'), ('company_id', 'company_id/id')],
            skip_rows_lacking=['barcode'],
        )
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
    def _jinasena_stock_bind_one(self, model, csv_path, match_fields, skip_rows_lacking=None):
        if not os.path.exists(csv_path):
            _logger.warning('[%s] CSV missing: %s', MODULE, csv_path)
            return
        skip_rows_lacking = skip_rows_lacking or []
        IMD = self.sudo()
        Model = self.env[model].sudo()
        bound = 0
        skipped_existing = 0
        for row in _read_csv(csv_path):
            xmlid = row.get('id')
            if not xmlid:
                continue
            # v0.0.9: skip rows missing a required CSV column (e.g. no barcode)
            if any(not row.get(col, '') for col in skip_rows_lacking):
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
