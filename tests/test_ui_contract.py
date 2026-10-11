"""Static UI-contract tests.

These guard the web front-end against silent regressions without needing a
browser: element ids referenced by app.js must exist in index.html, every
data-i18n key must be translated, EN/ES dictionaries must agree, and the
field/output types offered by the editor must match the backend models.
"""
import re
import typing
from pathlib import Path
from typing import Union

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


def _unwrap_union(union):
    origin = typing.get_origin(union)
    if origin is typing.Annotated:
        union = typing.get_args(union)[0]
        origin = typing.get_origin(union)
    if origin is Union:
        return typing.get_args(union)
    return (union,)


def _backend_types(union):
    return {m.model_fields["type"].default for m in _unwrap_union(union)}


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


def test_hidden_attribute_overrides_display_flex():
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", css)


def test_static_assets_are_cache_busted():
    assert re.search(r"/static/styles\.css\?v=", HTML)
    assert re.search(r"/static/app\.js\?v=", HTML)
    assert re.search(r"/static/i18n\.js\?v=", HTML)


def test_field_defaults_and_schema_cover_same_types():
    defaults = set(_defaults_keys("FIELD_DEFAULTS"))
    schema = set(re.findall(
        r"(\w+):\s*\[", re.search(
            r"const FIELD_SCHEMA = \{(.*?)\n\};", APP_JS, re.DOTALL).group(1)))
    assert defaults == schema, f"FIELD_DEFAULTS vs FIELD_SCHEMA drift: {defaults ^ schema}"


def _css_vars(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block))


def _theme_blocks():
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    dark = re.search(r":root\s*\{(.*?)\n\}", css, re.DOTALL)
    light = re.search(r'\[data-theme="light"\]\s*\{(.*?)\n\}', css, re.DOTALL)
    assert dark and light, "dark :root and [data-theme=light] palettes are required"
    return _css_vars(dark.group(1)), _css_vars(light.group(1)), css


def test_app_title_is_short_in_both_languages():
    assert I18N_JS.count('"app.title": "IoT Simulator"') == 2
    assert "IoT Simulator" in HTML
    assert "IoT Device Simulator" not in I18N_JS
    assert "Simulador de Dispositivos" not in I18N_JS


def test_github_pill_points_to_aparedero():
    assert "github.com/aparedero/iot-simulator" in HTML
    assert "@aparedero" in HTML
    assert 'class="gh-pill"' in HTML


def test_theme_palettes_are_visibly_distinct():
    dark, light, css = _theme_blocks()
    for token in (
        "--bg", "--surface", "--text", "--payload-bg", "--payload-fg",
        "--log-bg", "--log-fg",
    ):
        assert token in dark, f"dark palette missing {token}"
        assert token in light, f"light palette missing {token}"
        assert dark[token].strip() != light[token].strip(), (
            f"{token} is identical in light and dark themes"
        )
    assert re.search(r"color-scheme\s*:\s*dark", css)
    assert re.search(r"color-scheme\s*:\s*light", css)


def test_theme_toggle_applies_color_scheme():
    assert "colorScheme" in APP_JS
    assert "themeToggle" in APP_JS
    assert "theme.toLight" in I18N_JS
    assert "theme.toDark" in I18N_JS


def test_log_entries_use_full_width_grid():
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"\.log-entry\s*\{[^}]*display:\s*grid", css, re.DOTALL)
    assert re.search(r"\.log-entry\s*\{[^}]*minmax\(0,\s*1fr\)", css, re.DOTALL)
    assert re.search(r"\.log-entry\s+\.data\s*\{[^}]*min-width:\s*0", css, re.DOTALL)
    assert re.search(r"overflow-wrap:\s*anywhere", css)
