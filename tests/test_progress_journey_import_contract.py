import importlib


def test_progress_journey_import_contract():
    service = importlib.import_module("services.progress_journey_service")
    assert hasattr(service, "build_progress_journey_summary")
    assert hasattr(service, "normalize_progress_timeline_event")


def test_psyhelper_streamlit_module_imports():
    importlib.import_module("psyhelper_streamlit")
