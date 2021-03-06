# Encoding: UTF-8

from sqlalchemy import (Column, ForeignKey, MetaData, PrimaryKeyConstraint,
                        Table, UniqueConstraint)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.types import *
from sqlalchemy.orm import backref, relationship

from pokedex.db import tables as dex_tables
from pokedex.db import markdown
from pokedex.db.tables import TableBase, create_translation_table

pokedex_classes = list(dex_tables.mapped_classes)

def make_id():
    return Column(Integer, primary_key=True, nullable=False,
        info=dict(description="A numeric ID"))

def make_identifier(length):
    return Column(Unicode(length), nullable=False, unique=True, index=True,
        info=dict(description=u"An identifier", format='identifier'))

def set_print_sort_key(set_print):
    if set_print.set.release_date:
        release_key = set_print.set.release_date.timetuple()
    else:
        release_key = (1e100, 1e100)
    return release_key, set_print.set.identifier, set_print.number

class Card(TableBase):
    __tablename__ = 'tcg_cards'
    __singlename__ = 'tcg_card'
    id = make_id()
    stage_id = Column(Integer, ForeignKey('tcg_stages.id'), nullable=True,
        info=dict(description="ID of the card's evolution stage, if any"))
    class_id = Column(Integer, ForeignKey('tcg_classes.id'),
        nullable=True, index=True,
        info=dict(description="The ID of the card class"))

    family_id = Column(Integer, ForeignKey('tcg_card_families.id'),
        nullable=False, index=True,
        info=dict(description="ID of the card's family"))
    hp = Column(Integer, nullable=True,
        info=dict(description="The card's HP, if any"))
    retreat_cost = Column(Integer, nullable=True,
        info=dict(description="The card retreat cost, if any"))

    # TODO: legal is non-normal, but so far we lack data to compute it
    legal = Column(Boolean, nullable=False,
        info=dict(description="The card's legality in Modified"))

    @property
    def name(self):
        return self.family.name

    @property
    def types(self):
        return tuple(ct.type for ct in self.card_types)

    @property
    def mechanics(self):
        return tuple(cm.mechanic for cm in self.card_mechanics)

    @property
    def subclasses(self):
        return tuple(cs.subclass for cs in self.card_subclasses)

    @property
    def set_prints(self):
        set_prints = [sp for p in self.prints for sp in p.set_prints]
        set_prints.sort(key=set_print_sort_key)
        return set_prints


class Print(TableBase):
    __tablename__ = 'tcg_prints'
    __singlename__ = 'tcg_print'
    id = make_id()
    card_id = Column(Integer, ForeignKey('tcg_cards.id'),
        nullable=False, index=True,
        info=dict(description="The ID of the card"))
    pokemon_flavor_id = Column(Integer, ForeignKey('tcg_pokemon_flavors.id'),
        nullable=True,
        info=dict(description="ID of Pokémon flavor info, if any"))
    # TODO: Reprint note
    # TODO: Filename
    card_release_date = Column(DateTime, nullable=True,
        info=dict(description="The release date, if different from set"))
    card_ban_date = Column(DateTime, nullable=True,
        info=dict(description="Modified ban date, if different from set"))
    holographic = Column(Boolean, nullable=False,
        info=dict(description="True iff the card is holographic"))
    rarity_id = Column(Integer, ForeignKey('tcg_rarities.id'),
        nullable=True, index=True,
        info=dict(description="The ID of the rarity"))

    @property
    def illustrators(self):
        return [pi.illustrator for pi in self.print_illustrators]

    @property
    def set_prints(self):
        return sorted(self._set_prints, key=set_print_sort_key)

class TCGType(TableBase):
    __tablename__ = 'tcg_types'
    __singlename__ = 'tcg_type'
    load_from_csv = True

    id = make_id()
    identifier = make_identifier(10)
    initial = Column(Unicode(1), nullable=False, unique=True,
        info=dict(description=u"Unique shorthand initial", format='plaintext'))
    game_type_id = Column(Integer, ForeignKey(dex_tables.Type.id),
        nullable=False, index=True,
        info=dict(description="ID of the type's handheld game counterpart"))

create_translation_table('tcg_type_names', TCGType, 'names',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The type name", format='plaintext', official=True)),
)


