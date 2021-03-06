# Encoding: UTF-8
"""Usage:
  convert_csv.py [options] [<destdir>] [<infile>]

Options:
  -h, --help        Display help
  --sets-file=SETS  File with set information; default: sets.csv

infile defaults to stdin if not given.
"""

from __future__ import division, print_function, unicode_literals

import os
import io
import re
import sys
import csv
import textwrap
from contextlib import contextmanager
from collections import OrderedDict

import yaml
from docopt import docopt
from ptcgdex.load import identifier_from_name

type_initials = dict(
    Psychic = 'P',
    Water = 'W',
    Colorless = 'C',
    Fire = 'R',
    Fighting = 'F',
    Lightning = 'L',
    Grass = 'G',
    Metal = 'M',
    Darkness = 'D',
)

type_from_initial = {v: k for k, v in type_initials.items()}

class_from_initials = dict(
    P='Pokemon',
    T='Trainer',
    E='Energy',
)

def munge_errors(data):
    set_name = data['set'], data['card-name']
    if set_name == ('ex-emerald', "Farfetch'd"):
        a2cost = data.pop('attack-2-cost')
        assert a2cost == 'CC'
    elif set_name == ('mysterious-treasures', "Uxie"):
        height = data.pop('height')
        assert height == '1"00"'
        data['height'] = "1'00"
    elif set_name == ('majestic-dawn', "Croagunk"):
        height = data.pop('weight')
        assert height == '''2' 04"'''
        data['weight'] = '50.7 lbs.'
    elif set_name == ('diamond-and-pearl', "Azumarrill"):
        data['card-name'] = 'Azumarill'
        assert data['pokemon'] == 'Azumarrill'
        data['pokemon'] = 'Azumarill'
    elif set_name == ('diamond-and-pearl', "Marill"):
        assert data['dex-no.'] == '184'
        data['dex-no.'] = '183'
    elif set_name == ('mysterious-treasures', "Mantine"):
        assert data['dex-no.'] == '225'
        data['dex-no.'] = '226'
    elif set_name == ('great-encounters', "Linoone"):
        assert data['dex-no.'] == '254'
        data['dex-no.'] = '264'
    elif set_name == ('legends-awakened', "Regirock"):
        assert data['dex-no.'] == '277'
        data['dex-no.'] = '377'
    elif set_name == ('stormfront', "Mamoswine"):
        assert data['dex-no.'] == '474'
        data['dex-no.'] = '473'
    elif set_name == ('stormfront', "Voltorb") and data['dex-no.'] == '101':
        data['dex-no.'] = '100'
    elif set_name == ('mysterious-treasures', "Larivitar"):
        assert data['card-name'] == 'Larivitar'
        data['card-name'] = 'Larvitar'
        assert data['pokemon'] == 'Larivitar'
        data['pokemon'] = 'Larvitar'
    elif set_name == ('mysterious-treasures', "Celebi"):
        assert data['height'] == '2.00"', `data['height']`
        data['height'] = "2'0"
    elif set_name == ('platinum', "Scyther"):
        assert data['resist'] == 'R-30'
        data['resist'] = "F-30"
    elif set_name == ('platinum', "Pluspower"):
        data['card-name'] = "PlusPower"
    elif set_name in [
            ('platinum', "Dialga G"),
            ('platinum', "Palkia G"),
            ('platinum', "Weavile G"),
            ('platinum', "Gyarados G"),
            ('platinum', "Toxicroak G"),
            ('platinum', "Bronzong G"),
            ('platinum', "Crobat G"),
            ('platinum', "Houndoom G"),
            ('platinum', "Honchkrow G"),
            ('platinum', "Purugly G"),
            ('platinum', "Skuntank G"),
            ]:
        sp = data.pop('species')
        assert sp == "Team Galactic's"
        data['species'] = ''

    if data['pokemon'] == 'Nidoran M':
        data['pokemon'] = 'Nidoran♂'
    elif data['pokemon'] == 'Nidoran F':
        data['pokemon'] = 'Nidoran♀'
    elif data['pokemon'].startswith('Dark '):
        data['pokemon'] = data['pokemon'][len('Dark '):]
    elif data['pokemon'].startswith('Light '):
        data['pokemon'] = data['pokemon'][len('Light '):]

    if not data['class']:
        if set_name == ('legendary-collection', 'Full Heal Energy'):
            data['class'] = 'E'
        elif set_name == ('legendary-collection', 'Potion Energy'):
            data['class'] = 'E'
        elif data['set'] == 'legendary-collection' and data['num'].startswith('S'):
            data['class'] = 'P'

    if data['set'] == 'ex-team-magma-vs.-team-aqua':
        data['set'] = 'ex-team-magma-vs-team-aqua'
    elif data['set'] == 'stormfront' and data['card-name'].startswith('Poké\x81'):
        data['card-name'] = data['card-name'].replace('\x81', '')

