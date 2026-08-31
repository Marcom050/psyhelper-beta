from copy import deepcopy
from pathlib import Path

import psyhelper_streamlit as app


def _events(count):
    return [
        {"date_label": f"2026-08-{index + 1:02d}", "type": "homework" if index % 2 else "step_forward", "title": str(index)}
        for index in range(count)
    ]


def test_timeline_limit_order_categories_and_source_immutability():
    events = _events(12)
    original = deepcopy(events)
    visible = app.timeline_events_for_display(events, limit=5)
    assert [event["title"] for event in visible] == ["11", "10", "9", "8", "7"]
    assert {event["type"] for event in visible} == {"homework", "step_forward"}
    assert events == original
    assert len(app.timeline_events_for_display(events)) == 12
    assert len(app.timeline_events_for_display(_events(3), limit=5)) == 3


def test_timeline_progressive_disclosure_has_no_dead_button_or_recap_duplicate():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    timeline = source[source.index("    with detail_tabs[3]:"):source.index("    with detail_tabs[4]:")]
    assert 'show_all_key = "therapist_timeline_show_all"' in timeline
    assert "if len(journey_events) > initial_limit:" in timeline
    assert '"Mostra meno" if show_all' in timeline
    assert 'f"Mostra tutta la timeline ({len(journey_events)})"' in timeline
    assert 'with st.expander("+ Aggiungi una nota alla timeline", expanded=False):' in timeline
    assert "TIMELINE_SECTION_ORDER" not in source
    assert "Cosa sta succedendo" not in timeline
    assert "Punti da riprendere in seduta" not in timeline


def test_authenticated_sticky_offsets_and_checkbox_colors_are_semantic():
    css = app.DESIGN_SYSTEM_CSS
    assert "--psy-streamlit-header-offset: 3.5rem" in css
    assert "top: var(--psy-streamlit-header-offset)" in css
    assert "top: 0" not in css
    assert "top: -" not in css
    assert ".st-key-authenticated_patient_toolbar { position: static; }" in css
    assert ".st-key-therapist_global_toolbar { position: static; }" in css
    assert 'label[data-baseweb="checkbox"]:has(> input:checked) > div:first-of-type' in css
    assert 'input:checked + div' not in css