class CardType(TableBase):
    __tablename__ = 'tcg_card_types'

    card_id = Column(Integer, ForeignKey('tcg_cards.id'), nullable=False,
        primary_key=True,
        info=dict(description="The ID of the card"))
    type_id = Column(Integer, ForeignKey('tcg_types.id'), nullable=False,
        primary_key=True, index=True,
        info=dict(description="The ID of the type"))
    order = Column(Integer, nullable=False,
        info=dict(description="Type's sort order on the card"))

class Class(TableBase):
    __tablename__ = 'tcg_classes'
    __singlename__ = 'tcg_class'
    load_from_csv = True

    id = make_id()
    identifier = make_identifier(10)

create_translation_table('tcg_class_names', Class, 'names',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The class name", format='plaintext', official=True)),
)

class Stage(TableBase):
    __tablename__ = 'tcg_stages'
    __singlename__ = 'tcg_stage'
    load_from_csv = True

    id = make_id()
    identifier = make_identifier(10)

create_translation_table('tcg_stage_names', Stage, 'names',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The stage name", format='plaintext', official=True)),
)

class Subclass(TableBase):
    """Trainer type (Item, Stadium, Supporter, ace spec, etc)"""
    __tablename__ = 'tcg_subclasses'
    __singlename__ = 'tcg_subclass'

    id = make_id()
    identifier = make_identifier(10)

create_translation_table('tcg_subclass_names', Subclass, 'names',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The class name", format='plaintext', official=True)),
)

class CardSubclass(TableBase):
    __tablename__ = 'tcg_card_subclasses'
    card_id = Column(Integer, ForeignKey('tcg_cards.id'), nullable=False,
        primary_key=True,
        info=dict(description="The ID of the card"))
    subclass_id = Column(Integer, ForeignKey('tcg_subclasses.id'),
        nullable=False, primary_key=True, index=True,
        info=dict(description="The ID of the subclass"))
    order = Column(Integer, nullable=False,
        info=dict(description="Order of appearace on card"))

class Mechanic(TableBase):
    # Card Mechanic, Attack, PokéPower, PokéBody, Ability, Poké-Item, Text
    __tablename__ = 'tcg_mechanics'
    __singlename__ = 'tcg_mechanic'
    id = make_id()
    class_id = Column(Integer, ForeignKey('tcg_mechanic_classes.id'),
        nullable=False, index=True,
        info=dict(description="The ID of the mechanic class"))
    damage_base = Column(Integer, nullable=True,
        info=dict(description="Base attack damage, if applicable"))
    damage_modifier = Column(Unicode(1), nullable=True,
        info=dict(description="Attack damage modifier, if applicable"))

    @property
    def cost_string(self):
        costs = sorted(self.costs, key=lambda cost: cost.order)
        parts = []
        for cost in costs:
            parts += cost.type.initial * cost.amount
        return ''.join(parts)

create_translation_table('tcg_mechanic_names', Mechanic, 'names',
    name = Column(Unicode(32), nullable=True, index=True,
        info=dict(description="The class name", format='plaintext', official=True)),
)

create_translation_table('tcg_mechanic_effects', Mechanic, 'effects',
    effect = Column(Unicode(5120), nullable=True,
        info=dict(description="A detailed description of the effect",
                  format='markdown', official=True, string_getter=markdown.MarkdownString)),
)

class MechanicClass(TableBase):
    __tablename__ = 'tcg_mechanic_classes'
    __singlename__ = 'tcg_mechanic_class'
    load_from_csv = True

    id = make_id()
    identifier = make_identifier(10)

