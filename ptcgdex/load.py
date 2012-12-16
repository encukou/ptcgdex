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
import pokedex.db

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
        return unicode.__new__(cls, value)

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
    if mechanic.cost_string == '' and mechanic.class_.identifier == 'attack':
        mech['cost'] = '#'
    return OrderedDict([(k, v) for k, v in mech.items() if v])

def identifier_from_name(name):
    name = name.replace('!', '')
    name = name.replace('#', '')
    name = name.replace('*', 'star')
    return pokedex.db.identifier_from_name(name)

def get_family(session, en, name):
    if name == 'Ho-oh':
        # Standardize Ho-Oh capitaliation
        name = 'Ho-Oh'  # TODO
    if name.startswith('Unown'):
        # All Unown are named Unown (TODO: Hm, is that correct?)
        name = 'Unown'
    try:
        return util.get(session, tcg_tables.CardFamily,
                        name=name)
    except NoResultFound:
        family = tcg_tables.CardFamily()
        family.name_map[en] = name
        family.identifier = identifier_from_name(name)
        session.add(family)
    return family


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
            card_name = card_info.pop('name')
            print_status('{}/{} {}'.format(card_index, len(cards), card_name))

            # Exists already? Remove it
            query = session.query(tcg_tables.Print)
            query = query.filter(tcg_tables.Print.set == tcg_set)
            query = query.filter(tcg_tables.Print.set_number == card_info['number'])
            query = query.filter(tcg_tables.Print.order == card_info['order'])
            try:
                previous = query.one()
            except NoResultFound:
                pass
            else:
                for scan in previous.scans:
                    session.delete(scan)
                session.delete(previous)

            # Card bits
            if 'stage' in card_info:
                stage = util.get(session, tcg_tables.Stage,
                                 name=card_info.pop('stage'))
            else:
                stage = None
            card_class = util.get(session, tcg_tables.Class,
                                  card_class_idents[card_info.pop('class')])
            hp = card_info.pop('hp', None)
            retreat_cost = card_info.pop('retreat', None)

            resistance = card_info.pop('resistance', None)  # TODO
            if resistance and resistance.endswith('-20'):
                resistance = resistance[:-len('-20')]
                resistance_amount = 20
            elif resistance and resistance.endswith('-30'):
                resistance = resistance[:-len('-30')]
                resistance_amount = 30
            else:
                resistance_amount = 30
            if not resistance or resistance == 'None':
                resistant_types = []
            else:
                resistant_types = [type_by_initial(i) for i in resistance]

            card_types = tuple(
                util.get(session, tcg_tables.TCGType, name=t) for t in
                    card_info.pop('types', ()))

            weak_info = card_info.pop('weakness', None)

            card_family = get_family(session, en, card_name)

            # Find/make corresponding card
            query = session.query(tcg_tables.Card)
            query = query.filter(tcg_tables.Card.stage == stage)
            query = query.filter(tcg_tables.Card.hp == hp)
            query = query.filter(tcg_tables.Card.class_ == card_class)
            query = query.filter(tcg_tables.Card.retreat_cost == retreat_cost)
            query = query.filter(tcg_tables.Card.family == card_family)
            for card in query.all():
                if card.types != card_types:
                    continue
                mechanics = [export_mechanic(m.mechanic) for m
                        in card.card_mechanics]
                if mechanics != card_info['mechanics']:
                    continue
                # TODO: weak_info/resistance_types
                # TODO: card_subclass
                # TODO: evolutions
                # TODO: subclasses
                break
            else:
                card = None
            if not card:
                card = tcg_tables.Card()
                card.stage = stage
                card.class_ = card_class
                card.hp = hp
                card.retreat_cost = retreat_cost
                card.legal = card_info.pop('legal')
                card.family = card_family
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

                        if cost_string == '#':
                            cost_string = ''
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
                    weak_amount = weak_info.pop('amount')
                    weak_operation = weak_info.pop('operation')
                    weak_operation = {'x': '×'}.get(
                            weak_operation, weak_operation)
                    for w_index, initial in enumerate(weak_info.pop('type')):
                        w_type = type_by_initial(initial)
                        modifier = tcg_tables.DamageModifier()
                        modifier.card = card
                        modifier.type = w_type
                        modifier.amount = weak_amount
                        modifier.order = w_index
                        modifier.operation = weak_operation
                        session.add(modifier)
                else:
                    w_index = 0

                for r_index, r_type in enumerate(resistant_types,
                        start=w_index):
                    modifier = tcg_tables.DamageModifier()
                    modifier.card = card
                    modifier.type = r_type
                    modifier.amount = resistance_amount
                    modifier.order = r_index
                    modifier.operation = '-'
                    session.add(modifier)

                for subclass_index, subclass_name in enumerate(
                        card_info.pop('subclasses', ())):
                    try:
                        subclass = util.get(session, tcg_tables.Subclass,
                                            name=subclass_name)
                    except NoResultFound:
                        subclass = tcg_tables.Subclass()
                        subclass.identifier = identifier_from_name(
                            subclass_name)
                        subclass.name_map[en] = subclass_name
                        session.add(subclass)
                    link = tcg_tables.CardSubclass()
                    link.card = card
                    link.subclass = subclass
                    link.order = subclass_index
                    session.add(link)

                evolves_from = card_info.pop('evolves from', None)
                if evolves_from:
                    family = get_family(session, en, evolves_from)
                    link = tcg_tables.Evolution()
                    link.card = card
                    link.family = family
                    link.order = 0
                    link.family_to_card = True
                    session.add(link)

                evolves_into = card_info.pop('evolves into', None)
                if evolves_into:
                    family = get_family(session, en, evolves_into)
                    link = tcg_tables.Evolution()
                    link.card = card
                    link.family = family
                    link.order = 0
                    link.family_to_card = False
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

            dex_number = card_info.pop('dex number', None)
            if dex_number:
                species = util.get(session, dex_tables.PokemonSpecies,
                                        id=dex_number)
            else:
                species = None

            # Make the print

            card_print = tcg_tables.Print()
            card_print.card = card
            card_print.set = tcg_set
            card_print.set_number = card_info.pop('number')
            card_print.order = card_info.pop('order')
            card_print.rarity = rarity
            card_print.illustrator = illustrator
            card_print.holographic = card_info.pop('holographic')

            scan = tcg_tables.Scan()
            scan.print_ = card_print
            scan.filename = card_info.pop('filename')
            scan.order = 0
            session.add(scan)

            session.add(card_print)

            #import pdb; pdb.set_trace()
            if dex_number or any(x in card_info for x in (
                    'height', 'weight', 'dex entry', 'species')):
                session.flush()
                flavor = tcg_tables.PokemonFlavor()
                if dex_number:
                    species_name = card_info.pop('pokemon')
                    if species.name.lower() != species_name.lower():
                        raise ValueError("{!r} != {!r}".format(
                            species.name, species_name))
                    flavor.species = species
                if 'height' in card_info:
                    feet, inches = card_info.pop('height').split("'")
                    flavor.height = int(feet) * 12 + int(inches)
                if 'weight' in card_info:
                    flavor.weight = card_info.pop('weight')
                session.add(flavor)
                session.flush()
                if any(x in card_info for x in ('dex entry', 'species')):
                    link = tcg_tables.PokemonFlavor.flavor_table()
                    link.local_language = en
                    link.tcg_pokemon_flavor_id = flavor.id
                    if 'dex entry' in card_info:
                        link.dex_entry = card_info.pop('dex entry')
                    if 'species' in card_info:
                        link.genus = card_info.pop('species')
                    session.add(link)
                card_print.pokemon_flavor = flavor
            else:
                flavor = None

            card_info.pop('orphan', None)  # XXX
            card_info.pop('has-variant', None)  # XXX
            card_info.pop('dated', None)  # XXX
            card_info.pop('in-set-variant-of', None)  # XXX

            session.flush()
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

    included_keys = set(['holographic', 'legal', 'order'])

    for i, print_ in enumerate(tcg_set.prints):
        card = print_.card
        flavor = print_.pokemon_flavor
        print_status('{}/{}'.format(i, len(tcg_set.prints)))
        card_info = OrderedDict([
            ('set', tcg_set.identifier),
            ('number', print_.set_number),
            ('order', print_.order),
            ('name', card.name),
            ('rarity', print_.rarity.identifier),
            ('holographic', print_.holographic),
            ('class', card.class_.identifier[0].upper()),
            ('types', [t.name for t in card.types]),
            ('hp', card.hp),
        ])
        if card.stage:
            card_info['stage'] = card.stage.name
        if card.evolutions:
            assert len(card.evolutions) == 1  # TODO
            for evo in card.evolutions:
                if evo.family_to_card:
                    card_info['evolves from'] = evo.family.name
                else:
                    card_info['evolves into'] = evo.family.name
        card_info['legal'] = card.legal
        [card_info['filename']] = [s.filename for s in print_.scans]
        if flavor and flavor.species:
            card_info['pokemon'] = flavor.species.name
        card_info['subclasses'] = [sc.name for sc in card.subclasses]
        card_info['mechanics'] = [export_mechanic(cm.mechanic) for cm
                                  in card.card_mechanics]

        weaknesses = []
        resistances = []
        for m in card.damage_modifiers:
            mod = (
                    ('amount', m.amount),
                    ('operation', m.operation),
                    ('type', m.type.initial),
                )
            if m.operation == '-':
                resistances.append(OrderedDict([(k, v) for k, v in mod]))
            else:
                weaknesses.append(OrderedDict([(k, v) for k, v in mod]))
        if weaknesses:
            first_weakness = weaknesses[0]
            assert all(w['amount'] == first_weakness['amount'] and
                       w['operation'] == first_weakness['operation']
                       for w in weaknesses)
            first_weakness['type'] = ''.join(w['type'] for w in weaknesses)
            card_info['weakness'] = first_weakness
        if resistances:
            first_resistance = resistances[0]
            assert all(w['amount'] == first_resistance['amount'] and
                       w['operation'] == '-'
                       for w in resistances)
            resist_string = ''.join(w['type'] for w in resistances)
            if first_resistance['amount'] != 30:
                resist_string += '-{}'.format(first_resistance['amount'])
            card_info['resistance'] = resist_string

        card_info['retreat'] = card.retreat_cost

        if flavor:
            if flavor.species:
                card_info['dex number'] = flavor.species.id
            card_info['species'] = flavor.genus
            card_info['weight'] = flavor.weight
            card_info['height'] = "{}'{}".format(*divmod(flavor.height, 12))
            card_info['dex entry'] = Text(flavor.dex_entry or '')

        card_info['illustrator'] = print_.illustrator.name

        card_info = OrderedDict((k, v) for k, v in card_info.items()
            if v or k in included_keys)
        outfile.write(yaml_dump(card_info))

    print_done()
