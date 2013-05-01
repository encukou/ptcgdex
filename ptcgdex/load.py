# Encoding: UTF-8
from __future__ import division, unicode_literals

import os
import time
import re
from collections import namedtuple, OrderedDict
from datetime import datetime

import yaml
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import (
    joinedload, joinedload_all, subqueryload, subqueryload_all)
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
                     width=68,
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
    name = name.replace('&', '')
    name = name.replace('?', 'question')
    name = name.replace('#', '')
    name = name.replace('*', 'star')
    name = name.replace('δ', 'delta')
    return pokedex.db.identifier_from_name(name)

def get_family(session, en, name):
    if name == 'Ho-oh':
        # Standardize Ho-Oh capitaliation
        name = 'Ho-Oh'  # TODO
    try:
        return util.get(session, tcg_tables.CardFamily,
                        name=name)
    except NoResultFound:
        family = tcg_tables.CardFamily()
        family.name_map[en] = name
        family.identifier = identifier_from_name(name)
        session.add(family)
    return family

def get_illustrator(session, en, name):
    identifier = identifier_from_name(name)
    try:
        return util.get(session, tcg_tables.Illustrator, identifier)
    except NoResultFound:
        entity = tcg_tables.Illustrator()
        entity.name = name
        entity.identifier = identifier
        session.add(entity)
    return entity


def assert_dicts_equal(a, b):
    if a != b:
        for key in sorted(set(a) | set(b)):
            ai, bi = a.get(key, '<missing>'), b.get(key, '<missing>')
            if ai != bi:
                print yaml_dump({key: [ai, bi]})
        assert a == b

def import_(session, fileobj, label, identifier=None, verbose=True):
    prints = dex_load._get_verbose_prints(verbose)
    print_start, print_status, print_done = prints
    print_start(label)
    infos = list(yaml.safe_load_all(fileobj))
    def _status_printer(x):
        if len(infos) == 1:
            print_status(x)
        else:
            print_status('{}/{} {}'.format(i, len(infos), x))
    for i, info in enumerate(infos):
        if 'cards' in info:
            import_set(session, info, identifier, _status_printer)
        else:
            _status_printer(info.get('name'))
            import_print(session, info, do_commit=False)
    session.commit()
    print_done()


def import_set(session, info, identifier=None, print_status=None):
    tcg_set = tcg_tables.Set()
    en = session.query(dex_tables.Language).get(session.default_language_id)
    if 'name' in info:
        tcg_set.name_map[en] = info['name']
        identifier = identifier_from_name(info['name'])
    else:
        tcg_set.name_map[en] = identifier
    if identifier is None:
        tcg_set = None
    else:
        try:
            value = info['release date']
        except KeyError:
            pass
        else:
            tcg_set.release_date = datetime.strptime(value, "%Y-%m-%d").date()

        try:
            value = info['modified ban date']
        except KeyError:
            pass
        else:
            tcg_set.ban_date = datetime.strptime(value, "%Y-%m-%d").date()

        try:
            value = info['total']
        except KeyError:
            pass
        else:
            tcg_set.total = value

        tcg_set.identifier = identifier
        session.add(tcg_set)
        session.flush()
    for i, c_info in enumerate(info['cards']):
        card = c_info['card']
        print_status('{}/{} {}'.format(i, len(info['cards']), card['name']))
        print_ = import_print(session, card, do_commit=False)
        if tcg_set:
            link = tcg_tables.SetPrint(
                print_=print_,
                set=tcg_set,
                order=i,
            )
            if 'number' in c_info:
                link.number = c_info['number']
            session.add(link)


