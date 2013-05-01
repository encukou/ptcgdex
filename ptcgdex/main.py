"""Manage the PTCG extension to the veekun pokedex

Usage:
    ptcgdex [options] help
    ptcgdex [options] setup [-x | --no-pokedex]
    ptcgdex [options] load [<table-name> ...]
    ptcgdex [options] dump [--all] [<table-identifier> ...]
    ptcgdex [options] import [<file> ...]
    ptcgdex [options] export-card [--all | <print-id> ...]
    ptcgdex [options] export-set [--all | <set-identifier> ...]

Commands:
    help: Does just what you'd expect.
    setup: Combine `pokedex load` and `ptcgdex load`. For more control,
        run these commands separately.
    load: Load PTCGdex CSV files.
    dump: Dump the database into CSV files. Useful for developers.
    import: Import cards from YAML files. If no file is given, imports from
        standard input
    export-card: Export cards in a YAML format. Writes to stdout. 
    export-set: Export whole sets in a YAML format. Writes to stdout. 

Global options:
    -h --help               Display this help

    -q --quiet              Don't print nonessential output
    -v --verbose            Be verbose (default)
       --display-sql        Display SQL statements as they're executed

Load/dump options:
    -e --engine-uri URI     The database location (default: $POKEDEX_DB_ENGINE,
                                or a SQLite DB in the pokedex directory)
    -d --dex-csv-dir DIR    Directory containing the pokedex CSV files
    -c --ptcg-csv-dir DIR   Directory containing the ptcgdex CSV files

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
    from pokedex import defaults, db

    engine_uri = options['--engine-uri']
    got_from = 'command line'

    if engine_uri is None:
        engine_uri, got_from = defaults.get_default_db_uri_with_origin()

    engine_args = {}
    if options['--display-sql']:
        engine_args['echo'] = True

    session = db.connect(engine_uri, engine_args=engine_args)

    if options['--verbose']:
        print >>sys.stderr, (
            "Connected to database %(engine)s (from %(got_from)s)" %
                dict(engine=session.bind.url, got_from=got_from))

    return session

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
    table_names = options['<table-name>']
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


def dump(session, options):
    from ptcgdex import tcg_tables
    from pokedex.db import load as dex_load
    from ptcgdex import load as ptcg_load
    tables = options['<table-identifier>']
    if options['--all']:
        tables = [t.__tablename__ for t in all_tables(tcg_tables.tcg_classes)]
    elif not tables:
        csv_classes = [t for t in tcg_tables.tcg_classes
                if getattr(t, 'load_from_csv', False)]
        tables = [t.__tablename__ for t in all_tables(csv_classes)]

    dex_load.dump(session,
        directory=options['--ptcg-csv-dir'],
        tables=tables,
        verbose=options['--verbose'],
        langs=['en'])


def import_(session, options):
    from ptcgdex import load as ptcg_load
    def _load(f, label, name=None):
        ptcg_load.import_(session, f, label, name, verbose=options['--verbose'])
    if not options['<file>']:
        _load(sys.stdin, 'stdin')

    if session.connection().dialect.name == 'sqlite':
        session.connection().execute("PRAGMA synchronous=OFF")
        session.connection().execute("PRAGMA journal_mode=OFF")

    for filename in options['<file>']:
        with open(filename) as f:
            identifier, ext = os.path.splitext(os.path.basename(filename))
            _load(f, filename, identifier)

    if session.connection().dialect.name == 'sqlite':
        session.connection().execute("PRAGMA integrity_check")


def export(session, options):
    from ptcgdex import tcg_tables
    from ptcgdex import load as ptcg_load
    from pokedex.db import util
    prints = []
    for print_id in options['<print-id>']:
        prints.append(util.get(session, tcg_tables.Print, id=int(print_id)))
    if options['--all']:
        prints = session.query(tcg_tables.Print)
    for tcg_print in prints:
        print ptcg_load.yaml_dump(ptcg_load.export_print(tcg_print)),


def export_set(session, options):
    from ptcgdex import tcg_tables
    from ptcgdex import load as ptcg_load
    from pokedex.db import util
    sets = []
    for set_ident in options['<set-identifier>']:
        sets.append(util.get(session, tcg_tables.Set, set_ident))
    if options['--all']:
        sets = session.query(tcg_tables.Set)
    for tcg_set in sets:
        print ptcg_load.yaml_dump(ptcg_load.export_set(tcg_set)),


def main(argv=None):
    if argv is None:
        argv = sys.argv

    options = docopt(__doc__, argv=argv[1:])

    if not options['--verbose'] and not options['--quiet']:
        if options['export-card'] or options['export-set']:
            options['--verbose'] = False
        else:
            options['--verbose'] = True

    if not options['--ptcg-csv-dir']:
        options['--ptcg-csv-dir'] = os.path.join(
            os.path.dirname(__file__), 'data', 'csv')

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

    elif options['import']:
        session = make_session(options)
        import_(session, options)

    elif options['export-card']:
        session = make_session(options)
        export(session, options)

    elif options['export-set']:
        session = make_session(options)
        export_set(session, options)

    else:
        exit('Subcommand not supported yet')
