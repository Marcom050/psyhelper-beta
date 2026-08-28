from pathlib import Path

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
    for token in ("#FBF8F5", "#2C2725", "#746A66", "#E6DDD7", "#6F4B5A", "#C9785F"):
        assert token in css
    assert "color: var(--psy-text) !important; background: var(--psy-surface) !important" in css
    assert "rgba(111, 75, 90, .24)" in css


def test_streamlit_native_theme_matches_product_palette():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'fileWatcherType = "none"' in config
    assert 'primaryColor = "#6F4B5A"' in config
    assert 'backgroundColor = "#FBF8F5"' in config
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
