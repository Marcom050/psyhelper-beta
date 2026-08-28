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


def test_patient_surfaces_use_shared_date_formatter():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    assert "format_display_date(row.get('data'), include_time=True" in source
    assert "format_display_date(entry.get('created_at'), compact=True)" in source
    assert "return format_display_date(value, compact=True" in source
