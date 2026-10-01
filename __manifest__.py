# -*- coding: utf-8 -*-
{
    'name': 'Jinasena : MasterData : Stock',
    'version': '17.0.0.0.9',
    'summary': 'Master-data extracted from CDB for Stock domain.',
    'description': 'Extracted from Clear-DB. Test-env master data. Edit the CSVs in data/ to add/remove rows before install.',
    'author': 'Jinasena Agricultural Machinery (Pvt) Ltd.',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'depends': [
        'BugFix-Stock',
        'Jinasena_MasterData_Common',
        'Jinasena_MasterData_Accounting',
    ],
    'data': [
        'data/00_bind_xmlids.xml',
        'data/stock.warehouse.csv',
        'data/stock.location.csv',
        'data/stock.picking.type.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
