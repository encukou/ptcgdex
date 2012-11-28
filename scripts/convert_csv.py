# Encoding: UTF-8

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
)

stage_initials = {
    'Basic': 'B',
    'Stage 1': 'S1',
    'Stage 2': 'S2',
}

trainer_class_idents = {
    'Trainer': 'T',
}

trainer_subclass_idents = {
    'Fossil': 'f',
}

energy_class_idents = {
    'Special': 'Es',
    'Basic': 'Eb',
}

def dump_wrapped(text):
    lines = textwrap.wrap(text, 60,
        initial_indent='    ',
        subsequent_indent='    ')
    for line in lines:
        print line

def main(infile):
    sets = []
    cards = {}
    for data in csv.DictReader(infile):
        print
        def pop(name):
            item = data.pop(name)
            return item.strip().decode('utf-8')
        card_name = pop('card-name')
        try:
            pop('1')
            tcg_set = pop('set')
            sets.append(tcg_set)

            header = ['{}.'.format(pop('num'))]

            stage = pop('stage')
            if stage:
                header.append(stage_initials[stage])
            else:
                trainer_class = pop('trainer-class')
                if trainer_class:
                    classname = trainer_class_idents[trainer_class]
                    trainer_subclass = pop('trainer-sub-class')
                    if trainer_subclass:
                        classname += trainer_subclass_idents[trainer_subclass]
                    header.append(classname)
                else:
                    energy_class = pop('energy-class')
                    if energy_class:
                        header.append(energy_class_idents[energy_class])
                    else:
                        raise AssertionError('Unknown card type')
                        continue

            type1 = pop('type1')
            if type1:
                poke_type = type_initials[type1]
                type2 = pop('type2')
                if type2:
                    poke_type += type_initials[type2]
                header.append('[{}]'.format(poke_type))

            header.append(card_name)

            hp = pop('hp')
            if hp:
                header.append('~{}'.format(int(hp)))
        except:
            print card_name
            raise

        print ' '.join(header)

        evolves_from = pop('evolves-from')
        if evolves_from:
            print '<{}'.format(evolves_from)

        pkmn_power_1 = pop('pkmn-power-1')
        if pkmn_power_1:
            print 'PPWR {}:'.format(pkmn_power_1)
            dump_wrapped(pop('pkmn-power-txt'))

        for attack_number in range(1, 5):
            apop = lambda f: pop(f.format(attack_number))
            name = apop('attack-{}')
            if name:
                damage = apop('attack-{}-dmg')
                if damage:
                    damage_txt = ' ~{}'.format(damage)
                else:
                    damage_txt = ''
                print '[{}] {}{}:'.format(
                    apop('attack-{}-cost'), name, damage_txt)
                dump_wrapped(apop('attack-{}-txt'))

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
                raise AssertionError('Bad weakness {!r}'.format(weakness))
            print 'WEAK [{}]{}{}'.format(weak_type, weak_sign, weak_amount)

        resist = pop('resist')
        if resist and resist != 'None':
            print 'RESI [{}]'.format(resist)

        retreat = pop('retreat')
        if retreat:
            print 'RETR {}'.format(int(retreat))

        weight = pop('weight')
        if weight:
            weight, lbs, nothing = weight.partition('lbs.')
            assert lbs and not nothing
            if '.' in weight:
                weight = float(weight)
            else:
                weight = int(weight.replace(',', '', 1))
            height = pop('height').replace(u'’', "'").replace(u'”', '"')
            feet, sep, inches = height.rstrip('"').partition("'")
            feet = int(feet)
            inches = int(inches)
            dexi = "DEXI {} {} <{}> <{}'{}>:".format(
                pop('dex-no.'), pop('species'), weight, feet, inches)
            print repr(dexi)
            print dexi
            dump_wrapped(pop('dex'))

        for mechanic_name in 'trainer-txt', 'energy-txt':
            text = pop(mechanic_name)
            if text:
                print "MECHA:"
                dump_wrapped(text)

        print "ILLU {}".format(pop('illus.'))

        if any(data.values()):
            print data
            data = {k:v for k, v in data.items() if v}
            print data
            raise AssertionError('Unprocessed data remaining: {}'.format(data.keys()))
    # TODO: sets



main(sys.stdin)
