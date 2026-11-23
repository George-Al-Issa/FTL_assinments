"""Exercise the running prototype with a fresh synthetic record."""
import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def call(path, payload=None):
    base_url = os.getenv("CROSAFE_TEST_URL", "http://127.0.0.1:8000").rstrip("/")
    data = json.dumps(payload).encode() if payload is not None else None
    user = os.getenv("CROSAFE_ADMIN_USER", "admin")
    password = os.environ["CROSAFE_ADMIN_PASSWORD"]
    credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = Request(base_url + path, data, {
        "Content-Type": "application/json", "Authorization": f"Basic {credentials}",
    })
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


def main():
    field = json.loads(Path(__file__).with_name("field.json").read_text())
    field["id"] = str(uuid4())
    field_path = "/v1/fields/" + field["id"]

    assert call("/health") == (200, {"status": "ok", "weather_source": "synthetic"})
    assert call("/v1/fields/sync", field) == (200, field)
    assert call("/v1/fields/sync", field) == (200, field)
    assert call("/v1/fields/sync", {**field, "area_ha": 3})[0] == 409
    assert call(field_path) == (200, field)

    status, assessment = call(field_path + "/assessment")
    assert status == 200, assessment
    assert assessment["field_id"] == field["id"]
    assert [result["status"] for result in assessment["results"]] == [
        "demo", "unavailable", "unavailable", "unavailable",
    ]
    print("CroSafe fixture smoke check passed.")


if __name__ == "__main__":
    main()
