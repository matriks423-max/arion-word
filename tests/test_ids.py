from engine.canon.ids import slugify, entity_id


def test_slugify_basic():
    assert slugify("Kairo Voss") == "kairo-voss"


def test_slugify_strips_punctuation_and_accents():
    assert slugify("Caelum City — Inner District!") == "caelum-city-inner-district"


def test_entity_id_prefixes_type():
    assert entity_id("character", "Kairo Voss") == "char-kairo-voss"
    assert entity_id("world_doc", "Curses") == "world-curses"
