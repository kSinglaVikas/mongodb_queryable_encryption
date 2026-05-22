import argparse
import os
import random

from dotenv import load_dotenv
from faker import Faker
from pymongo import MongoClient

from qe_config import COLLECTION_NAME, auto_encryption_options, get_database_name, get_org_ids


JOB_TITLES = [
    "Software Engineer",
    "Senior Software Engineer",
    "QA Engineer",
    "Data Analyst",
    "Product Analyst",
    "DevOps Engineer",
    "Team Lead",
]

SKILL_SETS = [
    ["Python", "MongoDB", "Flask"],
    ["Java", "Spring", "SQL"],
    ["JavaScript", "Node.js", "MongoDB"],
    ["Go", "Kubernetes", "CI/CD"],
    ["React", "TypeScript", "REST"],
]


def parse_args():
    parser = argparse.ArgumentParser(description="Seed sample employee data into encrypted collection")
    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="Number of records to insert (recommended: 1000-5000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Bulk insert batch size",
    )
    parser.add_argument(
        "--start-employee-id",
        type=int,
        default=200000000,
        help="Starting employee_id for generated records",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for repeatable generation",
    )
    return parser.parse_args()


def make_pan(index: int) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    prefix = "".join(random.choice(letters) for _ in range(5))
    suffix_letter = letters[index % 26]
    return f"{prefix}{index % 10000:04d}{suffix_letter}"


def make_adhaar(index: int) -> str:
    # 12-digit mock identifier for testing only.
    return f"{800000000000 + index:012d}"


def build_employee(employee_id: int, org_id: int, fake: Faker) -> dict:
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = f"{first_name.lower()}.{last_name.lower()}.{employee_id}@{fake.free_email_domain()}"
    code = f"EMP{employee_id}"

    years = random.randint(1, 12)
    months = random.randint(0, 11)
    dob = fake.date_between(start_date="-56y", end_date="-21y").isoformat()
    joining_date = fake.date_between(start_date="-12y", end_date="today").isoformat()
    phone = f"+91{fake.random_number(digits=10, fix_len=True)}"

    return {
        "employee_id": employee_id,
        "employee_code": code,
        "organization_id": org_id,
        "person": {
            "given_name": first_name,
            "family_name": last_name,
            "date_of_birth": dob,
            "gender": random.choice(["Male", "Female"]),
            "marital_status": random.choice(["Single", "Married"]),
            "email": email,
            "phone_number": phone,
        },
        "profile": {
            "current_job_title": random.choice(JOB_TITLES),
            "key_skills": random.choice(SKILL_SETS),
            "total_experience": {"years": years, "months": months},
            "benefits": {
                "pf_applicable": random.choice([True, False]),
                "esi_applicable": random.choice([True, False]),
            },
        },
        "employment": {
            "employee_id": employee_id,
            "employee_code": code,
            "worksite_id": random.randint(10000, 99999),
            "designation_id": random.randint(50000, 99999),
            "joining_date": joining_date,
            "ctc": random.randint(450000, 2800000),
            "currency_code": "INR",
            "managers": {"l1_manager_id": max(100000001, employee_id - random.randint(1, 100))},
            "identification": {
                "pan_no": make_pan(employee_id),
                "adhaar_no": make_adhaar(employee_id),
            },
        },
    }


def parse_iso_dates_in_place(doc: dict):
    # Reuse app semantics by sending date strings and letting QE query fields parse consistently.
    # For direct inserts, we should convert date strings to BSON dates.
    from qe_config import parse_iso_date

    doc["person"]["date_of_birth"] = parse_iso_date(doc["person"]["date_of_birth"])


def seed_data(uri: str, total_count: int, batch_size: int, start_employee_id: int, seed: int):
    if total_count < 1:
        raise ValueError("count must be >= 1")
    if batch_size < 1:
        raise ValueError("batch-size must be >= 1")

    random.seed(seed)
    fake = Faker("en_IN")
    Faker.seed(seed)
    fake.seed_instance(seed)
    org_ids = get_org_ids()
    if not org_ids:
        raise ValueError("No ORG_IDS configured")

    client = MongoClient(uri, auto_encryption_opts=auto_encryption_options())
    db = client[get_database_name()]
    collection = db[COLLECTION_NAME]

    inserted = 0
    next_id = start_employee_id

    try:
        while inserted < total_count:
            docs = []
            chunk = min(batch_size, total_count - inserted)
            for _ in range(chunk):
                org_id = org_ids[(next_id - start_employee_id) % len(org_ids)]
                doc = build_employee(next_id, org_id, fake)
                parse_iso_dates_in_place(doc)
                docs.append(doc)
                next_id += 1

            result = collection.insert_many(docs, ordered=False)
            inserted += len(result.inserted_ids)
            print(f"Inserted {inserted}/{total_count}")

        print(
            f"Done. Inserted {inserted} docs into {get_database_name()}.{COLLECTION_NAME} "
            f"across organizations: {org_ids}"
        )
    finally:
        client.close()


def main():
    load_dotenv()
    uri = os.environ["MONGODB_URI"]
    args = parse_args()
    seed_data(uri, args.count, args.batch_size, args.start_employee_id, args.seed)


if __name__ == "__main__":
    main()