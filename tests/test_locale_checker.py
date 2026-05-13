import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import locale_checker  # noqa: E402


def _make_locale_resource(tmp_path, locales: dict[str, dict[str, str]], lua_calls: list[str] | None = None):
    res = tmp_path / "my_res"
    res.mkdir(parents=True)
    # Real FiveM resources always carry a manifest; without one the resource
    # walker (correctly) ignores the directory.
    (res / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\ngame 'gta5'\n", encoding="utf-8"
    )
    locale_dir = res / "locales"
    locale_dir.mkdir()
    for lang, entries in locales.items():
        body = ["Locales = Locales or {}", f"Locales['{lang}'] = {{"]
        for key, val in entries.items():
            body.append(f"  ['{key}'] = '{val}',")
        body.append("}\n")
        (locale_dir / f"{lang}.lua").write_text("\n".join(body), encoding="utf-8")
    if lua_calls:
        (res / "client.lua").write_text("\n".join(lua_calls), encoding="utf-8")
    return res


def test_detects_missing_keys(tmp_path):
    _make_locale_resource(tmp_path, {
        "en": {"hello": "Hello", "bye": "Bye"},
        "de": {"hello": "Hallo"},  # missing 'bye'
    })

    reports = locale_checker.check_resources(str(tmp_path))
    assert reports
    r = reports[0]
    assert set(r.languages) == {"en", "de"}
    assert "de" in r.missing
    assert "bye" in r.missing["de"]


def test_detects_undefined_refs(tmp_path):
    _make_locale_resource(
        tmp_path,
        {"en": {"hello": "Hello"}},
        lua_calls=[
            "local msg = _U('hello')",
            "local missing = _U('nope_undefined')",
        ],
    )
    reports = locale_checker.check_resources(str(tmp_path))
    r = reports[0]
    assert "nope_undefined" in r.undefined_refs
    assert "hello" not in r.undefined_refs
