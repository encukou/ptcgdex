# Encoding: UTF-8
from __future__ import division, unicode_literals

import os
import time
import re

import yaml
from sqlalchemy.orm.exc import NoResultFound
from pokedex.db import tables as dex_tables
from pokedex.db import load as dex_load
from pokedex.db import util

from ptcgdex import tcg_tables

NOTHING = object()

card_class_idents = dict(
    P='pokemon',
    T='trainer',
    E='energy',
)


def assert_empty(dct):
    """Assert an info dict is empty"""
    # Popping data from a dict and then checking everything was popped is a
    # good way to ensure that we process everything we have.
    if dct:
        print
        print '-ERROR-'
        print yaml.dump(dct)
        raise ValueError(
            'Unprocessed keys: {}'.format(dct.keys()))


def load_sets(session, directory, set_names=None, verbose=True):
    def find_by_name(table, name):
        return util.get(session, table, name=name)

    prints = dex_load._get_verbose_prints(verbose)
    print_start, print_status, print_done = prints

    en = util.get(session, dex_tables.Language, 'en')

    if set_names is None:
        set_names = [n for [n] in session.query(tcg_tables.Set.identifier)]
    for set_ident in set_names:
        tcg_set = util.get(session, tcg_tables.Set, set_ident)
        print_start(tcg_set.name)
        with open(os.path.join(directory, set_ident + '.cards')) as infile:
            cards = list(yaml.load_all(infile))
        for card_index, card_info in enumerate(cards):

            def pop(field, default=NOTHING):
                if default is NOTHING:
                    return card_info.pop(field)
                else:
                    return card_info.pop(field, default)

            def pop_to(field_name, dest, attr_name=None, convertor=None):
                value = pop(field_name, NOTHING)
                if value is not NOTHING:
                    if convertor:
                        value = convertor(value)
                    setattr(dest, attr_name or field_name, value)

            print_status('{}/{}'.format(card_index, len(cards)))

            if pop('set') != set_ident:
                raise ValueError('Card from wrong set: {}'.format(card_name))

            pop('evolves from')  # XXX: Handle evolution
            pop('evo line')  # XXX: Check this somehow?
            pop('filename')  # XXX: Handle scans

            if tcg_set.ban_date:
                if tcg_set.ban_date < tcg_set.ban_date.today():
                    legal = 'n'
                else:
                    legal = 'y'
            else:
                legal = 'y'
            if pop('legality') != legal:
                raise ValueError('Bad legality: {}'.format(card_name))

            card_class = util.get(session, tcg_tables.Class,
                                  card_class_idents[pop('class')])
            card_rarity = util.get(session, tcg_tables.Rarity, pop('rarity'))

            illustrator_name = pop('illustrator')
            try:
                illustrator = session.query(tcg_tables.Illustrator).filter_by(
                    name=illustrator_name).one()
            except NoResultFound:
                illustrator = tcg_tables.Illustrator()
                illustrator.name = illustrator_name
                session.add(illustrator)
                session.flush()

            if 'stage' in card_info:
                stage = find_by_name(tcg_tables.Stage, pop('stage'))
            else:
                stage = None

            types = [find_by_name(tcg_tables.TCGType, n) for n in pop('types')]

            resistance = pop('resistance')
            if resistance == 'None':
                resistance = None
            else:
                resistance = find_by_name(tcg_tables.TCGType, resistance)

            dex_number = pop('dex number', None)
            if dex_number:
                flavor = tcg_tables.PokemonFlavor()
                flavor.species = util.get(session, dex_tables.PokemonSpecies,
                                          id=dex_number)
                assert flavor.species.name == pop('pokemon')
                species = pop('species')
                if species != flavor.species.genus:
                    flavor.species_map[en] = species
                flavor.weight = pop('weight')
                feet, inches = pop('height').split("'")
                flavor.height = int(feet) * 12 + int(inches)
                flavor.dex_entry_map[en] = pop('dex entry')

            mechanics = []
            for order, mechanic_info in enumerate(pop('mechanics')):
                mech_type = util.get(session, tcg_tables.MechanicClass,
                                     mechanic_info.pop('type'))
                mechanic = tcg_tables.Mechanic()
                mechanic.effect_map[en] = mechanic_info.pop('text')
                if 'name' in mechanic_info:
                    mechanic.name_map[en] = mechanic_info.pop('name')
                if 'damage' in mechanic_info:
                    damage = mechanic_info.pop('damage')
                    mechanic.damage_base = int(damage)
                if 'cost' in mechanic_info:
                    cost_string = list(mechanic_info.pop('cost'))
                    while cost_string:
                        cost = tcg_tables.MechanicCost()
                        initial = cost_string[0]
                        cost.type = session.query(tcg_tables.TCGType
                            ).filter_by(initial=initial).one()
                        cost.amount = 0
                        while cost_string and cost_string[0] == initial:
                            cost.amount += 1
                            del cost_string[0]
                        cost.mechanic = mechanic
                assert_empty(mechanic_info)
                mechanics.append(mechanic)

            weak_info = pop('weakness')
            if weak_info:
                weakness = tcg_tables.Weakness()
                weakness.type = session.query(tcg_tables.TCGType
                    ).filter_by(initial=weak_info.pop('type')).one()
                weakness.amount = weak_info.pop('amount')
                operation = weak_info.pop('operation')
                weakness.operation = {'x': '×'}.get(operation, operation)
                assert_empty(weak_info)
            else:
                weakness = None

            card = tcg_tables.Card()
            card_name = pop('name')
            card.name_map[en] = card_name

            pop_to('hp', card, convertor=int)
            card.stage = stage
            card.types = types
            card.class_ = card_class
            card.rarity = card_rarity
            pop_to('holographic', card)
            pop_to('retreat', card, 'retreat_cost')
            for mechanic in mechanics:
                mechanic.card = card
            if weakness:
                weakness.card = card
            card.resistance_type = resistance

            card_print = tcg_tables.Print()
            card_print.set = tcg_set
            pop_to('number', card_print, 'set_number')
            card_print.order = int(card_print.set_number)

            card_print.card = card
            card_print.illustrator = illustrator
            card_print.pokemon_flavor = flavor

            assert_empty(card_info)

            session.add(card)
            session.add(card_print)
            session.flush()
        session.commit()
        print_done()
