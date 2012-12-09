# Encoding: UTF-8
from __future__ import division, unicode_literals

import os
import time
import re
from collections import namedtuple

import yaml
from sqlalchemy.orm.exc import NoResultFound
from pokedex.db import tables as dex_tables
from pokedex.db import load as dex_load
from pokedex.db import util, multilang

from ptcgdex import tcg_tables

NOTHING = object()

card_class_idents = dict(
    P='pokemon',
    T='trainer',
    E='energy',
)

class Loader(yaml.Loader):
    pass

def construct_yaml_str(self, node):
    """String handling function to always return unicode objects

    http://stackoverflow.com/questions/2890146/
    """
    return self.construct_scalar(node)

Loader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)


def assert_empty(dct):
    """Assert an info dict is empty"""
    # Popping data from a dict and then checking everything was popped is a
    # good way to ensure that we process everything we have.
    if dct:
        print
        print '-ERROR-'
        print yaml.safe_dump(dct)
        raise ValueError(
            'Unprocessed keys: {}'.format(dct.keys()))


ObjectInfo = namedtuple('ObjectInfo', 'cls attributes')

def export_mechanic(mechanic):
    effect = mechanic.effect
    mech = dict(
            type=mechanic.class_.identifier,
            name=mechanic.name,
            cost=mechanic.cost_string,
            text=effect.source_text if effect else None,
            damage='{}{}'.format(
                mechanic.damage_base or '',
                mechanic.damage_modifier or '')
        )
    return {k: v for k, v in mech.items() if v}

