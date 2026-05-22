# Flask Queryable Encryption App

This folder contains a separate Flask application that uses MongoDB Queryable Encryption for the employee data model in one shared encrypted collection.

## Features

- Queryable encrypted fields:
  - Equality: `person.given_name`, `person.email`, `person.phone_number`
  - Range: `person.date_of_birth`
  - Prefix (preview): `employment.identification.pan_no`
  - Suffix (preview): `employment.identification.adhaar_no`
- Five organizations (configurable through `ORG_IDS`) stored in one shared encrypted collection.
- Setup script to create encrypted collections.

## Prerequisites

- MongoDB deployment with Queryable Encryption support
- Automatic Encryption Shared Library (`mongo_crypt_v1`)
- Python 3.10+

## Configuration

1. Copy `.env.example` to `.env` and set values.
2. Ensure `SHARED_LIB_PATH` points to your `mongo_crypt` shared library.

## Install

```bash
pip install -r requirements.txt
```

## Setup Encrypted Collections

```bash
python setup_qe.py --drop-existing
```

The script creates one encrypted collection and the application scopes documents by `organization_id`.

## Load Sample Data (1k-5k)

```bash
# Load 1000 records
python seed_data.py --count 1000

# Load 5000 records
python seed_data.py --count 5000
```

Data is generated using Faker (`en_IN`) to produce realistic synthetic employee records.

Optional flags:

- `--batch-size 500` to tune insert chunk size.
- `--start-employee-id 200000000` to shift generated id range.
- `--seed 42` for repeatable random data.

## Run Flask App

```bash
python app.py
```

Server runs on port `5001`.

## API Examples

### Show supported query types

```bash
curl "http://localhost:5001/query-types"
```

### Insert employee

```bash
curl -X POST "http://localhost:5001/employees/19" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": 100000001,
    "employee_code": "EMP100000001",
    "organization_id": 19,
    "person": {
      "given_name": "John",
      "family_name": "Doe",
      "date_of_birth": "1990-05-15",
      "gender": "Male",
      "marital_status": "Single",
      "email": "john.doe@demo.com",
      "phone_number": "+919876543210"
    },
    "profile": {
      "current_job_title": "Software Engineer",
      "key_skills": ["Python", "MongoDB", "JavaScript"],
      "total_experience": {"years": 3, "months": 6},
      "benefits": {
        "pf_applicable": true,
        "esi_applicable": true
      }
    },
    "employment": {
      "employee_id": 100000001,
      "employee_code": "EMP100000001",
      "worksite_id": 17557,
      "designation_id": 61038,
      "joining_date": "2020-01-15",
      "ctc": 800000,
      "currency_code": "INR",
      "managers": {"l1_manager_id": 100000050},
      "identification": {
        "pan_no": "ABCDE1234F",
        "adhaar_no": "123456789012"
      }
    }
  }'
```

### Equality query

```bash
curl "http://localhost:5001/employees/19/search/equality?field=person.email&value=john.doe@demo.com"
```

### DOB range query

```bash
curl "http://localhost:5001/employees/19/search/dob-range?start=1989-01-01&end=1992-12-31"
```

### PAN prefix query

```bash
curl "http://localhost:5001/employees/19/search/pan-prefix?prefix=ABCDE"
```

### Aadhaar suffix query

```bash
curl "http://localhost:5001/employees/19/search/adhaar-suffix?suffix=9012"
```

## Notes

- Prefix/suffix encrypted string queries are preview features in MongoDB 8.2.
- The app stores all organizations in one encrypted collection and uses `organization_id` for application-level isolation.
