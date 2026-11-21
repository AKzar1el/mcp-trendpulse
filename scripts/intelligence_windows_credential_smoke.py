"""True Windows Credential Manager roundtrip with a disposable fake key.

No real provider contact, no API secret, no upload, no logs of credential
material. Run on GitHub's ephemeral Windows runner, not on a user's machine.
"""

from __future__ import annotations

import os
import sys
from uuid import uuid4

from mcp_trendpulse import intelligence_settings as keys


def main() -> None:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Only run this smoke on an ephemeral Windows GitHub Actions runner")
    name = keys.PROVIDERS["openalex"]["fields"][0]
    if os.environ.get(name):
        raise RuntimeError("Provider environment variable unexpectedly already set")
    # Test record is random and is never output. It is not a provider credential.
    dummy = "local-smoke-nonsecret-" + uuid4().hex
    existed = keys._read_secret(name)
    if existed is not None:
        raise RuntimeError("Unexpected preexisting test target; refusing to overwrite it")
    try:
        keys.save_provider_credentials("openalex", {name: dummy})
        assert keys._read_secret(name) == dummy
        status = keys.provider_status("openalex")
        assert status[0]["ready_for_live_auth_test"]
        assert status[0]["fields"][0]["configured"]
        assert dummy not in repr(status)
        assert dummy not in repr(keys.setup_instructions("openalex"))
        print("WinCred: save/read/status redaction verified")
    finally:
        keys.clear_provider_credentials("openalex")
    assert keys._read_secret(name) is None
    print("WinCred: disposable credential removal verified")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("WinCred test failed; no credential values were logged", file=sys.stderr)
        raise SystemExit(1) from None
