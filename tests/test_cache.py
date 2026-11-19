from migratelens.cache import Cache, make_key


def test_key_is_stable_and_sensitive():
    a = make_key("p", "m", {"x": 1, "y": 2})
    assert a == make_key("p", "m", {"y": 2, "x": 1})
    assert a != make_key("p2", "m", {"x": 1, "y": 2})
    assert a != make_key("p", "m2", {"x": 1, "y": 2})
    assert a != make_key("p", "m", {"x": 2, "y": 2})


def test_roundtrip_and_counters(tmp_path):
    c = Cache(tmp_path / "c.sqlite")
    k = make_key("p", "m")
    assert c.get(k) is None
    c.set(k, {"text": "hi", "tokens": 3})
    assert c.get(k) == {"text": "hi", "tokens": 3}
    assert (c.hits, c.misses) == (1, 1)


def test_persists_across_instances(tmp_path):
    p = tmp_path / "c.sqlite"
    Cache(p).set("k", {"v": 1})
    assert Cache(p).get("k") == {"v": 1}
