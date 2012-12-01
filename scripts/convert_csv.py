# Encoding: UTF-8
"""Usage:
  convert_csv.py [options] [<destdir>] [<infile>]

Options:
  -h, --help     Display help

infile defaults to stdin if not given.
"""

from __future__ import division, print_function, unicode_literals

import os
import io
import sys
import csv
import textwrap
from contextlib import contextmanager
from collections import OrderedDict

import yaml
from docopt import docopt

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
                     width=60,
                    )

def main(infile, destdir=None):
    if destdir and not os.path.isdir(destdir):
        raise ValueError('{} is not a directory'.format(destdir))
    sets = {}
    for data in csv.DictReader(infile):
        _orig_data = dict(data)
        munge_errors(data)
        print()
        def pop(name):
            item = data.pop(name)
            return item.strip().decode('utf-8')

        def simple_out(outname, name, convertor=None):
            arg = pop(name)
            if arg:
                if convertor:
                    arg = convertor(arg)
                result[outname] = arg

        result = OrderedDict()

        pop('1')
        tcg_set = data.get('set')
        simple_out('set', 'set')
        simple_out('number', 'num')
        simple_out('name', 'card-name')

        rarity = pop('rarity')
        rarity, holo, end = rarity.partition('-holo')
        assert not end, (rarity, holo, end)
        result['rarity'] = rarity
        result['holographic'] = bool(holo)

        simple_out('class', 'class')
        simple_out('class', 'class2')

        with nonempty_setter(result, 'types') as types:
            append_nonempty(types, pop('type1'))
            append_nonempty(types, pop('type2'))

        simple_out('hp', 'hp', convertor=int)

        simple_out('trainer class', 'trainer-class')

        simple_out('trainer subclass', 'trainer-sub-class')

        simple_out('energy class', 'energy-class')

        simple_out('stage', 'stage')

        simple_out('evolves from', 'evolves-from')
        simple_out('evolves into', 'evolves-into')

        simple_out('evo line', 'evo-line')
        simple_out('legality', 'legal')
        simple_out('filename', 'filename')
        simple_out('orphan', 'orphan')
        simple_out('has-variant', 'has-variant')
        simple_out('in-set-variant-of', 'in-set-variant-of')

        simple_out('dated', 'dated')
        simple_out('reprint of', 'reprint-of')
        simple_out('pokemon', 'pokemon')

        with nonempty_setter(result, 'classes') as classes:
            for classno in range(1, 4):
                cls = pop('sub-class-{}'.format(classno))
                if cls:
                    classes.append(cls)

        with nonempty_setter(result, 'mechanics') as mechanics:
            for label, mechanic_name, name_name in (
                    ('Note', 'poke-note', None),
                    ('Rule', 'trainer-rule', None),
                    ('Effect', 'trainer-txt', None),
                    ('Effect', 'energy-txt', None),
                    ('Pokémon Power', 'pkmn-power-txt', 'pkmn-power-1'),
                    ('PokéPower', 'power-1-txt', 'power-1'),
                    ('PokéPower', 'power-2-txt', 'power-2'),
                    ('PokéBody', 'body-1-txt', 'body-1'),
                    ('Item', 'poke-item-txt', 'poke-item'),
                    ):
                text = pop(mechanic_name)
                if text:
                    mechanic = OrderedDict()
                    if name_name:
                        mechanic['name'] = pop(name_name)
                    mechanic['type'] = label
                    mechanic['text'] = Text(text)
                    mechanics.append(mechanic)

        with nonempty_setter(result, 'attacks') as attacks:
            for attack_number in range(1, 5):
                apop = lambda f: pop(f.format(attack_number))
                name = apop('attack-{}')
                if name:
                    attack = OrderedDict([
                        ('name', name),
                        ('cost', apop('attack-{}-cost')),
                        ('text', Text(apop('attack-{}-txt'))),
                        ('damage', apop('attack-{}-dmg')),
                    ])
                    attacks.append(OrderedDict(
                        (k, v) for k, v in attack.items() if v))

        weakness = pop('weakness')
        if weakness and weakness != 'None':
            weakness = weakness.replace(' ', '')
            for sign in 'x+':
                if sign in weakness:
                    weak_type, weak_sign, weak_amount = weakness.partition(
                        sign)
                    weak_amount = int(weak_amount)
                    break
            else:
                if len(weakness) == 1:
                    weak_type, weak_sign, weak_amount = weakness, '', ''
                else:
                    raise AssertionError('Bad weakness {!r}'.format(weakness))
            result['weakness'] = {
                'type': weak_type,
                'operation': weak_sign,
                'amount': weak_amount,
            }

        simple_out('resistance', 'resist')

        retreat = pop('retreat')
        if retreat:
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
        simple_out('illustrator', 'illus.')

        print(dump(result), end='')

        sets.setdefault(tcg_set or 'unknown', []).append(result)

        if any(data.values()):
            print(yaml.dump(_orig_data))
            print(data)
            data = {k:v for k, v in data.items() if v}
            print(data)
            raise AssertionError('Unprocessed data remaining: {}'.format(data.keys()))
    if destdir:
        for name, cards in sets.items():
            filename = os.path.join(destdir, '{}.cards'.format(name))
            with open(filename, 'w') as setfile:
                for card in cards:
                    setfile.write(dump(card))

#sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='UTF-8', line_buffering=True)

if __name__ == '__main__':
    arguments = docopt(__doc__, argv=sys.argv[1:], help=True, version=None)
    if arguments['<infile>']:
        infile = open(arguments['<infile>'])
    else:
        infile = sys.stdin
    main(infile, arguments['<destdir>'])
