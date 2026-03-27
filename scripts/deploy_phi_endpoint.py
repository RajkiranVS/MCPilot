"""
MCPilot — SageMaker PHI Endpoint Deployment Script
Packages spaCy model and deploys to SageMaker real-time endpoint.

Usage:
  python scripts/deploy_phi_endpoint.py

What it does:
  1. Saves spaCy en_core_web_sm model to local directory
  2. Packages model + inference script into model.tar.gz
  3. Uploads to S3
  4. Creates SageMaker model + endpoint config + endpoint
  5. Prints endpoint name to add to .env

Cost: ~$0.056/hour on ml.t2.medium (free tier: 250h for 2 months)
IMPORTANT: Run delete_endpoint() when not testing to avoid charges.
"""
import os
import sys
import tarfile
import shutil
import boto3
import sagemaker
from sagemaker.sklearn.estimator import SKLearn
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
REGION          = "ap-south-1"
ENDPOINT_NAME   = "mcpilot-phi-detector"
INSTANCE_TYPE   = "ml.t2.medium"
MODEL_DIR       = Path("scripts/phi_model_package")
INFERENCE_SCRIPT = "app/compliance/sagemaker_inference.py"

# ── AWS clients ───────────────────────────────────────────────────────────────
boto_session    = boto3.Session(region_name=REGION)
sm_session      = sagemaker.Session(boto_session=boto_session)
s3_client       = boto_session.client("s3")
sm_client       = boto_session.client("sagemaker")
BUCKET          = sm_session.default_bucket()
account_id      = boto_session.client("sts").get_caller_identity()["Account"]


def save_spacy_model():
    """Save en_core_web_sm to local directory for packaging."""
    print("Saving spaCy model locally...")
    import spacy
    nlp = spacy.load("en_core_web_sm")
    model_path = MODEL_DIR / "phi_model"
    model_path.mkdir(parents=True, exist_ok=True)
    nlp.to_disk(str(model_path))
    print(f"Model saved to {model_path}")


def package_model() -> Path:
    """Package model + inference script into model.tar.gz."""
    print("Packaging model artifacts...")

    # Copy inference script into package
    shutil.copy(INFERENCE_SCRIPT, str(MODEL_DIR / "inference.py"))

    # Create tar.gz
    tar_path = MODEL_DIR / "model.tar.gz"
    with tarfile.open(str(tar_path), "w:gz") as tar:
        tar.add(str(MODEL_DIR / "phi_model"), arcname="phi_model")
        tar.add(str(MODEL_DIR / "inference.py"), arcname="inference.py")

    print(f"Package created: {tar_path} ({tar_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return tar_path


def upload_to_s3(tar_path: Path) -> str:
    """Upload model package to S3."""
    s3_key = f"mcpilot/phi-model/model.tar.gz"
    print(f"Uploading to s3://{BUCKET}/{s3_key}...")
    s3_client.upload_file(str(tar_path), BUCKET, s3_key)
    s3_uri = f"s3://{BUCKET}/{s3_key}"
    print(f"Uploaded: {s3_uri}")
    return s3_uri


def get_or_create_execution_role() -> str:
    """Get SageMaker execution role ARN."""
    iam = boto_session.client("iam")
    role_name = "MCPilotSageMakerRole"

    try:
        role = iam.get_role(RoleName=role_name)
        arn = role["Role"]["Arn"]
        print(f"Using existing role: {arn}")
        return arn
    except iam.exceptions.NoSuchEntityException:
        pass

    print(f"Creating IAM role: {role_name}...")
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "sagemaker.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=str(trust_policy).replace("'", '"'),
        Description="MCPilot SageMaker execution role",
    )
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
    )
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
    )
    arn = role["Role"]["Arn"]
    print(f"Role created: {arn}")
    return arn


def deploy_endpoint(s3_uri: str, role_arn: str) -> str:
    """Deploy spaCy model to SageMaker endpoint using SKLearnModel."""
    from sagemaker.sklearn.model import SKLearnModel
    import shutil

    print(f"\nDeploying endpoint: {ENDPOINT_NAME}")
    print(f"Instance type: {INSTANCE_TYPE}")
    print("This takes 5-8 minutes...\n")

    # Copy inference script into model package directory
    # SKLearnModel needs entry_point to exist in source_dir
    inference_dest = MODEL_DIR / "inference.py"
    if not inference_dest.exists():
        shutil.copy(INFERENCE_SCRIPT, str(inference_dest))
        print(f"Inference script copied to {inference_dest}")

    sklearn_model = SKLearnModel(
        model_data=s3_uri,
        role=role_arn,
        entry_point="inference.py",
        source_dir=str(MODEL_DIR),
        framework_version="1.2-1",
        py_version="py3",
        sagemaker_session=sm_session,
    )

    predictor = sklearn_model.deploy(
        initial_instance_count=1,
        instance_type=INSTANCE_TYPE,
        endpoint_name=ENDPOINT_NAME,
        wait=True,
    )

    print(f"\nEndpoint deployed: {predictor.endpoint_name}")
    return predictor.endpoint_name


def test_endpoint(endpoint_name: str):
    """Quick smoke test of the deployed endpoint."""
    print("\nTesting endpoint...")
    runtime = boto_session.client("sagemaker-runtime")
    import json

    payload = json.dumps({"text": "Patient John Smith SSN 123-45-6789 DOB January 1 1980"})
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=payload,
    )
    result = json.loads(response["Body"].read())
    print(f"PHI detected: {result['phi_detected']}")
    print(f"Entities found: {result['entity_count']}")
    print(f"Redacted text: {result['redacted_text']}")
    print("\nEndpoint test PASSED ✓")


def delete_endpoint(endpoint_name: str = ENDPOINT_NAME):
    """
    Delete the endpoint to stop charges.
    Run this when done testing.
    """
    print(f"Deleting endpoint: {endpoint_name}...")
    sm_client.delete_endpoint(EndpointName=endpoint_name)
    print("Endpoint deleted. No further charges.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        delete_endpoint()
        sys.exit(0)

    print("="*55)
    print("MCPilot — SageMaker PHI Endpoint Deployment")
    print("="*55)
    print(f"Region  : {REGION}")
    print(f"Bucket  : {BUCKET}")
    print(f"Endpoint: {ENDPOINT_NAME}")
    print("="*55 + "\n")

    save_spacy_model()
    tar_path = package_model()
    s3_uri   = upload_to_s3(tar_path)
    role_arn = get_or_create_execution_role()
    endpoint = deploy_endpoint(s3_uri, role_arn)
    test_endpoint(endpoint)

    print("\n" + "="*55)
    print("ADD TO YOUR .env:")
    print(f"AWS_SAGEMAKER_PHI_ENDPOINT={endpoint}")
    print(f"AWS_REGION={REGION}")
    print("="*55)

    # Cleanup local package AFTER deployment and test
    shutil.rmtree(str(MODEL_DIR), ignore_errors=True)
    print("\nLocal package cleaned up.")