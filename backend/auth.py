"""
One-time Google authorization.

Run this once, in your own terminal, before starting agent.py:

    python auth.py

It opens a browser for consent and writes token.json next to
this file. The MCP server never prompts on its own -- it only
reads the token this script produces.
"""

import sys

from mcp_server import (
    CREDENTIALS_FILE,
    SCOPES,
    TOKEN_FILE,
    run_consent_flow,
)


def main():

    print()
    print("=" * 60)
    print("Google Authorization")
    print("=" * 60)
    print()
    print(f"OAuth client : {CREDENTIALS_FILE}")
    print(f"Token output : {TOKEN_FILE}")
    print()
    print("Scopes requested:")

    for scope in SCOPES:
        print(f"  - {scope}")

    print()

    if TOKEN_FILE.exists():

        print("token.json already exists.")
        print("Delete it first if you want to re-authorize.")
        print()
        return 0

    if not CREDENTIALS_FILE.exists():

        print(f"ERROR: {CREDENTIALS_FILE} not found.")
        print()
        return 1

    print("Opening browser for consent...")
    print()

    credentials = run_consent_flow()

    print()
    print("Authorized.")
    print(f"Token written to {TOKEN_FILE}")
    print()

    return 0 if credentials else 1


if __name__ == "__main__":
    sys.exit(main())
