from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_dotenv_file(env_path: Path) -> None:
    """Lightweight .env loader so the script works without extra dependencies."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def check_presence(name: str, *, optional: bool = False) -> tuple[str, str]:
    value = os.getenv(name, "").strip()
    if value:
        return "PASS", value
    if optional:
        return "SKIP", "not set (optional)"
    return "FAIL", "missing"


def check_pattern(name: str, pattern: str, help_text: str) -> tuple[str, str]:
    value = os.getenv(name, "").strip()
    if not value:
        return "FAIL", "missing"
    if re.fullmatch(pattern, value):
        return "PASS", value
    return "FAIL", help_text


def print_result(name: str, status: str, detail: str) -> None:
    print(f"[{status}] {name}: {detail}")


def validate_env() -> tuple[list[tuple[str, str, str]], list[str]]:
    results: list[tuple[str, str, str]] = []
    results.append(
        (
            "AZURE_SUBSCRIPTION_ID",
            *check_pattern(
                "AZURE_SUBSCRIPTION_ID",
                r"[0-9a-fA-F-]{36}",
                "expected a subscription GUID like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            ),
        )
    )
    results.append(("AZURE_RESOURCE_GROUP", *check_presence("AZURE_RESOURCE_GROUP")))
    results.append(("AZURE_LOCATION", *check_presence("AZURE_LOCATION")))
    results.append(
        (
            "AZURE_OPENAI_ENDPOINT",
            *check_pattern(
                "AZURE_OPENAI_ENDPOINT",
                r"https://[a-zA-Z0-9-]+\.openai\.azure\.com/?",
                "expected format https://<resource>.openai.azure.com",
            ),
        )
    )
    results.append(("AZURE_OPENAI_MODEL", *check_presence("AZURE_OPENAI_MODEL")))
    results.append(
        (
            "AZURE_OPENAI_API_KEY",
            *check_presence("AZURE_OPENAI_API_KEY", optional=True),
        )
    )
    results.append(
        (
            "AZURE_SEARCH_ENDPOINT",
            *check_pattern(
                "AZURE_SEARCH_ENDPOINT",
                r"https://[a-zA-Z0-9-]+\.search\.windows\.net/?",
                "expected format https://<service>.search.windows.net",
            ),
        )
    )
    results.append(
        ("AZURE_SEARCH_INDEX_NAME", *check_presence("AZURE_SEARCH_INDEX_NAME"))
    )
    results.append(
        ("AZURE_SEARCH_API_KEY", *check_presence("AZURE_SEARCH_API_KEY", optional=True))
    )
    results.append(
        (
            "AZURE_STORAGE_ACCOUNT_URL",
            *check_pattern(
                "AZURE_STORAGE_ACCOUNT_URL",
                r"https://[a-zA-Z0-9-]+\.blob\.core\.windows\.net/?",
                "expected format https://<storage-account>.blob.core.windows.net",
            ),
        )
    )
    results.append(
        ("AZURE_STORAGE_CONTAINER", *check_presence("AZURE_STORAGE_CONTAINER"))
    )
    results.append(
        (
            "AZURE_KEY_VAULT_URL",
            *check_pattern(
                "AZURE_KEY_VAULT_URL",
                r"https://[a-zA-Z0-9-]+\.vault\.azure\.net/?",
                "expected format https://<vault-name>.vault.azure.net",
            ),
        )
    )
    missing_required = [name for name, status, _ in results if status == "FAIL"]
    return results, missing_required


def build_search_credential():
    search_api_key = os.getenv("AZURE_SEARCH_API_KEY", "").strip()
    if search_api_key:
        from azure.core.credentials import AzureKeyCredential

        return AzureKeyCredential(search_api_key), "api_key"

    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(), "default_azure_credential"


def test_search_service() -> tuple[str, str]:
    from azure.search.documents.indexes import SearchIndexClient

    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
    credential, mode = build_search_credential()
    client = SearchIndexClient(endpoint=endpoint, credential=credential)

    try:
        client.get_index(index_name)
        return "PASS", f"connected via {mode}; index '{index_name}' exists"
    except Exception as exc:
        error_text = str(exc)
        if "ResourceNotFoundError" in type(exc).__name__ or "No index" in error_text:
            return "WARN", (
                f"connected via {mode}, but index '{index_name}' does not exist yet"
            )
        raise


def test_storage_service() -> tuple[str, str]:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    account_url = os.environ["AZURE_STORAGE_ACCOUNT_URL"]
    container_name = os.environ["AZURE_STORAGE_CONTAINER"]

    client = BlobServiceClient(
        account_url=account_url,
        credential=DefaultAzureCredential(),
    )
    container_client = client.get_container_client(container_name)

    if container_client.exists():
        return (
            "PASS",
            f"connected with DefaultAzureCredential; container '{container_name}' exists",
        )

    return (
        "WARN",
        f"connected with DefaultAzureCredential, but container '{container_name}' does not exist yet",
    )


def test_key_vault_service() -> tuple[str, str]:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    vault_url = os.environ["AZURE_KEY_VAULT_URL"]
    client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())

    pager = client.list_properties_of_secrets().by_page()
    first_page = next(pager, [])
    secret_count = len(list(first_page))
    return (
        "PASS",
        f"connected with DefaultAzureCredential; first page returned {secret_count} secret metadata entries",
    )


def test_openai_service() -> tuple[str, str]:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    model = os.environ["AZURE_OPENAI_MODEL"]
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    base_url = f"{endpoint.rstrip('/')}/openai/v1/"

    if api_key:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        auth_mode = "api_key"
    else:
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )
        client = OpenAI(
            api_key=token_provider,
            base_url=base_url,
        )
        auth_mode = "default_azure_credential"

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with OK"}],
        max_completion_tokens=5,
    )
    message = response.choices[0].message.content if response.choices else "no output"
    return "PASS", f"connected via {auth_mode}; sample response: {message!r}"


def run_live_service_checks(*, include_openai: bool) -> list[tuple[str, str, str]]:
    checks: list[tuple[str, Callable[[], tuple[str, str]]]] = [
        ("AZURE_AI_SEARCH", test_search_service),
        ("AZURE_BLOB_STORAGE", test_storage_service),
        ("AZURE_KEY_VAULT", test_key_vault_service),
    ]
    if include_openai:
        checks.append(("AZURE_OPENAI", test_openai_service))

    results: list[tuple[str, str, str]] = []
    for label, check in checks:
        try:
            status, detail = check()
        except ImportError as exc:
            status = "FAIL"
            detail = f"missing dependency: {exc}. Run 'pip install -e .' first."
        except Exception as exc:  # pragma: no cover - depends on external services
            status = "FAIL"
            detail = f"{type(exc).__name__}: {exc}"
        results.append((label, status, detail))

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Azure environment variables and optionally test live service connectivity."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate variable presence and format; skip live service calls.",
    )
    parser.add_argument(
        "--skip-openai",
        action="store_true",
        help="Skip the Azure OpenAI live call to avoid token usage.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    load_dotenv_file(ENV_FILE)

    if not ENV_FILE.exists():
        print(f"[FAIL] .env file not found at {ENV_FILE}")
        print("Create it first with: cp .env.example .env")
        return 1

    results, missing_required = validate_env()

    print(f"Checking environment file: {ENV_FILE}")
    print("")
    for name, status, detail in results:
        print_result(name, status, detail)

    print("")
    print("Notes:")
    print("- AZURE_SEARCH_API_KEY is optional when you use az login / DefaultAzureCredential.")
    print("- AZURE_OPENAI_API_KEY can be left empty if your az login identity has Azure OpenAI access.")
    print("- Live Azure OpenAI testing makes a tiny token-consuming request unless you use --skip-openai.")

    if missing_required:
        print("")
        print("Environment validation failed.")
        return 1

    if args.validate_only:
        print("")
        print("Environment validation passed.")
        return 0

    print("")
    print("Testing live Azure service connectivity...")
    live_results = run_live_service_checks(include_openai=not args.skip_openai)
    for name, status, detail in live_results:
        print_result(name, status, detail)

    failed_live_checks = [name for name, status, _ in live_results if status == "FAIL"]

    print("")
    if failed_live_checks:
        print("Environment validation passed, but one or more live service checks failed.")
        return 1

    print("Environment validation passed and live service checks completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
