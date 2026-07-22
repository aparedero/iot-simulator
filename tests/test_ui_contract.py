"""Static UI-contract tests.

These guard the web front-end against silent regressions without needing a
browser: element ids referenced by app.js must exist in index.html, every
data-i18n key must be translated, EN/ES dictionaries must agree, and the
field/output types offered by the editor must match the backend models.
"""
import re
import typing
from pathlib import Path

from app.models import FieldConfig, OutputConfig

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")
I18N_JS = (STATIC / "i18n.js").read_text(encoding="utf-8")


def _html_ids():
    return set(re.findall(r'id="([\w-]+)"', HTML))


def _js_ref_ids():
    # $("id") / $('id') / $(`id`)
    return set(re.findall(r"""\$\(\s*["'`]([\w-]+)["'`]\s*\)""", APP_JS))


def _translation_keys():
    # every "some.key": defined anywhere in the i18n dictionaries
    return set(re.findall(r'"([\w.]+)"\s*:', I18N_JS))


def _dict_block(lang):
    m = re.search(rf"{lang}:\s*\{{(.*?)\n  \}},", I18N_JS, re.DOTALL)
    assert m, f"could not locate '{lang}' dictionary block"
    return set(re.findall(r'"([\w.]+)"\s*:', m.group(1)))


def _defaults_keys(name):
    m = re.search(rf"const {name} = \{{(.*?)\n\}};", APP_JS, re.DOTALL)
    assert m, f"could not locate {name}"
    return dict(re.findall(r'(\w+):\s*\{\s*type:\s*"([^"]+)"', m.group(1)))


def _backend_types(union):
    return {m.model_fields["type"].default for m in typing.get_args(union)}


def test_all_referenced_ids_exist_in_html():
    missing = _js_ref_ids() - _html_ids()
    assert not missing, f"app.js references ids absent from index.html: {sorted(missing)}"


def test_examples_feature_wired():
    # The web "load examples" feature must be present end to end.
    for eid in ("btnExamples", "examplesModalBg", "examplesList",
                "btnExamplesClose", "btnExamplesClose2"):
        assert eid in _html_ids(), f"missing element #{eid}"
    assert "openExamples" in APP_JS
    assert "/api/examples" in APP_JS


def test_every_data_i18n_key_is_translated():
    keys = set(re.findall(r'data-i18n(?:-placeholder)?="([\w.]+)"', HTML))
    missing = keys - _translation_keys()
    assert not missing, f"data-i18n keys with no translation: {sorted(missing)}"


def test_en_es_dictionaries_agree():
    en, es = _dict_block("en"), _dict_block("es")
    assert en == es, f"EN/ES key mismatch: only_en={sorted(en - es)} only_es={sorted(es - en)}"


def test_editor_field_types_match_backend():
    ui = _defaults_keys("FIELD_DEFAULTS")
    # JS key and its declared "type" must be identical
    for k, v in ui.items():
        assert k == v, f"FIELD_DEFAULTS['{k}'] declares type '{v}'"
    assert set(ui) == _backend_types(FieldConfig)


def test_editor_output_types_match_backend():
    ui = _defaults_keys("OUTPUT_DEFAULTS")
    for k, v in ui.items():
        assert k == v, f"OUTPUT_DEFAULTS['{k}'] declares type '{v}'"
    assert set(ui) == _backend_types(OutputConfig)


def test_field_defaults_and_schema_cover_same_types():
    defaults = set(_defaults_keys("FIELD_DEFAULTS"))
    schema = set(re.findall(
        r"(\w+):\s*\[", re.search(
            r"const FIELD_SCHEMA = \{(.*?)\n\};", APP_JS, re.DOTALL).group(1)))
    assert defaults == schema, f"FIELD_DEFAULTS vs FIELD_SCHEMA drift: {defaults ^ schema}"
