from pathlib import Path
import inspect
import re

import psyhelper_streamlit as app


def test_display_date_rejects_epoch_and_legacy_sentinels():
    for value in (None, "", "not-a-date", 0, "1970-01-01T00:00:00+00:00"):
        assert app.format_display_date(value) == "—"
    assert app.format_display_date("2026-08-06T16:31:11+00:00", include_time=True) == "6 agosto 2026 · 16:31"


def test_design_system_preserves_material_symbol_fonts():
    css = app.DESIGN_SYSTEM_CSS
    assert 'html, body, [class*="st-"]' not in css
    assert ".material-symbols-rounded" in css
    assert 'font-family: "Material Symbols Rounded"' in css


def test_primary_form_submit_matches_current_streamlit_structure():
    css = app.DESIGN_SYSTEM_CSS
    assert '[data-testid="stFormSubmitButton"] button[kind="primary"]' in css
    assert '[data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primary"]' in css
    assert "background: var(--psy-primary) !important" in css
    assert "background: var(--psy-primary-hover) !important" in css


def test_warm_theme_tokens_and_secondary_button_contrast_are_global():
    css = app.DESIGN_SYSTEM_CSS
    for token in ("#FFFCFA", "#FFFFFF", "#FFF5F0", "#29282B", "#706A68", "#EADFD9", "#C84E3A"):
        assert token in css
    assert "color: var(--psy-text) !important; background: var(--psy-surface) !important" in css
    assert "rgba(200, 78, 58, .22)" in css


def test_streamlit_native_theme_matches_product_palette():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'fileWatcherType = "none"' in config
    assert 'primaryColor = "#C84E3A"' in config
    assert 'backgroundColor = "#FFFCFA"' in config
    assert 'secondaryBackgroundColor = "#FFF5F0"' in config
    assert 'textColor = "#29282B"' in config
    assert "#FF4B4B" not in config


def test_bridge_renderers_do_not_apply_character_ellipsis():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    card_source = source[source.index("def _session_bridge_card"):source.index("def _session_bridge_draft_preview")]
    assert "[:177]" not in card_source
    assert "len(summary)" not in card_source
    assert "white-space: pre-wrap" in app.DESIGN_SYSTEM_CSS


def test_patient_surfaces_use_shared_date_formatter():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "format_display_date(row.get('data'), include_time=True" in source
    assert "format_display_date(entry.get('created_at'), compact=True)" in source
    assert "return format_display_date(value, compact=True" in source


def test_all_runtime_checked_checkbox_css_can_only_paint_the_graphic_box():
    """Audit both CSS blocks loaded by the real entrypoint, including the later guard."""
    combined_css = app.DESIGN_SYSTEM_CSS + inspect.getsource(app.SessionAdapter._render_ui_regression_guards)
    checked_rules = re.findall(r"([^{}]*checked[^{}]*)\{([^{}]*)\}", combined_css, flags=re.IGNORECASE)
    checkbox_rules = [(selector, declarations) for selector, declarations in checked_rules if "checkbox" in selector.lower()]

    assert checkbox_rules
    for selector, declarations in checkbox_rules:
        assert '> div:first-of-type' in selector
        assert '[data-testid="stWidgetLabel"]' not in selector
        properties = {declaration.split(":", 1)[0].strip() for declaration in declarations.split(";") if ":" in declaration}
        assert properties <= {"background-color", "border-color"}

    # The text node is reset by the later, more specific runtime block too.
    guard_source = inspect.getsource(app.SessionAdapter._render_ui_regression_guards)
    assert '> [data-testid="stWidgetLabel"]' in guard_source
    for declaration in ("color:", "background:", "font-weight:", "opacity:", "-webkit-text-fill-color:"):
        assert declaration in guard_source
