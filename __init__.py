# -*- coding: utf-8 -*-
"""Jinasena_MasterData_Stock — pre-init hook binds our xmlids to existing rows.

Odoo auto-creates stock.warehouse rows when each company is created; those rows
have no xmlid and collide with our CSV inserts on the (name, company_id) unique
constraint. Same happens with stock.location's (name, company_id, location_id)
constraint for auto-created / seeded rows.

The hook scans our data CSVs before install and registers our xmlids against
matching existing DB rows via ir.model.data. Downstream CSV load then treats
those rows as UPDATE (no INSERT, no conflict).
"""
import csv
import logging
import os
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODULE = 'Jinasena_MasterData_Stock'
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def _resolve_xmlid_to_id(env, ref):
    """Resolve 'module.name' xmlid to its res_id, or return None."""
    if not ref or '.' not in ref:
        return None
    try:
        return env.ref(ref).id
    except Exception:
        return None


def _bind_existing(env, model, csv_path, match_fields):
    """Read CSV, look up rows in DB by match_fields values, register xmlids."""
    if not os.path.exists(csv_path):
        return
    IMD = env['ir.model.data'].sudo()
    Model = env[model].sudo()
    bound = 0
    with open(csv_path, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            xmlid = row.get('id')
            if not xmlid:
                continue
            # Skip if this xmlid already exists (module upgrade)
            existing = IMD.search([('module', '=', MODULE), ('name', '=', xmlid)], limit=1)
            if existing:
                continue
            # Build the domain from match_fields
            domain = []
            skip = False
            for fld, csv_col in match_fields:
                val = row.get(csv_col)
                if csv_col.endswith('/id'):
                    resolved = _resolve_xmlid_to_id(env, val)
                    if resolved is None and val:
                        skip = True
                        break
                    domain.append((fld, '=', resolved))
                else:
                    domain.append((fld, '=', val or False))
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
    if bound:
        _logger.info('[%s] pre-bound %s existing %s rows to our xmlids', MODULE, bound, model)


def pre_init_hook(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _bind_existing(env, 'stock.warehouse',
                   os.path.join(DATA_DIR, 'stock.warehouse.csv'),
                   [('name', 'name'), ('company_id', 'company_id/id')])
    _bind_existing(env, 'stock.location',
                   os.path.join(DATA_DIR, 'stock.location.csv'),
                   [('name', 'name'),
                    ('company_id', 'company_id/id'),
                    ('location_id', 'location_id/id')])
