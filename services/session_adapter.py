from dataclasses import dataclass
from typing import Any, Callable

import streamlit as st

from services.auth_service import (
    default_wellness_data,
    ensure_wellness_schema,
    load_account_bundle,
    load_user_metadata,
    save_account_bundle,
)


@dataclass
class AppSessionData:
    username: str | None
    logged_in: bool
    profile: dict[str, Any]
    messages: list[dict[str, Any]]
    wellness: dict[str, Any]
    user_metadata: dict[str, Any]
    selected_patient_username: str | None
    analytics_consent: bool
    beta_disclaimer_accepted: bool
    scroll_to_top: bool


class SessionAdapter:
    def __init__(
        self,
        session_state: Any | None = None,
        *,
        default_wellness_factory: Callable[[], dict[str, Any]] = default_wellness_data,
        load_account_bundle_func: Callable[[str], dict[str, Any]] = load_account_bundle,
        load_user_metadata_func: Callable[[str], dict[str, Any]] = load_user_metadata,
        save_account_bundle_func: Callable[[str, dict[str, Any], list[dict[str, Any]], dict[str, Any]], None] = save_account_bundle,
        ensure_wellness_schema_func: Callable[[dict[str, Any]], None] = ensure_wellness_schema,
    ):
        self._session_state = session_state if session_state is not None else st.session_state
        self._default_wellness_factory = default_wellness_factory
        self._load_account_bundle = load_account_bundle_func
        self._load_user_metadata = load_user_metadata_func
        self._save_account_bundle = save_account_bundle_func
        self._ensure_wellness_schema = ensure_wellness_schema_func

    def _get(self, key: str, default: Any = None) -> Any:
        return self._session_state.get(key, default)

    def _set(self, key: str, value: Any) -> None:
        self._session_state[key] = value

    def _setdefault(self, key: str, default: Any) -> Any:
        return self._session_state.setdefault(key, default)

    def _pop(self, key: str, default: Any = None) -> Any:
        return self._session_state.pop(key, default)

    def get_session_data(self) -> AppSessionData:
        return AppSessionData(
            username=self.get_username(),
            logged_in=self.is_logged_in(),
            profile=self.get_profile(),
            messages=self.get_messages(),
            wellness=self.get_wellness(),
            user_metadata=self.get_user_metadata(),
            selected_patient_username=self.get_selected_patient_username(),
            analytics_consent=self.get_analytics_consent(),
            beta_disclaimer_accepted=self.is_beta_disclaimer_accepted(),
            scroll_to_top=self.get_scroll_to_top(),
        )

    def initialize_defaults(self) -> None:
        self._setdefault("username", None)
        self._setdefault("logged_in", False)
        self._setdefault("profile", {})
        self._setdefault("messages", [])
        self._setdefault("wellness", self._default_wellness_factory())
        self._setdefault("user_metadata", {})
        self._setdefault("selected_patient_username", None)
        self._setdefault("analytics_consent", False)
        self._setdefault("beta_disclaimer_accepted", False)
        self._setdefault("scroll_to_top", False)
        if not isinstance(self.get_wellness(), dict):
            self.set_wellness(self._default_wellness_factory())
        self._ensure_wellness_schema(self.get_wellness())

    def load_user_session(self, username: str) -> None:
        bundle = self._load_account_bundle(username)
        self.set_user_metadata(self._load_user_metadata(username))
        self.set_profile(bundle["profile"])
        self.set_messages(bundle["messages"])
        self.set_wellness(bundle["wellness"])

    def persist_user_session(self, username: str | None = None) -> None:
        effective_username = username or self.get_username()
        if not effective_username:
            return
        self._save_account_bundle(
            effective_username,
            self.get_profile(),
            self.get_messages(),
            self.get_wellness(),
        )

    def reset_for_logout(self) -> None:
        self.set_logged_in(False)
        self.set_username(None)
        self.set_user_metadata({})
        self.set_profile({})
        self.set_messages([])
        self.set_wellness(self._default_wellness_factory())
        self.set_scroll_to_top(True)

    def get_profile(self) -> dict[str, Any]:
        return self._get("profile", {})

    def set_profile(self, profile: dict[str, Any]) -> None:
        self._set("profile", profile)

    def get_messages(self) -> list[dict[str, Any]]:
        return self._get("messages", [])

    def set_messages(self, messages: list[dict[str, Any]]) -> None:
        self._set("messages", messages)

    def get_wellness(self) -> dict[str, Any]:
        wellness = self._get("wellness")
        if not isinstance(wellness, dict):
            wellness = self._default_wellness_factory()
            self.set_wellness(wellness)
        return wellness

    def set_wellness(self, wellness: dict[str, Any]) -> None:
        self._set("wellness", wellness)

    def get_username(self) -> str | None:
        return self._get("username")

    def set_username(self, username: str | None) -> None:
        self._set("username", username)

    def is_logged_in(self) -> bool:
        return bool(self._get("logged_in", False))

    def set_logged_in(self, logged_in: bool) -> None:
        self._set("logged_in", logged_in)

    def get_user_metadata(self) -> dict[str, Any]:
        return self._get("user_metadata", {})

    def set_user_metadata(self, user_metadata: dict[str, Any]) -> None:
        self._set("user_metadata", user_metadata)

    def get_selected_patient_username(self) -> str | None:
        return self._get("selected_patient_username")

    def set_selected_patient_username(self, username: str | None) -> None:
        self._set("selected_patient_username", username)

    def get_analytics_consent(self) -> bool:
        return bool(self._get("analytics_consent", False))

    def set_analytics_consent(self, consent: bool) -> None:
        self._set("analytics_consent", consent)

    def is_beta_disclaimer_accepted(self) -> bool:
        return bool(self._get("beta_disclaimer_accepted", False))

    def accept_beta_disclaimer(self, accepted_at: str) -> None:
        self._set("beta_disclaimer_accepted", True)
        self._set("beta_disclaimer_accepted_at", accepted_at)

    def get_beta_disclaimer_accepted_at(self, default: str) -> str:
        return self._get("beta_disclaimer_accepted_at", default)

    def get_scroll_to_top(self) -> bool:
        return bool(self._get("scroll_to_top", False))

    def set_scroll_to_top(self, scroll_to_top: bool) -> None:
        self._set("scroll_to_top", scroll_to_top)

    def pop_scroll_to_top(self) -> bool:
        return bool(self._pop("scroll_to_top", False))

    def ensure_authenticated_defaults(self, username: str | None = None) -> None:
        self._setdefault("profile", {})
        self._setdefault("messages", [])
        self._setdefault("wellness", self._default_wellness_factory())
        effective_username = username or self.get_username()
        if effective_username:
            self._setdefault("user_metadata", self._load_user_metadata(effective_username))
        else:
            self._setdefault("user_metadata", {})
        if not isinstance(self.get_wellness(), dict):
            self.set_wellness(self._default_wellness_factory())
        self._ensure_wellness_schema(self.get_wellness())
