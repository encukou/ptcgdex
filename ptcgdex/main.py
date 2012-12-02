"""Manage the PTCG extension to the veekun pokedex

Usage:
    ptcgdex [options] help
    ptcgdex [options] setup [-x | --no-pokedex]
    ptcgdex [options] load [<table-or-set-name> ...]
    ptcgdex [options] dump [--sets | --csv] [<table-or-set-identifier> ...]

Commands:
    help: Does just what you'd expect.
    setup: Combine `pokedex load` and `ptcgdex load`. For more control,
        run these commands separately.
    load: Load PTCGdex files.
    dump: Dump the PTCGdex database back into files. Useful for developers.

Global options:
    -h --help               Display this help

    -q --quiet              Don't print nonessential output
    -v --verbose            Be verbose (default)

Load/dump options:
    -e --engine-uri URI     The database location (default: $POKEDEX_DB_ENGINE,
                                or a SQLite DB in the pokedex directory)
    -d --dex-csv-dir DIR    Directory containing the pokedex CSV files
    -c --ptcg-csv-dir DIR   Directory containing the ptcgdex CSV files
    -s --card-dir DIR        Directory containing the ptcgdex card files

    -D --drop-tables        Drop existing tables before loading (default for
                                setup)
    -S --safe               Disable engine-specific optimizations.

Setup options:
    -x --no-pokedex         Do not touch base pokedex tables when loading

Dump options:
    --sets                  Only dump card files
    --csv                   Only dump CSV files
"""

import os
import sys

from docopt import docopt


def make_session(options):
    class DummyDexOptions(object):
        engine_uri = options['--engine-uri']
        verbose = options['--verbose']

    from pokedex import main as dex_main
    return dex_main.get_session(DummyDexOptions)

def all_tables(tcg_tables):
    result = list(tcg_tables)
    for table in tcg_tables:
        result.extend(table.translation_classes)
    return result


def load(session, options):
    from ptcgdex import tcg_tables
    from ptcgdex import load as ptcg_load
    from pokedex.db import load as dex_load
    tcg_tables = [c.__tablename__ for c in all_tables(tcg_tables.tcg_classes)]
    table_names = options['<table-or-set-name>']
    sets = []
    if table_names:
        tcg_table_set = set(tcg_tables)
        tables = []
        for tablename in table_names:
            tcg_tablename = 'tcg_' + tablename
            if tablename in tcg_table_set:
                tables.append(tablename)
            elif tcg_tablename in tcg_table_set:
                tables.append(tcg_tablename)
            else:
                sets.append(tablename)
    else:
        tables = tcg_tables
        sets = None

    if tables:
        dex_load.load(session,
            directory=options['--ptcg-csv-dir'],
            drop_tables=options['--drop-tables'],
            tables=tables,
            verbose=options['--verbose'],
            safe=options['--safe'],
            recursive=False,
            langs=[])

    ptcg_load.load_sets(session,
        directory=options['--card-dir'],
        set_names=sets)


def dump(session, options):
    from ptcgdex import tcg_tables
    from pokedex.db import load as dex_load
    tables = options['<table-or-set-identifier>']
    if not tables:
        if options['--csv']:
            csv_tables = tcg_tables.tcg_classes
        else:
            csv_tables = [t for t in tcg_tables.tcg_classes
                    if getattr(t, 'load_from_csv', False)]
        tables = [c.__tablename__ for c in all_tables(csv_tables)]

    dex_load.dump(session,
        directory=options['--ptcg-csv-dir'],
        tables=tables,
        verbose=options['--verbose'],
        langs=['en'])


def main(argv=None):
    if argv is None:
        argv = sys.argv

    options = docopt(__doc__, argv=argv[1:])

    if not options['--verbose'] and not options['--quiet']:
        options['--verbose'] = True

    if not options['--ptcg-csv-dir']:
        options['--ptcg-csv-dir'] = os.path.join(
            os.path.dirname(__file__), 'data', 'csv')
    if not options['--card-dir']:
        options['--card-dir'] = os.path.join(
            os.path.dirname(__file__), 'data', 'cards')

    if options['help']:
        print __doc__

    elif options['setup']:
        from pokedex.db import load as dex_load
        session = make_session(options)
        if not options['--no-pokedex']:
            dex_load.load(session,
                directory=options['--dex-csv-dir'],
                drop_tables=True,
                verbose=options['--verbose'],
                safe=options['--safe'])
        load(session, options)

    elif options['load']:
        session = make_session(options)
        load(session, options)

    elif options['dump']:
        session = make_session(options)
        dump(session, options)

    else:
        exit('Subcommand not supported yet')
