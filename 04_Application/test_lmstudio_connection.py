from pathlib import Path

from job_extractor import extract_job_listing


PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_FILE = (
    PROJECT_ROOT
    / "03_Test_Data"
    / "JOB-TEST-003_DATA_ANALYST_raw.txt"
)


job_text = TEST_FILE.read_text(
    encoding="utf-8"
).strip()


result = extract_job_listing(
    job_text=job_text,
    source_reference="JOB-TEST-003",
)


print("Extraction successful")
print()
print("Input file:", TEST_FILE)
print()

print("Company:", result.fields.company.value)
print("Role:", result.fields.role.value)
print("Location:", result.fields.location.value)
print("Employment type:", result.fields.employment_type.value)
print("Salary:", result.fields.salary.value)
print("Posting date:", result.fields.posting_date.value)

print()
print("Required requirements:")
for item in result.fields.required_requirements.value:
    print("-", item)

print()
print("Preferred requirements:")
for item in result.fields.preferred_requirements.value:
    print("-", item)

print()
print("Education requirements:")
for item in result.fields.education_requirements.value:
    print("-", item)