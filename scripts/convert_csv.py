
import io
import sys
import csv
import yaml
import textwrap

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

stage_initials = {
    'Baby': 'A',
    'Basic': 'B',
    'Stage 1': 'S1',
    'Stage 2': 'S2',
    'Level-Up': 'L',
}

rarities = {
    'triple-rare-holo': '3H',
    'P': 'P',
    'rare-holo': 'RH',
    'rare': 'R',
    'uncommon': 'U',
    'uncommon-holo': 'UH',
    'common': 'C',
    'common-holo': 'CH',
    'none': '-',
    '': '?',
}

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

def dump_wrapped(print, text):
    lines = textwrap.wrap(text, 60,
        initial_indent='    ',
        subsequent_indent='    ')
    for line in lines:
        print(line)

def main(infile):
    sets = []
    cards = {}
    for data in csv.DictReader(infile):
        _orig_data = dict(data)
        munge_errors(data)
        print()
        def pop(name):
            item = data.pop(name)
            return item.strip()

        def simple_out(template, name):
            arg = pop(name)
            if arg:
                print(template.format(arg))

        card_name = pop('card-name')
        try:
            pop('1')
            tcg_set = pop('set')
            if not tcg_set:
                print('ERROR: NO SET FOR CARD')
                print()
                continue
            sets.append(tcg_set)
            print('#SET {}'.format(tcg_set))

            header = ['{}.'.format(pop('num'))]

            header.append((pop('class') + pop('class2')) or '?')

            header.append(rarities[pop('rarity')])

            header.append(card_name)

            hp = pop('hp')
            if hp:
                header.append('~{}'.format(int(hp)))
        except:
            print(card_name)
            raise

        print(' '.join(header))

        simple_out('TYPE {}', 'type1')
        simple_out('TYPE {}', 'type2')


        simple_out('TCLS {}', 'trainer-class')
        simple_out('ECLS {}', 'energy-class')

        stage = pop('stage')
        if stage:
            print('STGE {}'.format(stage_initials[stage]))

        simple_out('< {}', 'evolves-from')
        simple_out('> {}', 'evolves-into')

        simple_out('#### evoline {}', 'evo-line')
        simple_out('#### legal {}', 'legal')
        simple_out('#### filename {}', 'filename')
        simple_out('#### orphan {}', 'orphan')
        simple_out('#### variant {}', 'has-variant')
        simple_out('#### in-set-variant-of {}', 'in-set-variant-of')

        simple_out('DATD {}', 'dated')
        simple_out('REPR {}', 'reprint-of')

        simple_out('TSUB {}', 'trainer-sub-class')

        for classno in range(1, 4):
            simple_out('SCLS {}', 'sub-class-{}'.format(classno))

        pokemon = pop('pokemon')
        if pokemon:
            print('POKE', pokemon)

        for label, mechanic_name, name_name in (
                ('RULE Note', 'poke-note', None),
                ('RULE Rule', 'trainer-rule', None),
                ('RULE Effect', 'trainer-txt', None),
                ('RULE Effect', 'energy-txt', None),
                ('RULE Pokémon Power', 'pkmn-power-txt', 'pkmn-power-1'),
                ('RULE PokéPower', 'power-1-txt', 'power-1'),
                ('RULE PokéPower', 'power-2-txt', 'power-2'),
                ('RULE PokéBody', 'body-1-txt', 'body-1'),
                ('RULE Item', 'poke-item-txt', 'poke-item'),
                ):
            text = pop(mechanic_name)
            if text:
                if name_name:
                    print('{}, {}:'.format(label, pop(name_name)))
                else:
                    print("{}:".format(label))
                dump_wrapped(print, text)

        for attack_number in range(1, 5):
            apop = lambda f: pop(f.format(attack_number))
            name = apop('attack-{}')
            if name:
                damage = apop('attack-{}-dmg')
                if damage:
                    damage_txt = ' ~{}'.format(damage)
                else:
                    damage_txt = ''
                print('[{}] {}{}:'.format(
                    apop('attack-{}-cost'), name, damage_txt))
                dump_wrapped(print, apop('attack-{}-txt'))

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
            print('WEAK [{}]{}{}'.format(weak_type, weak_sign, weak_amount))

        simple_out('RESI [{}]', 'resist')

        retreat = pop('retreat')
        if retreat:
            print('RETR {}'.format(int(retreat)))

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
            dexi = "DEXI {} {} <{}> <{}'{}>:".format(
                pop('dex-no.'), pop('species'), weight, feet, inches)
            print(dexi)
            dump_wrapped(print, pop('dex'))

        simple_out('ILLU {}', 'illus.')

        if any(data.values()):
            print(yaml.dump(_orig_data))
            print(data)
            data = {k:v for k, v in data.items() if v}
            print(data)
            raise AssertionError('Unprocessed data remaining: {}'.format(data.keys()))
    # TODO: sets

sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='UTF-8', line_buffering=True)

main(sys.stdin)
