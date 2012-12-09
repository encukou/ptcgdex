# Encoding: UTF-8

from sqlalchemy import (Column, ForeignKey, MetaData, PrimaryKeyConstraint,
                        Table, UniqueConstraint)
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
    return Column(Unicode(length), nullable=False, unique=True,
        info=dict(description=u"An identifier", format='identifier'))

class Card(TableBase):
    __tablename__ = 'tcg_cards'
    __singlename__ = 'tcg_card'
    id = make_id()
    stage_id = Column(Integer, ForeignKey('tcg_stages.id'), nullable=True,
        info=dict(description="ID of the card's evolution stage, if any"))
    class_id = Column(Integer, ForeignKey('tcg_classes.id'), nullable=False,
        info=dict(description="The ID of the card class"))

    family_id = Column(Integer, ForeignKey('tcg_card_families.id'),
        nullable=True,
        info=dict(description="ID of the card's family"))
    hp = Column(Integer, nullable=True,
        info=dict(description="The card's HP, if any"))
    retreat_cost = Column(Integer, nullable=True,
        info=dict(description="The card retreat cost, if any"))
    resistance_type_id = Column(Integer, ForeignKey('tcg_types.id'),
        nullable=True,
        info=dict(description="ID of type the card is resistant to, if any"))

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
        return tuple(sorted((cs.subclass for cs in self.card_subclasses),
                            key=lambda s: s.id))


class Print(TableBase):
    __tablename__ = 'tcg_prints'
    __singlename__ = 'tcg_print'
    id = make_id()
    card_id = Column(Integer, ForeignKey('tcg_cards.id'), nullable=False,
        info=dict(description="The ID of the card"))
    set_id = Column(Integer, ForeignKey('tcg_sets.id'), nullable=False,
        info=dict(description="The ID of the set this appeard in"))
    set_number = Column(Unicode(5), nullable=False,
        info=dict(description="The card number in the set (may not be actually numeric)"))
    order = Column(Integer, nullable=False,
        info=dict(description="Sort order inside the set (may not be unique)"))
    illusrator_id = Column(Integer, ForeignKey('tcg_illustrators.id'),
        nullable=False,
        info=dict(description="ID of the illustrator"))
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
    rarity_id = Column(Integer, ForeignKey('tcg_rarities.id'), nullable=False,
        info=dict(description="The ID of the rarity"))

class TCGType(TableBase):
    __tablename__ = 'tcg_types'
    __singlename__ = 'tcg_type'
    load_from_csv = True

    id = make_id()
    identifier = make_identifier(10)
    initial = Column(Unicode(1), nullable=False, unique=True,
        info=dict(description=u"Unique shorthand initial", format='plaintext'))
    game_type_id = Column(Integer, ForeignKey(dex_tables.Type.id),
        nullable=False,
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
        primary_key=True,
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
    load_from_csv = True

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
        nullable=False, primary_key=True,
        info=dict(description="The ID of the subclass"))

class Mechanic(TableBase):
    # Card Mechanic, Attack, PokéPower, PokéBody, Ability, Poké-Item, Text
    __tablename__ = 'tcg_mechanics'
    __singlename__ = 'tcg_mechanic'
    id = make_id()
    class_id = Column(Integer, ForeignKey('tcg_mechanic_classes.id'),
        nullable=False,
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
        primary_key=True, nullable=False,
        info=dict(description="The ID of the mechanic"))
    order = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"Order of appearance on card."))

class Weakness(TableBase):
    __tablename__ = 'tcg_weaknesses'
    __singlename__ = 'tcg_weakness'
    card_id = Column(Integer, ForeignKey('tcg_cards.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The ID of the card"))
    type_id = Column(Integer, ForeignKey('tcg_types.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The type of Energy this card is weak to"))
    operation = Column(Unicode(2), nullable=False,
        info=dict(description=u"The operator in the damage adjustment"))
    amount = Column(Integer, nullable=False,
        info=dict(description=u"The number in the damage adjustment"))

class PokemonFlavor(TableBase):
    __tablename__ = 'tcg_pokemon_flavors'
    __singlename__ = 'tcg_pokemon_flavor'
    id = make_id()
    species_id = Column(Integer, ForeignKey(dex_tables.PokemonSpecies.id),
        nullable=False,
        info=dict(description=u"The ID of the Pokémon species"))
    height = Column(Integer, nullable=False,
        info=dict(description="Height in pounds"))
    weight = Column(Integer, nullable=False,
        info=dict(description="Weight in inches"))

create_translation_table('tcg_pokemon_flavor_text', PokemonFlavor, 'flavor',
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

class Illustrator(TableBase):
    __tablename__ = 'tcg_illustrators'
    __singlename__ = 'tcg_illustrator'
    id = make_id()
    name = Column(Unicode(50), nullable=False,
        info=dict(description="Name of the illustrator"))

class Scan(TableBase):
    __tablename__ = 'tcg_scans'
    __singlename__ = 'tcg_scan'
    id = make_id()
    print_id = Column(Integer, ForeignKey('tcg_prints.id'), nullable=False,
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
        primary_key=True, nullable=False,
        info=dict(description=u"The ID of the family"))
    family_to_card = Column(Boolean, nullable=False,
        info=dict(description=u"True for 'evolves from', false for 'evolves to'"))


_pokedex_classes_set = set(pokedex_classes)
tcg_classes = [c for c in dex_tables.mapped_classes if
               c not in _pokedex_classes_set]



Card.class_ = relationship(Class, backref='cards')
Card.stage = relationship(Stage, backref='cards')
Card.resistance_type = relationship(TCGType, backref='resistant_cards')
Card.family = relationship(CardFamily, backref='cards')

Print.card = relationship(Card, backref='prints')
Print.set = relationship(Set, backref=backref(
    'prints', order_by=(Print.order.asc(), Print.set_number.asc())))
Print.illustrator = relationship(Illustrator, backref='prints')
Print.pokemon_flavor = relationship(PokemonFlavor, backref='prints')
Print.rarity = relationship(Rarity, backref='prints')

TCGType.game_type = relationship(dex_tables.Type)

CardType.card = relationship(Card, backref=backref(
    'card_types', order_by=CardType.order.asc()))
CardType.type = relationship(TCGType, backref='card_types')

CardSubclass.card = relationship(Card, backref='card_subclasses')
CardSubclass.subclass = relationship(Subclass, backref='card_subclasses')

Mechanic.class_ = relationship(MechanicClass, backref='mechanics')

MechanicCost.mechanic = relationship(Mechanic, backref=backref(
    'costs', order_by=MechanicCost.order.asc()))
MechanicCost.type = relationship(TCGType)

Weakness.card = relationship(Card, backref='weaknesses')
Weakness.type = relationship(TCGType, backref='weaknesses')

CardMechanic.card = relationship(Card, backref=backref(
    'card_mechanics', order_by=CardMechanic.order.asc()))
CardMechanic.mechanic = relationship(Mechanic, backref='card_mechanics')

PokemonFlavor.species = relationship(dex_tables.PokemonSpecies)

Scan.print_ = relationship(Print, backref=backref(
    'scans', order_by=Scan.order.asc()))

Evolution.card = relationship(Card, backref='evolutions')
Evolution.family = relationship(CardFamily, backref='evolutions')