def load_sets(session, directory, set_names=None, verbose=True):
    def type_by_initial(initial):
        query = session.query(tcg_tables.TCGType)
        query = query.filter_by(initial=initial)
        return query.one()

    prints = dex_load._get_verbose_prints(verbose)
    print_start, print_status, print_done = prints

    en = session.query(dex_tables.Language).get(session.default_language_id)

    if set_names is None:
        set_names = [n for [n] in session.query(tcg_tables.Set.identifier)]
    for set_ident in set_names:
        tcg_set = util.get(session, tcg_tables.Set, set_ident)
        print_start(tcg_set.name)
        with open(os.path.join(directory, set_ident + '.cards')) as infile:
            cards = list(yaml.load_all(infile, Loader=Loader))

        for card_index, card_info in enumerate(cards):

            assert tcg_set.identifier == card_info.pop('set')
            print_status('{}/{}'.format(card_index, len(cards)))

            # Exists already? Remove it
            query = session.query(tcg_tables.Print)
            query = query.filter(tcg_tables.Print.set == tcg_set)
            query = query.filter(tcg_tables.Print.set_number == card_info['number'])
            try:
                previous = query.one()
            except NoResultFound:
                pass
            else:
                session.delete(previous)

            # Card bits
            card_name = card_info.pop('name')

            if 'stage' in card_info:
                stage = util.get(session, tcg_tables.Stage,
                                 name=card_info.pop('stage'))
            else:
                stage = None
            card_class = util.get(session, tcg_tables.Class,
                                  card_class_idents[card_info.pop('class')])
            hp = card_info.pop('hp', None)
            retreat_cost = card_info.pop('retreat', None)

            resistance = card_info.pop('resistance', None)
            if not resistance or resistance == 'None':
                resistance_type = None
            else:
                resistance_type = type_by_initial(resistance)

            card_types = tuple(
                util.get(session, tcg_tables.TCGType, name=t) for t in
                    card_info.pop('types', ()))

            weak_info = card_info.pop('weakness', None)

            if 'subclass' in card_info:
                card_subclass = util.get(session, tcg_tables.Subclass,
                                         name=card_info.pop('subclass'))
            else:
                card_subclass = None

            # Find/make corresponding card
            query = session.query(tcg_tables.Card)
            query = query.filter(tcg_tables.Card.stage == stage)
            query = query.filter(tcg_tables.Card.hp == hp)
            query = query.filter(tcg_tables.Card.class_ == card_class)
            query = query.filter(tcg_tables.Card.retreat_cost == retreat_cost)
            query = query.filter(tcg_tables.Card.resistance_type == resistance_type)
            query = util.filter_name(query, tcg_tables.Card, card_name, en)
            for card in query.all():
                if card.types != card_types:
                    continue
                mechanics = [export_mechanic(m.mechanic) for m
                        in card.card_mechanics]
                if mechanics != card_info['mechanics']:
                    continue
                # TODO: weak_info
                # TODO: card_subclass
                break
            else:
                card = None
            if not card:
                card = tcg_tables.Card()
                card.name_map[en] = card_name
                card.stage = stage
                card.class_ = card_class
                card.hp = hp
                card.retreat_cost = retreat_cost
                card.resistance_type = resistance_type
                session.add(card)
                for index, mechanic_info in enumerate(
                        card_info.pop('mechanics', ())):
                    # Mechanic bits
                    mechanic_name = mechanic_info.pop('name', None)
                    effect = mechanic_info.pop('text', None)
                    cost_string = mechanic_info.pop('cost', '')
                    mechanic_class = util.get(
                        session, tcg_tables.MechanicClass,
                        mechanic_info.pop('type'))
                    damage = mechanic_info.pop('damage', None)

                    # Find/make mechanic
                    query = session.query(tcg_tables.Mechanic)
                    if mechanic_name:
                        query = util.filter_name(query, tcg_tables.Mechanic,
                                         mechanic_name, en)
                    if effect:
                        query = util.filter_name(query, tcg_tables.Mechanic,
                                         effect, en, name_attribute='effect',
                                         names_table_name='effects_table')
                    query = query.filter(tcg_tables.Mechanic.class_ == mechanic_class)
                    for mechanic in query.all():
                        if export_mechanic(mechanic) == mechanic_info:
                            break
                    else:
                        mechanic = None
                    if not mechanic:
                        mechanic = tcg_tables.Mechanic()
                        mechanic.name_map[en] = mechanic_name
                        mechanic.effect_map[en] = effect
                        mechanic.class_ = mechanic_class

                        cost_list = list(cost_string)
                        while cost_list:
                            cost = tcg_tables.MechanicCost()
                            initial = cost_list[0]
                            cost.type = type_by_initial(initial)
                            cost.amount = 0
                            while cost_list and cost_list[0] == initial:
                                cost.amount += 1
                                del cost_list[0]
                            cost.mechanic = mechanic
                            session.add(cost)

                        if damage:
                            if damage.endswith(('+', '-', '?', '×')):
                                mechanic.damage_modifier = damage[-1]
                                damage = damage[:-1]
                            if damage:
                                mechanic.damage_base = int(damage)

                        session.add(mechanic)

                    link = tcg_tables.CardMechanic()
                    link.card = card
                    link.mechanic = mechanic
                    link.order = index
                    session.add(link)

                    assert_empty(mechanic_info)

                for index, card_type in enumerate(card_types):
                    link = tcg_tables.CardType()
                    link.card = card
                    link.type = card_type
                    link.slot = index
                    session.add(link)

                if weak_info:
                    w_type = type_by_initial(weak_info.pop('type'))
                    weakness = tcg_tables.Weakness()
                    weakness.card = card
                    weakness.type = w_type
                    weakness.amount = weak_info.pop('amount')
                    operation = weak_info.pop('operation')
                    weakness.operation = {'x': '×'}.get(
                        operation, operation)
                    session.add(weakness)
                    assert_empty(weak_info)

                if card_subclass:
                    link = tcg_tables.CardSubclass()
                    link.card = card
                    link.subclass = card_subclass
                    session.add(link)

            # Print bits
            illustrator_name = card_info.pop('illustrator')
            try:
                illustrator = util.get(session, tcg_tables.Illustrator,
                             name=illustrator_name)
            except NoResultFound:
                illustrator = tcg_tables.Illustrator()
                illustrator.name = illustrator_name
                session.add(illustrator)
            rarity = util.get(session, tcg_tables.Rarity,
                              card_info.pop('rarity'))

            # Make the print

            card_print = tcg_tables.Print()
            card_print.card = card
            card_print.set = tcg_set
            card_print.set_number = card_info.pop('number')
            try:
                card_print.order = int(card_print.set_number)
            except ValueError:
                pass
            card_print.rarity = rarity
            card_print.illustrator = illustrator
            card_print.holographic = card_info.pop('holographic')

            dex_number = card_info.pop('dex number', None)
            if dex_number:
                flavor = tcg_tables.PokemonFlavor()
                species = util.get(session, dex_tables.PokemonSpecies,
                                        id=dex_number)
                species_name = card_info.pop('pokemon')
                if species.name != species_name:
                    raise ValueError("{!r} != {!r}".format(
                        flavor.species.name, species_name))
                feet, inches = card_info.pop('height').split("'")
                flavor.species = species
                flavor.genus_map[en] = card_info.pop('species'),
                flavor.weight = card_info.pop('weight'),
                flavor.height = int(feet) * 12 + int(inches),
                flavor.dex_entry_map[en] = card_info.pop('dex entry', None)
                card_print.flavor = flavor
            else:
                flavor = None

            session.add(card_print)

            card_info.pop('evolves from', None)  # XXX: Handle evolution
            card_info.pop('evo line', None)  # XXX: Check this somehow?
            card_info.pop('filename')  # XXX: Handle scans

            card_info.pop('legality')  # XXX: Check legality
            card_info.pop('orphan', None)  # XXX
            card_info.pop('has-variant', None)  # XXX
            card_info.pop('dated', None)  # XXX
            card_info.pop('in-set-variant-of', None)  # XXX

            session.commit()

        print_done()
