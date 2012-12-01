# Encoding: UTF-8

from sqlalchemy import (Column, ForeignKey, MetaData, PrimaryKeyConstraint,
                        Table, UniqueConstraint)
from sqlalchemy.types import *

from pokedex.db import tables as dex_tables
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
    hp = Column(Integer, nullable=True,
        info=dict(description="The card's HP"))
    stage = Column(Integer, nullable=True,
        info=dict(description="The card's evolution stage"))
    class_id = Column(Integer, ForeignKey('tcg_classes.id'), nullable=False,
        info=dict(description="The ID of the card class"))

create_translation_table('tcg_card_names', Card, 'names',
    name = Column(Unicode(32), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class Print(TableBase):
    __tablename__ = 'tcg_prints'
    __singlename__ = 'tcg_print'
    id = make_id()
    card_id = Column(Integer, ForeignKey('tcg_cards.id'), nullable=False,
        info=dict(description="The ID of the card"))
    set_id = Column(Integer, ForeignKey('tcg_sets.id'), nullable=False,
        info=dict(description="The ID of the set this appeard in"))
    set_number = Column(Integer, nullable=False,
        info=dict(description="The number in the set"))
    illusrator_id = Column(Integer, ForeignKey('tcg_illustrators.id'),
        nullable=False,
        info=dict(description="The ID of the illustrator"))
    pokemon_flavor_id = Column(Integer, ForeignKey('tcg_pokemon_flavors.id'),
        nullable=False,
        info=dict(description="The ID of the illustrator"))
    # TODO: Reprint note
    # TODO: Filename
    card_release_date = Column(DateTime, nullable=True,
        info=dict(description="The release date, if different from set"))
    card_ban_date = Column(DateTime, nullable=True,
        info=dict(description="Modified ban date, if different from set"))

create_translation_table('tcg_print_names', Print, 'names',
    flavor = Column(Unicode(32), nullable=False, index=True,
        info=dict(description="The flavor text or dex entry",
                  format='plaintext', official=True)),
)

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
    type_id = Column(Integer, ForeignKey('tcg_subclasses.id'), nullable=False,
        primary_key=True,
        info=dict(description="The ID of the subclass"))

class Mechanic(TableBase):
    # Card Mechanic, Attack, PokéPower, PokéBody, Ability, Poké-Item, Text
    # also Note, Weakness, Resistance, Retread cost
    # TODO: Evolution
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

create_translation_table('tcg_mechanic_names', Mechanic, 'names',
    name = Column(Unicode(32), nullable=False, index=True,
        info=dict(description="The class name", format='plaintext', official=True)),
)

class MechanicClass(TableBase):
    __tablename__ = 'tcg_mechanic_classes'
    __singlename__ = 'tcg_mechanic_class'
    id = make_id()
    identifier = make_identifier(10)

create_translation_table('tcg_mechanic_class_names', MechanicClass, 'names',
    name = Column(Unicode(10), nullable=False, index=True,
        info=dict(description="The name", format='plaintext', official=True)),
)

class MechanicCost(TableBase):
    __tablename__ = 'tcg_mechanic_costs'
    __singlename__ = 'tcg_mechanic_cost'
    # TODO: these should be in the order typed in
    mechanic_id = Column(Integer, ForeignKey('tcg_mechanics.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The ID of the mechanic"))
    type_id = Column(Integer, ForeignKey('tcg_types.id'),
        primary_key=True, nullable=False,
        info=dict(description=u"The type of Energy"))
    amount = Column(Integer, nullable=False,
        info=dict(description=u"The amount of this Energy required"))

# TODO: class MechanicWording(TableBase):

class CardMechanic(TableBase):
    __tablename__ = 'tcg_card_mechanics'
    card_id = Column(Integer, ForeignKey('tcg_cards.id'),
        primary_key=True, nullable=False,
        info=dict(description="The ID of the card"))
    type_id = Column(Integer, ForeignKey('tcg_mechanics.id'),
        primary_key=True, nullable=False,
        info=dict(description="The ID of the mechanic"))
    order = Column(Integer, primary_key=True, nullable=False,
        info=dict(description=u"Order of appearance on card."))

class PokemonFlavor(TableBase):
    __tablename__ = 'tcg_pokemon_flavors'
    __singlename__ = 'tcg_pokemon_flavor'
    id = make_id()
    species_id = Column(Integer, ForeignKey(dex_tables.PokemonSpecies.id),
        nullable=False,
        info=dict(description=u"The ID of the Pokémon species"))
    height = Column(Integer, nullable=True,
        info=dict(description="Height, if different from games"))
    weight = Column(Integer, nullable=True,
        info=dict(description="Weight, if different from games"))
    weight = Column(Integer, nullable=True,
        info=dict(description="Weight, if different from games"))
    version_id = Column(Integer, ForeignKey(dex_tables.Version.id),
        nullable=True,
        info=dict(
            description="Game version ID, if flavor text is taken from games"))

create_translation_table('tcg_pokemon_flavor_text', PokemonFlavor, 'flavor',
    species = Column(Unicode(16), nullable=True, index=True,
        info=dict(description="The species, if different from games",
                  format='plaintext', official=True)),
    name = Column(Unicode(256), nullable=True, index=True,
        info=dict(description="The 'dex text, if different from games",
                  format='plaintext', official=True)),
)

# TODO: class Evolution(TableBase):

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


_pokedex_classes_set = set(pokedex_classes)
tcg_classes = [c for c in dex_tables.mapped_classes if
               c not in _pokedex_classes_set]
