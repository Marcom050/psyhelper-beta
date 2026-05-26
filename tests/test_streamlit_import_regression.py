import ast
import importlib
from pathlib import Path


def test_psyhelper_streamlit_imports_cleanly():
    importlib.import_module("psyhelper_streamlit")


def test_streamlit_auth_service_import_contract_is_valid():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "services.auth_service":
            imported_names = [alias.name for alias in node.names]
            break

    assert imported_names, "Expected auth_service imports in psyhelper_streamlit.py"

    auth_service = importlib.import_module("services.auth_service")
    missing = [name for name in imported_names if not hasattr(auth_service, name)]
    assert not missing, f"Missing names in services.auth_service: {missing}"


def test_delete_user_account_is_directly_importable_from_auth_service():
    from services.auth_service import delete_user_account

    assert callable(delete_user_account)


def test_progress_journey_builder_is_imported_from_service():
    source = Path("psyhelper_streamlit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "services.progress_journey_service":
            imported_names = [alias.name for alias in node.names]
            break

    assert "build_progress_journey_summary" in imported_names

    service = importlib.import_module("services.progress_journey_service")
    assert hasattr(service, "build_progress_journey_summary")
