"""Optional intelligence provider settings, without LLM-writable secrets.

Design intentionally follows the GitHub/Playwright/Context7 MCP pattern:
separate feature surface, explicit configuration, environment overrides, and
read-only configuration discovery. Windows stores keys in the current user's
native Credential Manager (DPAPI-backed). Other operating systems use injected
environment variables; there is no insecure plaintext fallback.

This module never imports the production TrendPulse server or enables agents.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Any

# Every credential name is controlled by this static allowlist.
PROVIDERS: dict[str, dict[str, Any]] = {
    "openalex": {
        "fields": ("TRENDPULSE_INTEL_OPENALEX_KEY",),
        "docs": "https://help.openalex.org/api/",
        "free": "Keyless basic queries available; optional registered free key with $1/day allowance",
        "keyless_basic_queries_available": True,
    },
    "companies_house": {
        "fields": ("TRENDPULSE_INTEL_COMPANIES_HOUSE_KEY",),
        "docs": "https://developer.company-information.service.gov.uk/",
        "free": "Free registration, 600 requests / 5 minutes upstream",
    },
    "epo": {
        "fields": ("TRENDPULSE_INTEL_EPO_CONSUMER_KEY",
                   "TRENDPULSE_INTEL_EPO_CONSUMER_SECRET"),
        "docs": "https://www.epo.org/en/searching-for-patents/data/web-services/ops",
        "free": "Registered OPS access with 4 GB/week free download allowance; no paid fallback",
    },
    "entsoe": {
        "fields": ("TRENDPULSE_INTEL_ENTSOE_TOKEN",),
        "docs": "https://transparency.entsoe.eu/",
        "free": "Free transparency API token subject to approval and fair use",
    },
    "changedetection_local": {
        "fields": ("TRENDPULSE_INTEL_CHANGEDETECTION_KEY",),
        "docs": "https://changedetection.io/docs/api_v1/",
        "free": "Only your self-hosted loopback instance, no hosted subscription",
    },
    "bing_webmaster": {
        "fields": ("BING_WEBMASTER_API_KEY",),
        "docs": "https://learn.microsoft.com/en-us/bingwebmaster/getting-access",
        "free": "Free Bing Webmaster API key from a verified-site account; "
                "global keyword research methods do not take a siteUrl",
    },
}

_TARGET_PREFIX = "mcp-trendpulse:intelligence:"
_ERROR_NOT_FOUND = 1168


class SecureStoreUnavailable(RuntimeError):
    """The platform does not offer the native credential store used by this tool."""


def _supports_native_store() -> bool:
    return os.name == "nt"


def _credential_type():
    class Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]
    return Credential


def _win_api():
    if not _supports_native_store():
        raise SecureStoreUnavailable(
            "Native secure key storage is available on Windows only. "
            "Use your MCP client's secure environment-variable configuration on this host."
        )
    kind = _credential_type()
    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredWriteW.argtypes = [ctypes.POINTER(kind), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(kind)),
    ]
    api.CredReadW.restype = wintypes.BOOL
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    return kind, api


def _field(name: str) -> str:
    if name not in {field for p in PROVIDERS.values() for field in p["fields"]}:
        raise ValueError("Unknown provider credential field")
    return name


def _read_secret(name: str) -> str | None:
    kind, api = _win_api()
    ptr = ctypes.POINTER(kind)()
    if not api.CredReadW(_TARGET_PREFIX + _field(name), 1, 0, ctypes.byref(ptr)):
        code = ctypes.get_last_error()
        if code == _ERROR_NOT_FOUND:
            return None
        raise OSError("Windows Credential Manager read failed")
    try:
        data = ctypes.string_at(ptr.contents.CredentialBlob,
                                ptr.contents.CredentialBlobSize)
        return data.decode("utf-16-le")
    finally:
        api.CredFree(ptr)


def _write_secret(name: str, secret: str) -> None:
    kind, api = _win_api()
    if not isinstance(secret, str) or not secret.strip() or "\x00" in secret:
        raise ValueError("Credential must be a nonempty single string")
    raw = secret.encode("utf-16-le")
    if len(raw) > 2560:
        raise ValueError("Credential exceeds Windows Credential Manager size limit")
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    record = kind()
    record.Flags = 0
    record.Type = 1  # CRED_TYPE_GENERIC
    record.TargetName = _TARGET_PREFIX + _field(name)
    record.Comment = "Local, opt-in TrendPulse intelligence provider"
    record.CredentialBlobSize = len(raw)
    record.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    record.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE, current OS user
    record.UserName = "mcp-trendpulse"
    if not api.CredWriteW(ctypes.byref(record), 0):
        raise OSError("Windows Credential Manager write failed")


def _delete_secret(name: str) -> None:
    _, api = _win_api()
    if not api.CredDeleteW(_TARGET_PREFIX + _field(name), 1, 0):
        if ctypes.get_last_error() != _ERROR_NOT_FOUND:
            raise OSError("Windows Credential Manager delete failed")


def resolved_environment(env: dict[str, str] | None = None,
                         provider: str | None = None) -> dict[str, str]:
    """Environment wins; native OS keychain is a local-user fallback only.

    Explicit env={} bypasses the OS store so tests and servers are hermetic.
    Never include values in returned MCP settings/tool output.
    """
    result = dict(os.environ if env is None else env)
    if env is not None or not _supports_native_store():
        return result
    # Avoid unnecessarily loading unrelated provider keys into the process.
    profiles = (PROVIDERS[provider],) if provider in PROVIDERS else (
        PROVIDERS.values() if provider is None else ()
    )
    for config in profiles:
        for name in config["fields"]:
            if not result.get(name):
                value = _read_secret(name)
                if value:
                    result[name] = value
    return result


def provider_status(provider: str | None = None,
                    env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Safe metadata suitable for an MCP tool and client settings screen."""
    if provider is not None and provider not in PROVIDERS:
        raise ValueError("Unknown configured provider")
    environment = resolved_environment(env)
    rows = []
    for name, metadata in PROVIDERS.items():
        if provider is not None and provider != name:
            continue
        fields = [{"env_name": field, "configured": bool(environment.get(field))}
                  for field in metadata["fields"]]
        rows.append({
            "provider": name,
            "fields": fields,
            "ready_for_live_auth_test": all(entry["configured"] for entry in fields),
            "keyless_basic_queries_available": bool(
                metadata.get("keyless_basic_queries_available", False)
            ),
            "free_allowance": metadata["free"],
            "documentation": metadata["docs"],
            "secret_storage": "Windows Credential Manager or environment variables",
            "configured_is_not_verified": True,
        })
    return rows


