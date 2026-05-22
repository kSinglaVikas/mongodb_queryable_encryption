import os
from copy import deepcopy
from datetime import datetime, timezone

from bson import json_util
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from pymongo import MongoClient

from qe_config import (
    COLLECTION_NAME,
    auto_encryption_options,
    get_database_name,
    get_org_ids,
    parse_iso_date,
)


app = Flask(__name__)
load_dotenv()

MONGODB_URI = os.environ["MONGODB_URI"]
ALLOWED_ORG_IDS = set(get_org_ids())

ALLOWED_EQUALITY_FIELDS = {
    "person.given_name",
    "person.email",
    "person.phone_number",
}

SUPPORTED_QUERY_TYPES = {
    "equality": sorted(ALLOWED_EQUALITY_FIELDS),
    "range": ["person.date_of_birth"],
    "prefixPreview": ["employment.identification.pan_no"],
    "suffixPreview": ["employment.identification.adhaar_no"],
}

RESULT_PROJECTION = {"_id": 0, "__safeContent__": 0}


class SharedClientCache:
    def __init__(self, uri: str):
        self.uri = uri
        self._client = None

    def get_collection(self):
        if self._client is None:
            self._client = MongoClient(
                self.uri,
                auto_encryption_opts=auto_encryption_options(),
            )
        db_name = get_database_name()
        return self._client[db_name][COLLECTION_NAME]


org_clients = SharedClientCache(MONGODB_URI)


def json_response(payload, status=200):
    return Response(json_util.dumps(payload), status=status, mimetype="application/json")


def normalize_employee_payload(payload: dict, org_id: int) -> dict:
    doc = deepcopy(payload)
    doc["organization_id"] = org_id

    person = doc.get("person", {})
    if "date_of_birth" in person and isinstance(person["date_of_birth"], str):
        person["date_of_birth"] = parse_iso_date(person["date_of_birth"])

    return doc


def ensure_org_allowed(org_id: int):
    if org_id not in ALLOWED_ORG_IDS:
        return jsonify({"error": f"Unsupported organization_id={org_id}"}), 400
    return None


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/query-types")
def query_types():
    return jsonify(
        {
            "collection": COLLECTION_NAME,
            "supported_query_types": SUPPORTED_QUERY_TYPES,
        }
    )


@app.post("/employees/<int:organization_id>")
def create_employee(organization_id: int):
    org_error = ensure_org_allowed(organization_id)
    if org_error:
        return org_error

    payload = request.get_json(force=True)
    document = normalize_employee_payload(payload, organization_id)
    collection = org_clients.get_collection()
    result = collection.insert_one(document)

    return jsonify({"inserted_id": str(result.inserted_id)})


@app.get("/employees/<int:organization_id>/search/equality")
def search_equality(organization_id: int):
    org_error = ensure_org_allowed(organization_id)
    if org_error:
        return org_error

    field = request.args.get("field", "").strip()
    value = request.args.get("value", "")
    if field not in ALLOWED_EQUALITY_FIELDS:
        return jsonify({"error": "Unsupported equality field"}), 400

    collection = org_clients.get_collection()
    docs = list(collection.find({"organization_id": organization_id, field: value}, RESULT_PROJECTION))
    return json_response(docs)


@app.get("/employees/<int:organization_id>/search/dob-range")
def search_dob_range(organization_id: int):
    org_error = ensure_org_allowed(organization_id)
    if org_error:
        return org_error

    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"error": "Provide start and end in YYYY-MM-DD"}), 400

    start_dt = parse_iso_date(start)
    end_dt = parse_iso_date(end)

    collection = org_clients.get_collection()
    docs = list(
        collection.find(
            {
                "organization_id": organization_id,
                "person.date_of_birth": {
                    "$gte": start_dt,
                    "$lte": end_dt,
                }
            },
            RESULT_PROJECTION,
        )
    )
    return json_response(docs)


@app.get("/employees/<int:organization_id>/search/pan-prefix")
def search_pan_prefix(organization_id: int):
    org_error = ensure_org_allowed(organization_id)
    if org_error:
        return org_error

    prefix = request.args.get("prefix", "")
    if not prefix:
        return jsonify({"error": "Provide prefix"}), 400

    collection = org_clients.get_collection()
    docs = list(
        collection.find(
            {
                "organization_id": organization_id,
                "$expr": {
                    "$encStrStartsWith": {
                        "input": "$employment.identification.pan_no",
                        "prefix": prefix,
                    }
                },
            },
            RESULT_PROJECTION,
        )
    )
    return json_response(docs)


@app.get("/employees/<int:organization_id>/search/adhaar-suffix")
def search_adhaar_suffix(organization_id: int):
    org_error = ensure_org_allowed(organization_id)
    if org_error:
        return org_error

    suffix = request.args.get("suffix", "")
    if not suffix:
        return jsonify({"error": "Provide suffix"}), 400

    collection = org_clients.get_collection()
    docs = list(
        collection.find(
            {
                "organization_id": organization_id,
                "$expr": {
                    "$encStrEndsWith": {
                        "input": "$employment.identification.adhaar_no",
                        "suffix": suffix,
                    }
                },
            },
            RESULT_PROJECTION,
        )
    )
    return json_response(docs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
