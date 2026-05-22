import argparse
import os

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

from qe_config import (
    COLLECTION_NAME,
    auto_encryption_options,
    build_client_encryption,
    encrypted_fields_map,
    get_database_name,
    get_key_vault_namespace,
)


def ensure_key_vault_index(client, key_vault_namespace: str):
    key_vault_db, key_vault_coll = key_vault_namespace.split(".", 1)
    client[key_vault_db][key_vault_coll].create_index(
        [("keyAltNames", ASCENDING)],
        name="keyAltNames_1",
        unique=True,
        partialFilterExpression={"keyAltNames": {"$exists": True}},
    )


def setup_collection(uri: str, drop_existing: bool):
    key_vault_namespace = get_key_vault_namespace()
    db_name = get_database_name()
    encrypted_client = MongoClient(uri, auto_encryption_opts=auto_encryption_options())
    regular_client = MongoClient(uri)

    try:
        ensure_key_vault_index(regular_client, key_vault_namespace)

        if drop_existing:
            regular_client[db_name][COLLECTION_NAME].drop()

        client_encryption = build_client_encryption(encrypted_client)
        try:
            client_encryption.create_encrypted_collection(
                encrypted_client[db_name],
                COLLECTION_NAME,
                encrypted_fields_map(),
                "local",
                {},
            )
            regular_client[db_name][COLLECTION_NAME].create_index(
                [("organization_id", ASCENDING)],
                name="organization_id_1",
            )
            print(f"Created encrypted collection {db_name}.{COLLECTION_NAME}")
        except Exception as exc:
            message = str(exc)
            if "NamespaceExists" in message or "already exists" in message:
                regular_client[db_name][COLLECTION_NAME].create_index(
                    [("organization_id", ASCENDING)],
                    name="organization_id_1",
                )
                print(f"Encrypted collection already exists: {db_name}.{COLLECTION_NAME}")
            else:
                raise

    finally:
        encrypted_client.close()
        regular_client.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Create Queryable Encryption collections for multiple organizations")
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing employee collections before setup",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    uri = os.environ["MONGODB_URI"]

    args = parse_args()
    setup_collection(uri, args.drop_existing)


if __name__ == "__main__":
    main()