def setup_instructions(provider: str) -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise ValueError("Unknown configured provider")
    meta = PROVIDERS[provider]
    return {
        "provider": provider,
        "documentation": meta["docs"],
        "free_allowance": meta["free"],
        "field_names": list(meta["fields"]),
        "credential_optional_for_basic_queries": bool(
            meta.get("keyless_basic_queries_available", False)
        ),
        "windows_command": f"mcp-trendpulse-cli intelligence settings set-key {provider}",
        "all_platforms": "Use your MCP client's secure environment-variable injection.",
        "safety": (
            "Only the human user should enter keys in a trusted terminal or "
            "credential manager. Bing's official GET API requires apikey as an "
            "HTTPS request parameter, so the fixed-host transport uses it only "
            "in flight; never echo the authenticated URL or key into logs, "
            "prompts, MCP arguments, GitHub files or chat."
            if provider == "bing_webmaster" else
            "Only the human user should enter keys in a trusted local terminal or "
            "credential manager. Never put secrets in prompts, MCP tool arguments, "
            "GitHub files, URL query parameters or chat messages."
        ),
    }


def save_provider_credentials(provider: str, values: dict[str, str]) -> None:
    """Explicit local-CLI action. Restores earlier keys if a write fails."""
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider")
    if not _supports_native_store():
        raise SecureStoreUnavailable(
            "Native key storage requires Windows. Use secure MCP environment injection."
        )
    names = PROVIDERS[provider]["fields"]
    if set(values) != set(names):
        raise ValueError("All required credential fields must be supplied")
    previous = {name: _read_secret(name) for name in names}
    written = []
    try:
        for name in names:
            _write_secret(name, values[name])
            written.append(name)
    except Exception:
        for name in reversed(written):
            if previous[name] is None:
                _delete_secret(name)
            else:
                _write_secret(name, previous[name])
        raise


def clear_provider_credentials(provider: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider")
    if not _supports_native_store():
        raise SecureStoreUnavailable(
            "Native key storage requires Windows. Remove environment secrets from the client."
        )
    for name in PROVIDERS[provider]["fields"]:
        _delete_secret(name)
