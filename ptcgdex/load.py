from pokedex.db import load as dex_load

from ptcgdex import tcg_tables

def load_sets(session, directory, set_names=None):
    if set_names is None:
        set_names = [n for [n] in session.query(tcg_tables.Set.identifier)]
    print set_names
