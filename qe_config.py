import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from bson.codec_options import CodecOptions
from bson.binary import STANDARD
from pymongo.encryption import ClientEncryption
from pymongo.encryption_options import AutoEncryptionOpts


COLLECTION_NAME = "employees"


def get_org_ids() -> List[int]:
    raw = os.getenv("ORG_IDS", "19,20,21,22,23")
    org_ids = []
    for value in raw.split(","):
        value = value.strip()
        if value:
            org_ids.append(int(value))
    return org_ids


def get_master_key_file() -> Path:
    configured = os.getenv("MASTER_KEY_FILE")
    if configured:
        path = Path(configured).resolve()
    else:
        legacy_dir = os.getenv("ORG_MASTER_KEY_DIR", "./keys")
        path = (Path(legacy_dir) / "customer-master-key.bin").resolve()

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_key_vault_namespace() -> str:
    return os.getenv("QE_KEY_VAULT_NAMESPACE", "qe_keyvault.__keyVault")


def get_database_name() -> str:
    return os.getenv("QE_DATABASE_NAME", "hr_qe")


def load_or_create_master_key() -> bytes:
    key_file = get_master_key_file()
    if not key_file.exists():
        key_file.write_bytes(os.urandom(96))

    key_material = key_file.read_bytes()
    if len(key_material) != 96:
        raise ValueError(f"Master key file must be 96 bytes: {key_file}")
    return key_material


def kms_providers() -> Dict[str, Dict[str, bytes]]:
    return {"local": {"key": load_or_create_master_key()}}


def auto_encryption_options() -> AutoEncryptionOpts:
    shared_lib_path = os.environ["SHARED_LIB_PATH"]
    return AutoEncryptionOpts(
        kms_providers(),
        get_key_vault_namespace(),
        crypt_shared_lib_path=shared_lib_path,
    )


def build_client_encryption(mongo_client) -> ClientEncryption:
    return ClientEncryption(
        kms_providers=kms_providers(),
        key_vault_namespace=get_key_vault_namespace(),
        key_vault_client=mongo_client,
        codec_options=CodecOptions(uuid_representation=STANDARD),
    )


def encrypted_fields_map() -> Dict[str, List[Dict[str, object]]]:
    # Prefix and suffix query types are preview features in MongoDB 8.2.
    return {
        "fields": [
            {
                "path": "person.given_name",
                "bsonType": "string",
                "queries": [{"queryType": "equality"}],
            },
            {
                "path": "person.email",
                "bsonType": "string",
                "queries": [{"queryType": "equality"}],
            },
            {
                "path": "person.phone_number",
                "bsonType": "string",
                "queries": [{"queryType": "equality"}],
            },
            {
                "path": "person.date_of_birth",
                "bsonType": "date",
                "queries": [
                    {
                        "queryType": "range",
                        "min": datetime(1900, 1, 1, tzinfo=timezone.utc),
                        "max": datetime(2100, 1, 1, tzinfo=timezone.utc),
                        "sparsity": 1,
                        "trimFactor": 4,
                    }
                ],
            },
            {
                "path": "employment.identification.pan_no",
                "bsonType": "string",
                "queries": [
                    {
                        "queryType": "prefixPreview",
                        "strMinQueryLength": 2,
                        "strMaxQueryLength": 10,
                        "caseSensitive": True,
                        "diacriticSensitive": True,
                    }
                ],
            },
            {
                "path": "employment.identification.adhaar_no",
                "bsonType": "string",
                "queries": [
                    {
                        "queryType": "suffixPreview",
                        "strMinQueryLength": 2,
                        "strMaxQueryLength": 12,
                        "caseSensitive": True,
                        "diacriticSensitive": True,
                    }
                ],
            },
        ]
    }


def parse_iso_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
