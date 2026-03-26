import json
from pathlib import Path

from mem0 import MemoryClient


def main():
    settings_path = Path(__file__).with_name("settings.json")
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    tokens = settings.get("service_tokens") or {}

    api_key = str(tokens.get("mem0_api_key") or "").strip()
    user_id = str(tokens.get("mem0_user_id") or "sir").strip() or "sir"
    app_id = str(tokens.get("mem0_app_id") or "edith").strip() or "edith"
    org_id = str(tokens.get("mem0_org_id") or "").strip()
    project_id = str(tokens.get("mem0_project_id") or "").strip()

    if not api_key:
        raise SystemExit("mem0_api_key is not configured in backend/settings.json")

    client_kwargs = {"api_key": api_key}
    if org_id and project_id:
        client_kwargs["org_id"] = org_id
        client_kwargs["project_id"] = project_id

    client = MemoryClient(**client_kwargs)
    result = client.search(
        "edith",
        filters={
            "AND": [
                {"user_id": user_id},
                {"app_id": app_id},
            ]
        },
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