def import_card(session, card_info):
    def type_by_initial(initial):
        query = session.query(tcg_tables.TCGType)
        query = query.filter_by(initial=initial)
        return query.one()

    en = session.query(dex_tables.Language).get(session.default_language_id)
    card_name = card_info['name']

    if 'stage' in card_info:
        stage = util.get(session, tcg_tables.Stage,
                            name=card_info.get('stage'))
    else:
        stage = None
    if card_info.get('class'):
        card_class = util.get(session, tcg_tables.Class,
                            card_class_idents[card_info.get('class')])
    else:
        card_class = None
    hp = card_info.get('hp', None)
    retreat_cost = card_info.get('retreat', None)

    card_types = tuple(
        util.get(session, tcg_tables.TCGType, name=t) for t in
            card_info.get('types', ()))

    damage_mod_info = card_info.get('damage modifiers', [])

    card_family = get_family(session, en, card_name)

    # Find/make corresponding card
    query = session.query(tcg_tables.Card)
    query = query.filter(tcg_tables.Card.stage == stage)
    query = query.filter(tcg_tables.Card.hp == hp)
    query = query.filter(tcg_tables.Card.class_ == card_class)
    query = query.filter(tcg_tables.Card.retreat_cost == retreat_cost)
    query = query.filter(tcg_tables.Card.family == card_family)

    query = query.options(joinedload('family'))
    query = query.options(joinedload_all('card_types.type.names'))
    query = query.options(subqueryload_all('card_mechanics.mechanic.names'))
    query = query.options(subqueryload_all('card_subclasses.subclass.names'))
    card_query = query
    for card in card_query.all():
        if card.types != card_types:
            continue
        mnames = [m.mechanic.name for m in card.card_mechanics]
        if mnames != [m.get('name') for m in card_info.get('mechanics', [])]:
            continue
        if card_info == export_card(card):
            return card

    # No card found, make a new one
    card = tcg_tables.Card()
    card.stage = stage
    card.class_ = card_class
    card.hp = hp
    card.retreat_cost = retreat_cost
    card.legal = card_info.get('legal', False)
    card.family = card_family
    session.add(card)
    for mechanic_index, mechanic_info in enumerate(
            card_info.get('mechanics', ())):
        # Mechanic bits
        mechanic_name = mechanic_info.get('name', None)
        effect = mechanic_info.get('text', None)
        cost_string = mechanic_info.get('cost', '')
        mechanic_class = util.get(
            session, tcg_tables.MechanicClass,
            mechanic_info.get('type'))
        damage = mechanic_info.get('damage', None)

        # Find/make mechanic
        query = session.query(tcg_tables.Mechanic)
        if mechanic_name:
            query = util.filter_name(query, tcg_tables.Mechanic,
                                mechanic_name, en)
        if effect:
            query = query.filter(tcg_tables.Mechanic.effect == effect)
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

    for dm_index, dm_info in enumerate(damage_mod_info):
        dm_type = util.get(session, tcg_tables.TCGType,
            name=dm_info.get('type'))
        modifier = tcg_tables.DamageModifier()
        modifier.card = card
        modifier.type = dm_type
        modifier.amount = dm_info.get('amount')
        modifier.order = dm_index
        modifier.operation = dm_info.get('operation')
        session.add(modifier)
        session.flush()

    for subclass_index, subclass_name in enumerate(
            card_info.get('subclasses', ())):
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

    for evolves_from in card_info.get('evolves from', []):
        family = get_family(session, en, evolves_from)
        link = tcg_tables.Evolution()
        link.card = card
        link.family = family
        link.order = 0
        link.family_to_card = True
        session.add(link)

    for evolves_into in card_info.get('evolves into', []):
        family = get_family(session, en, evolves_into)
        link = tcg_tables.Evolution()
        link.card = card
        link.family = family
        link.order = 0
        link.family_to_card = False
        session.add(link)

    # TODO: make sure we actually roundtrip!
    #assert_dicts_equal(card_info, export_card(card))

    return card


def import_print(session, card_info, do_commit=True):
    en = session.query(dex_tables.Language).get(session.default_language_id)

    card_name = card_info['name']

    card = import_card(session,
        {k: v for k, v in card_info.items() if k in CARD_EXPORT_KEYS})

    # Print bits
    illustrator_names = card_info.get('illustrators', ())
    if 'illustrator' in card_info:
        illustrators.append(card_info.get('illustrator'))
    illustrators = [get_illustrator(session, en, name)
        for name in illustrator_names]

    if card_info.get('rarity'):
        rarity = util.get(session, tcg_tables.Rarity,
                            card_info.get('rarity'))
    else:
        rarity = None

    dex_number = card_info.get('dex number', None)
    if dex_number:
        species = util.get(session, dex_tables.PokemonSpecies,
                                id=dex_number)
    else:
        species = None

    # Make the print

    card_print = tcg_tables.Print()
    card_print.card = card
    card_print.rarity = rarity
    card_print.holographic = card_info.get('holographic')

    scan = tcg_tables.Scan()
    scan.print_ = card_print
    scan.filename = card_info.get('filename')
    scan.order = 0
    session.add(scan)

    session.add(card_print)

    for i, illustrator in enumerate(illustrators):
        link = tcg_tables.PrintIllustrator()
        link.print_ = card_print
        link.illustrator = illustrator
        link.order = i
        session.add(link)

    if dex_number or any(x in card_info for x in (
            'height', 'weight', 'dex entry', 'species')):
        session.flush()
        flavor = tcg_tables.PokemonFlavor()
        if dex_number:
            species_name = card_info.get('pokemon')
            if species.name.lower() != species_name.lower():
                raise ValueError("{!r} != {!r}".format(
                    species.name, species_name))
            flavor.species = species
        if 'height' in card_info:
            feet, inches = card_info.get('height').split("'")
            flavor.height = int(feet) * 12 + int(inches)
        if 'weight' in card_info:
            flavor.weight = card_info.get('weight')
        session.add(flavor)
        session.flush()
        if any(x in card_info for x in ('dex entry', 'species')):
            link = tcg_tables.PokemonFlavor.flavor_table()
            link.local_language = en
            link.tcg_pokemon_flavor_id = flavor.id
            if 'dex entry' in card_info:
                link.dex_entry = card_info.get('dex entry')
            if 'species' in card_info:
                link.genus = card_info.get('species')
            session.add(link)
        card_print.pokemon_flavor = flavor
    else:
        flavor = None

    card_info.pop('orphan', None)  # XXX
    card_info.pop('has-variant', None)  # XXX
    card_info.pop('dated', None)  # XXX
    card_info.pop('in-set-variant-of', None)  # XXX

    session.flush()

    # TODO: make sure we actually roundtrip!
    # assert_dicts_equal(card_info, export_print(card_print))

    if do_commit:
        session.commit()

    return card_print


