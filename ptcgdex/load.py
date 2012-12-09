# Encoding: UTF-8
from __future__ import division, unicode_literals

import os
import time
import re
from collections import namedtuple, OrderedDict

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


class Dumper(yaml.SafeDumper):
    pass

class Text(unicode):
    def __new__(cls, value=''):
        return unicode.__new__(cls, value.replace('’', "'"))

def long_text_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='>')

def odict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())

Dumper.add_representer(Text, long_text_representer)
Dumper.add_representer(OrderedDict, odict_representer)

def yaml_dump(stuff):
    return yaml.dump(stuff,
                     default_flow_style=False,
                     Dumper=Dumper,
                     allow_unicode=True,
                     explicit_start=True,
                     width=60,
                    )


def export_mechanic(mechanic):
    effect = mechanic.effect
    mech = OrderedDict([
            ('name', mechanic.name),
            ('cost', mechanic.cost_string),
            ('damage', '{}{}'.format(
                mechanic.damage_base or '',
                mechanic.damage_modifier or '')),
            ('type', mechanic.class_.identifier),
            ('text', Text(effect.source_text) if effect else None),
        ])
    return OrderedDict([(k, v) for k, v in mech.items() if v])

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
                card.legal = card_info.pop('legal')
                session.add(card)
                for mechanic_index, mechanic_info in enumerate(
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
                        cost_index = 0
                        while cost_list:
                            cost = tcg_tables.MechanicCost()
                            initial = cost_list[0]
                            cost.type = type_by_initial(initial)
                            cost.amount = 0
                            while cost_list and cost_list[0] == initial:
                                cost.amount += 1
                                del cost_list[0]
                            cost.mechanic = mechanic
                            cost.order = cost_index
                            cost_index += 1
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
                    link.order = mechanic_index
                    session.add(link)

                for type_index, card_type in enumerate(card_types):
                    link = tcg_tables.CardType()
                    link.card = card
                    link.type = card_type
                    link.order = type_index
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
                flavor.weight = card_info.pop('weight')
                flavor.height = int(feet) * 12 + int(inches)
                flavor.dex_entry_map[en] = card_info.pop('dex entry', None)
                flavor.genus_map[en] = card_info.pop('species')
                session.add(flavor)
                card_print.pokemon_flavor = flavor
            else:
                flavor = None

            session.add(card_print)

            card_info.pop('evolves from', None)  # XXX: Handle evolution
            card_info.pop('filename')  # XXX: Handle scans

            card_info.pop('orphan', None)  # XXX
            card_info.pop('has-variant', None)  # XXX
            card_info.pop('dated', None)  # XXX
            card_info.pop('in-set-variant-of', None)  # XXX

            session.commit()

        print_done()


def dump_sets(session, directory, set_identifiers=None, verbose=True):
    sets = session.query(tcg_tables.Set).order_by(tcg_tables.Set.id).all()
    for tcg_set in sets:
        ident = tcg_set.identifier
        if set_identifiers is None or ident in set_identifiers:
            pathname = os.path.join(directory, '{}.cards'.format(ident))
            outfile = open(pathname, 'w')
            dump_set(tcg_set, outfile, verbose=verbose)

def dump_set(tcg_set, outfile, verbose=True):
    prints = dex_load._get_verbose_prints(verbose)
    print_start, print_status, print_done = prints

    print_start(tcg_set.name)

    included_keys = set(['holographic', 'legal'])

    for i, print_ in enumerate(tcg_set.prints):
        card = print_.card
        flavor = print_.pokemon_flavor
        print_status('{}/{}'.format(i, len(tcg_set.prints)))
        card_info = OrderedDict([
            ('set', tcg_set.identifier),
            ('number', print_.set_number),
            ('name', card.name),
            ('rarity', print_.rarity.identifier),
            ('holographic', print_.holographic),
            ('class', card.class_.identifier[0].upper()),
            ('types', [t.name for t in card.types]),
            ('hp', card.hp),
        ])
        if card.subclasses:
            [card_info['subclass']] = [sc.name for sc in card.subclasses]
        if card.stage:
            card_info['stage'] = card.stage.name
        card_info['legal'] = card.legal
        if flavor and flavor.species:
            card_info['pokemon'] = flavor.species.name
        card_info['mechanics'] = [export_mechanic(cm.mechanic) for cm
                                  in card.card_mechanics]

        weaknesses = []
        for w in card.weaknesses:
            weakness = (
                    ('amount', w.amount),
                    ('operation', w.operation),
                    ('type', w.type.initial),
                )
            weaknesses.append(OrderedDict([(k, v) for k, v in weakness]))
        if weaknesses:
            [card_info['weakness']] = weaknesses

        if card.resistance_type:
            card_info['resistance'] = card.resistance_type.initial
        card_info['retreat'] = card.retreat_cost

        if flavor:
            if flavor.species:
                card_info['dex number'] = flavor.species.id
            card_info['species'] = flavor.genus
            card_info['weight'] = flavor.weight
            card_info['height'] = "{}'{}".format(*divmod(flavor.height, 12))
            card_info['dex entry'] = flavor.dex_entry

        card_info['illustrator'] = print_.illustrator.name

        card_info = OrderedDict((k, v) for k, v in card_info.items()
            if v or k in included_keys)
        outfile.write(yaml_dump(card_info))

    print_done()