create_translation_table('tcg_mechanic_class_names', MechanicClass, 'names',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class Rarity(TableBase):
    __tablename__ = 'tcg_rarities'
    __singlename__ = 'tcg_rarity'
    load_from_csv = True

    id = make_id()
    identifier = make_identifier(10)
    symbol = Column(Unicode(3), nullable=False,
        info=dict(description=u"A symbol of the rarity, such as ●, ◆, ★"))

create_translation_table('tcg_rarity_names', Rarity, 'names',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class MechanicCost(TableBase):
    __tablename__ = 'tcg_mechanic_costs'
    __singlename__ = 'tcg_mechanic_cost'
    mechanic_id = Column(Integer, ForeignKey('tcg_mechanics.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The ID of the mechanic"))
    type_id = Column(Integer, ForeignKey('tcg_types.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The type of Energy"))
    amount = Column(Integer, nullable=False,
        info=dict(description=u"The amount of this Energy required"))
    order = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"Order of appearance on card."))

class CardMechanic(TableBase):
    __tablename__ = 'tcg_card_mechanics'
    card_id = Column(Integer, ForeignKey('tcg_cards.id'),
        primary_key=True, nullable=False,
        info=dict(description="The ID of the card"))
    mechanic_id = Column(Integer, ForeignKey('tcg_mechanics.id'),
        primary_key=True, nullable=False, index=True,
        info=dict(description="The ID of the mechanic"))
    order = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"Order of appearance on card."))

class DamageModifier(TableBase):
    """Damage modifiers such as Weaknesses and Resistances"""
    __tablename__ = 'tcg_damage_modifiers'
    __singlename__ = 'tcg_damage_modifier'
    card_id = Column(Integer, ForeignKey('tcg_cards.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The ID of the card"))
    type_id = Column(Integer, ForeignKey('tcg_types.id'),
        primary_key=True, nullable=False, index=True,
        info=dict(description=u"The type this card is weak/resistant to"))
    operation = Column(Unicode(2), nullable=False,
        info=dict(description=u"The operator in the damage adjustment"))
    amount = Column(Integer, nullable=False,
        info=dict(description=u"The number in the damage adjustment"))
    order = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"Order of appearance on card."))

class PokemonFlavor(TableBase):
    __tablename__ = 'tcg_pokemon_flavors'
    __singlename__ = 'tcg_pokemon_flavor'
    id = make_id()
    species_id = Column(Integer, ForeignKey(dex_tables.PokemonSpecies.id),
        nullable=True,
        info=dict(description=u"The ID of the Pokémon species"))
    height = Column(Integer, nullable=True,
        info=dict(description="Height in pounds"))
    weight = Column(Integer, nullable=True,
        info=dict(description="Weight in inches"))

create_translation_table('tcg_pokemon_flavor', PokemonFlavor, 'flavor',
    genus = Column(Unicode(16), nullable=True, index=True,
        info=dict(description="The species, if different from games",
                  format='plaintext', official=True)),
    dex_entry = Column(Unicode(256), nullable=True, index=True,
        info=dict(description="The 'dex entry, if different from games",
                  format='plaintext', official=True)),
)

class Set(TableBase):
    __tablename__ = 'tcg_sets'
    __singlename__ = 'tcg_set'
    load_from_csv = True

    id = make_id()
    identifier = make_identifier(30)
    total = Column(Integer, nullable=True,
        info=dict(description="Number of cards in the set, if applicable"))
    # TODO: sub-sets
    release_date = Column(Date, nullable=True,
        info=dict(description="The release date"))
    ban_date = Column(Date, nullable=True,
        info=dict(description="Modified ban date"))

create_translation_table('tcg_set_names', Set, 'names',
    name = Column(Unicode(30), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class SetPrint(TableBase):
    __tablename__ = 'tcg_set_prints'
    __singlename__ = 'tcg_set_print'
    set_id = Column(Integer, ForeignKey('tcg_sets.id'),
        nullable=False, primary_key=True,
        info=dict(description="The ID of the set"))
    print_id = Column(Integer, ForeignKey('tcg_prints.id'),
        nullable=False, primary_key=True, index=True,
        info=dict(description="The ID of the print"))
    number = Column(Unicode(5), nullable=True,
        info=dict(description='The card "number" in the set (may not be actually numeric)'))
    order = Column(Integer, nullable=True,
        info=dict(description="Sort order inside the set"))

    @property
    def card(self):
        return self.print_.card

class Illustrator(TableBase):
    __tablename__ = 'tcg_illustrators'
    __singlename__ = 'tcg_illustrator'
    id = make_id()
    identifier = make_identifier(50)
    name = Column(Unicode(50), nullable=False,
        info=dict(description="Name of the illustrator"))


class PrintIllustrator(TableBase):
    __tablename__ = 'tcg_print_illustrators'
    print_id = Column(Integer, ForeignKey('tcg_prints.id'),
        primary_key=True, nullable=False,
        info=dict(description="The ID of the print"))
    illustrator_id = Column(Integer, ForeignKey('tcg_illustrators.id'),
        primary_key=True, nullable=False, index=True,
        info=dict(description="The ID of the illustrator"))
    order = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"Order of appearance on card."))


class Scan(TableBase):
    __tablename__ = 'tcg_scans'
    __singlename__ = 'tcg_scan'
    id = make_id()
    print_id = Column(Integer, ForeignKey('tcg_prints.id'),
        nullable=False, index=True,
        info=dict(description=u"The ID of the print this is a scan of"))
    filename = Column(Unicode(30), nullable=False,
        info=dict(description="Filename for this scan"))
    order = Column(Integer, nullable=False,
        info=dict(description=u"Order for scan galleries."))


class CardFamily(TableBase):
    """Set of all cards that share the same name"""
    # The name of a card is actually important for mechanics, so it seems
    # a bit icky to stick it on "card" and leave it at the mercy of
    # translations. So, we have card family objects in the DB.
    # (Also: less translation needed)

    __tablename__ = 'tcg_card_families'
    __singlename__ = 'tcg_card_family'
    id = make_id()
    identifier = make_identifier(32)

    @property
    def set_prints(self):
        set_prints = [sp
                      for c in self.cards
                      for p in c.prints
                      for sp in p.set_prints]
        set_prints.sort(key=set_print_sort_key)
        return set_prints


create_translation_table('tcg_card_family_names', CardFamily, 'names',
    name = Column(Unicode(32), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)


class Evolution(TableBase):
    __tablename__ = 'tcg_evolutions'
    __singlename__ = 'tcg_evolution'

    card_id = Column(Integer, ForeignKey('tcg_cards.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The ID of the card the evolution appears on"))
    family_id = Column(Integer, ForeignKey('tcg_card_families.id'),
        primary_key=True, nullable=False, index=True,
        info=dict(description=u"The ID of the family"))
    family_to_card = Column(Boolean, nullable=False,
        info=dict(description=u"True for 'evolves from', false for 'evolves to'"))
    order = Column(Integer, nullable=False,
        info=dict(description=u"Order of appearance on card."))


_pokedex_classes_set = set(pokedex_classes)
tcg_classes = [c for c in dex_tables.mapped_classes if
               c not in _pokedex_classes_set]



Card.class_ = relationship(Class, backref='cards')
Card.stage = relationship(Stage, backref='cards')
Card.family = relationship(CardFamily, backref='cards')

Print.card = relationship(Card, backref='prints')
Print.pokemon_flavor = relationship(PokemonFlavor, backref='prints')
Print.rarity = relationship(Rarity, backref='prints')

TCGType.game_type = relationship(dex_tables.Type)

CardType.card = relationship(Card, backref=backref(
    'card_types', order_by=CardType.order.asc()))
CardType.type = relationship(TCGType, backref='card_types')

CardSubclass.card = relationship(Card, backref=backref(
    'card_subclasses', order_by=CardSubclass.order.asc()))
CardSubclass.subclass = relationship(Subclass, backref='card_subclasses')

Mechanic.class_ = relationship(MechanicClass, backref='mechanics')

MechanicCost.mechanic = relationship(Mechanic, backref=backref(
    'costs', order_by=MechanicCost.order.asc()))
MechanicCost.type = relationship(TCGType)

DamageModifier.card = relationship(Card, backref=backref(
    'damage_modifiers', order_by=DamageModifier.order.asc()))
DamageModifier.type = relationship(TCGType, backref='damage_modifiers')

CardMechanic.card = relationship(Card, backref=backref(
    'card_mechanics', order_by=CardMechanic.order.asc()))
CardMechanic.mechanic = relationship(Mechanic, backref='card_mechanics')

PokemonFlavor.species = relationship(dex_tables.PokemonSpecies)

Set.prints = association_proxy('set_prints', 'print_')

SetPrint.print_ = relationship(Print, backref='set_prints')
SetPrint.set = relationship(Set, backref=backref(
    'set_prints', order_by=(SetPrint.order.asc(), SetPrint.number.asc())))

PrintIllustrator.print_ = relationship(Print, backref='print_illustrators')
PrintIllustrator.illustrator = relationship(Illustrator, backref=backref(
    'print_illustrators', order_by=(PrintIllustrator.order)))

Scan.print_ = relationship(Print, backref=backref(
    'scans', order_by=Scan.order.asc()))

Evolution.card = relationship(Card, backref=backref(
    'evolutions', order_by=Evolution.order.asc()))
Evolution.family = relationship(CardFamily, backref='evolutions')
