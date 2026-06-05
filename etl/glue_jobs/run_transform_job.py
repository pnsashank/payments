import boto3
import time
import os
from dotenv import load_dotenv

load_dotenv()

REGION = "ap-southeast-2"
BUCKET = "paylens-data-lake"
GLUE_ROLE_ARN = os.getenv("GLUE_ROLE_ARN")
JOB_NAME = "paylens-transform-job"
SCRIPT_PATH = "glue_transform_job.py"

glue = boto3.client("glue", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)

def upload_script():
    s3.upload_file(
        Filename=SCRIPT_PATH,
        Bucket=BUCKET,
        Key="scripts/glue_transform_job.py"
    )
    print(f"Script uploaded to s3://{BUCKET}/scripts/glue_transform_job.py")

def create_job():
    try:
        glue.get_job(JobName=JOB_NAME)
        print(f"Job '{JOB_NAME}' already exists, skipping creation.")
    except glue.exceptions.EntityNotFoundException:
        glue.create_job(
            Name=JOB_NAME,
            Role=GLUE_ROLE_ARN,
            Command={
                "Name": "glueetl",
                "ScriptLocation": f"s3://{BUCKET}/scripts/glue_transform_job.py",
                "PythonVersion":  "3"
            },
            DefaultArguments={
                "--S3_BUCKET": BUCKET,
                "--RAW_DB": "paylens_raw",
                "--CURATED_DB": "paylens_curated",
                "--job-language": "python",
                "--enable-glue-datacatalog":  ""
            },
            GlueVersion="4.0",
            NumberOfWorkers=2,
            WorkerType="G.1X"
        )
        print(f"Job '{JOB_NAME}' created successfully.")

def run_job():
    response = glue.start_job_run(
        JobName=JOB_NAME,
        Arguments={
            "--S3_BUCKET": BUCKET,
            "--RAW_DB": "paylens_raw",
            "--CURATED_DB": "paylens_curated"
        }
    )
    run_id = response["JobRunId"]
    print(f"Job run started: {run_id}")
    return run_id

def wait_for_job(run_id):
    print("Waiting for job to complete...")
    while True:
        response = glue.get_job_run(JobName=JOB_NAME, RunId=run_id)
        status = response["JobRun"]["JobRunState"]
        print(f"Status: {status}")

        if status in ("SUCCEEDED", "FAILED", "ERROR", "STOPPED"):
            if status == "SUCCEEDED":
                print("Transform job completed successfully.")
            else:
                error = response["JobRun"].get("ErrorMessage", "No error message")
                print(f"Job failed: {error}")
            break

        time.sleep(30)

if __name__ == "__main__":
    upload_script()
    create_job()
    run_id = run_job()
    wait_for_job(run_id)