@contextmanager
def nonempty_setter(target_dict, name, default=None):
    if default is None:
        value = []
    else:
        value = default
    yield value
    if value:
        target_dict[name] = value

def append_nonempty(lst, value):
    if value:
        lst.append(value)

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

def dump(stuff):
    return yaml.dump(stuff,
                     default_flow_style=False,
                     Dumper=Dumper,
                     allow_unicode=True,
                     explicit_start=True,
                     width=68,
                    )

def main(infile, destdir=None, names_file=None):
    if names_file is None:
        names_file = 'sets.csv'
    sets = {}
    for line in csv.DictReader(open(names_file)):
        tcg_set = sets[identifier_from_name(line['name'])] = OrderedDict()
        for field in ('name', 'total', 'release date', 'modified ban date'):
            if line[field]:
                tcg_set[field] = line[field]
        if 'total' in tcg_set:
            tcg_set['total'] = int(tcg_set['total'])
        tcg_set['cards'] = []

    if destdir and not os.path.isdir(destdir):
        raise ValueError('{} is not a directory'.format(destdir))
    for data in csv.DictReader(infile):
        data = {k: v.decode('utf-8') for k, v in data.items()}
        _orig_data = dict(data)
        munge_errors(data)
        print()
        def pop(name):
            item = data.pop(name)
            return item.strip()

        def simple_out(outname, name, convertor=None):
            arg = pop(name)
            if arg:
                if convertor:
                    arg = convertor(arg)
                result[outname] = arg

        result = OrderedDict()

        pop('1')
        tcg_set = data.pop('set')
        set_list = sets.setdefault(tcg_set or 'unknown', {'cards': []})['cards']
        name = data.pop('card-name')
        name = re.sub(r'Unown \((.)\)', r'Unown \1', name)
        result['name'] = name

        rarity = pop('rarity')
        if rarity == 'P':
            rarity = 'promo'
        rarity, holo, end = rarity.partition('-holo')
        assert not end, (rarity, holo, end)
        result['rarity'] = rarity
        result['holographic'] = bool(holo)

        simple_out('class', 'class')

        with nonempty_setter(result, 'types') as types:
            append_nonempty(types, pop('type1'))
            append_nonempty(types, pop('type2'))

        simple_out('hp', 'hp', convertor=int)

        simple_out('stage', 'stage')

        evolves_from = pop('evolves-from')
        if evolves_from:
            result['evolves from'] = [evolves_from]
        evolves_into = pop('evolves-into')
        if evolves_into:
            result['evolves into'] = [evolves_into]

        pop('evo-line')
        simple_out('legal', 'legal', convertor=lambda el: el == 'y')
        simple_out('filename', 'filename')
        simple_out('orphan', 'orphan')
        simple_out('has-variant', 'has-variant')
        simple_out('in-set-variant-of', 'in-set-variant-of')

        simple_out('dated', 'dated')
        simple_out('reprint of', 'reprint-of')
        pokemon = pop('pokemon')
        if pokemon and pokemon not in ['Mysterious Fossil']:
            result['pokemon'] = pokemon

        with nonempty_setter(result, 'subclasses') as subclasses:
            class2 = pop('class2')
            if class2:
                subclasses.append(class_from_initials[class2])
            trainer_class = pop('trainer-class')
            if trainer_class and trainer_class != 'Trainer':
                subclasses.append(trainer_class)
            names = ['trainer-sub-class', 'energy-class'] + [
                'sub-class-{}'.format(i) for i in range(1, 4)]
            for name in names:
                cls = pop(name)
                if cls:
                    subclasses.append(cls)

        with nonempty_setter(result, 'mechanics') as mechanics:
            for label, mechanic_name, extra in (
                    ('note', 'poke-note', []),
                    ('rule', 'trainer-rule', []),
                    ('effect', 'trainer-txt', []),
                    ('effect', 'energy-txt', []),
                    ('pokemon-power', 'pkmn-power-txt', [('name', 'pkmn-power-1')]),
                    ('pokepower', 'power-1-txt', [('name', 'power-1')]),
                    ('pokepower', 'power-2-txt', [('name', 'power-2')]),
                    ('pokebody', 'body-1-txt', [('name', 'body-1')]),
                    ('item', 'poke-item-txt', [('name', 'poke-item')]),
                    ) + tuple([
                        ('attack', 'attack-{}-txt'.format(i),
                            [('name', 'attack-{}'.format(i)),
                             ('cost', 'attack-{}-cost'.format(i)),
                             ('damage', 'attack-{}-dmg'.format(i))])
                        for i in range(1, 5)]):
                text = pop(mechanic_name)
                if text or any(data.get(v) for k, v in extra):
                    mechanic = OrderedDict()
                    for extra_name, extra_field in extra:
                        extra_value = pop(extra_field)
                        if extra_value:
                            if extra_name == 'damage':
                                extra_value = extra_value.replace('x', '×')
                            mechanic[extra_name] = extra_value
                    mechanic['type'] = label
                    if text:
                        mechanic['text'] = Text(text)
                    mechanics.append(mechanic)

        damage_modifiers = []
        weakness = pop('weakness')
        if weakness and weakness != 'None':
            weakness = weakness.replace(' ', '')
            for sign in 'x+':
                if sign in weakness:
                    weak_type, weak_sign, weak_amount = weakness.partition(
                        sign)
                    if weak_sign == 'x':
                        weak_sign = '×'
                    weak_amount = int(weak_amount)
                    break
            else:
                if len(weakness) == 1:
                    weak_type, weak_sign, weak_amount = weakness, '', ''
                else:
                    raise AssertionError('Bad weakness {!r}'.format(weakness))
            for t in weak_type:
                damage_modifiers.append(dict(
                    type=type_from_initial[t],
                    operation=weak_sign,
                    amount=weak_amount,
                ))
        resist = pop('resist')
        if resist and resist.lower() != 'none':
            res = dict(operation='-', amount=30)
            if resist.endswith('-30'):
                resist = resist[:-3]
            elif resist.endswith('-20'):
                resist = resist[:-3]
                res['amount'] = 20
            for t in resist:
                res['type'] = type_from_initial[t]
                damage_modifiers.append(dict(res))
        if damage_modifiers:
            result['damage modifiers'] = damage_modifiers

        retreat = pop('retreat')
        if retreat and int(retreat):
            result['retreat'] = int(retreat)

        simple_out('dex number', 'dex-no.', convertor=int)
        simple_out('species', 'species')

        weight = pop('weight')
        if weight:
            weight = weight.replace('Ibs', 'lbs')
            weight, lbs, end = weight.partition('lb')
            assert lbs and end in ('.', 's.'), (weight, lbs, end)
            if '.' in weight:
                weight = float(weight)
            else:
                weight = int(weight.replace(',', '', 1))
            height = pop('height').replace('’', "'").replace('”', '"')
            feet, sep, inches = height.rstrip('"').partition("'")
            if not sep and '.' in feet:
                feet = float(feet)
                inches = 0
            else:
                feet = int(feet)
                inches = int(inches)
            result['weight'] = weight
            result['height'] = "{}'{}".format(feet, inches)

        simple_out('dex entry', 'dex', convertor=Text)
        illustrator = pop('illus.')
        if illustrator:
            result['illustrators'] = [x.strip() for x in illustrator.split(',')]

        print(dump(result), end='')

        card = OrderedDict()
        number = pop('num')
        if number:
            card['number'] = number
        card['card'] = result
        set_list.append(card)

        if any(data.values()):
            print(yaml.dump(_orig_data))
            print(data)
            data = {k:v for k, v in data.items() if v}
            print(data)
            raise AssertionError('Unprocessed data remaining: {}'.format(data.keys()))
    if destdir:
        for name, set_dict in sets.items():
            if set_dict['cards']:
                print('Out:', name)
                filename = os.path.join(destdir, '{}.cards'.format(name))
                with open(filename, 'w') as setfile:
                    if set_dict.keys() == ['cards'] and all(
                            c.keys() == ['card'] for c in set_dict['cards']):
                        for card in set_dict['cards']:
                            setfile.write(dump(card['card']))
                    else:
                        setfile.write(dump(set_dict))

#sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='UTF-8', line_buffering=True)

if __name__ == '__main__':
    arguments = docopt(__doc__, argv=sys.argv[1:], help=True, version=None)
    if arguments['<infile>']:
        infile = open(arguments['<infile>'])
    else:
        infile = sys.stdin
    main(infile, arguments['<destdir>'], arguments['--sets-file'])