def export_set(tcg_set):
    result = OrderedDict()
    if tcg_set.name:
        result['name'] = tcg_set.name
    if tcg_set.total is not None:
        result['total'] = tcg_set.total
    if tcg_set.release_date:
        result['release date'] = tcg_set.release_date.isoformat()
    if tcg_set.ban_date:
        result['modified ban date'] = tcg_set.ban_date.isoformat()
    result['cards'] = []
    for set_print in tcg_set.set_prints:
        res = OrderedDict()
        result['cards'].append(res)
        if set_print.number is not None:
            res['number'] = set_print.number
        res['card'] = export_print(set_print.print_)
    return result

def make_ordered_dict(data, key_order, always_included_keys=[]):
    items = [(k, v) for k, v in data.items() if v or k in always_included_keys]
    items.sort(key=lambda k_v: key_order.index(k_v[0]))
    return OrderedDict(items)

CARD_EXPORT_KEYS = [
    'name', 'class', 'types', 'hp', 'stage', 'evolves from', 'evolves to',
    'legal', 'subclasses', 'mechanics', 'damage modifiers',
    'retreat',
]

INCLUDED_KEYS = set(['holographic', 'legal', 'order'])

def export_card(card):
    card_info = {
        'name': card.name,
        'hp': card.hp,
        'legal': card.legal,
        'types': [t.name for t in card.types],
        'subclasses': [sc.name for sc in card.subclasses],
        'mechanics': [export_mechanic(cm.mechanic) for cm
                                    in card.card_mechanics],
        'retreat': card.retreat_cost,
    }
    if card.class_:
        card_info['class'] = card.class_.identifier[0].upper()
    if card.stage:
        card_info['stage'] = card.stage.name
    card_info['damage modifiers'] = damage_mods = []
    for m in card.damage_modifiers:
        damage_mods.append(OrderedDict([
                ('amount', m.amount),
                ('operation', m.operation),
                ('type', m.type.name),
            ]))
    if card.evolutions:
        assert len(card.evolutions) == 1  # TODO
        for evo in card.evolutions:
            if evo.family_to_card:
                collection = 'evolves from'
            else:
                collection = 'evolves into'
            card_info.setdefault(collection, []).append(evo.family.name)
    return make_ordered_dict(card_info, CARD_EXPORT_KEYS, INCLUDED_KEYS)

PRINT_EXPORT_KEYS = [
    'name', 'rarity', 'holographic', 'class',
    'types', 'hp', 'stage', 'evolves from', 'evolves to', 'legal',
    'filename', 'pokemon', 'subclasses', 'mechanics', 'damage modifiers',
    'retreat', 'dex number', 'species', 'weight', 'height', 'dex entry',
    'illustrators',
]

def export_print(print_):
    print_info = export_card(print_.card)
    flavor = print_.pokemon_flavor
    print_info.update({
        'holographic': print_.holographic,
        'illustrators': [il.name for il in print_.illustrators]
    })
    if print_.rarity:
        print_info['rarity'] = print_.rarity.identifier
    [print_info['filename']] = [s.filename for s in print_.scans]
    if flavor and flavor.species:
        print_info['pokemon'] = flavor.species.name

    if flavor:
        if flavor.species:
            print_info['dex number'] = flavor.species.id
        print_info['species'] = flavor.genus
        print_info['weight'] = flavor.weight
        print_info['height'] = "{}'{}".format(*divmod(flavor.height, 12))
        print_info['dex entry'] = Text(flavor.dex_entry or '')

    return make_ordered_dict(print_info, PRINT_EXPORT_KEYS, INCLUDED_KEYS)
