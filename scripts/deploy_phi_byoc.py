"""
MCPilot — SageMaker PHI Endpoint Deployment (BYOC)
Deploys custom spaCy container from ECR to SageMaker endpoint.

Usage:
  python scripts/deploy_phi_byoc.py          # deploy
  python scripts/deploy_phi_byoc.py delete   # delete endpoint
"""
import sys
import json
import boto3
import sagemaker

REGION        = "ap-south-1"
ACCOUNT_ID    = "574772738151"
ENDPOINT_NAME = "mcpilot-phi-detector"
INSTANCE_TYPE = "ml.t2.medium"
IMAGE_URI     = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/mcpilot-phi:latest"
ROLE_NAME     = "MCPilotSageMakerRole"

boto_session  = boto3.Session(region_name=REGION)
sm_client     = boto_session.client("sagemaker")
runtime       = boto_session.client("sagemaker-runtime")
iam           = boto_session.client("iam")


def get_role_arn() -> str:
    try:
        return iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        print(f"Creating IAM role: {ROLE_NAME}...")
        trust = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="MCPilot SageMaker execution role",
        )
        iam.attach_role_policy(
            RoleName=ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
        )
        iam.attach_role_policy(
            RoleName=ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess",
        )
        return role["Role"]["Arn"]


def deploy():
    role_arn = get_role_arn()
    print(f"Role ARN: {role_arn}")

    # Create SageMaker model
    model_name = f"{ENDPOINT_NAME}-model"
    print(f"Creating SageMaker model: {model_name}...")
    try:
        sm_client.delete_model(ModelName=model_name)
    except Exception:
        pass

    sm_client.create_model(
        ModelName=model_name,
        PrimaryContainer={"Image": IMAGE_URI},
        ExecutionRoleArn=role_arn,
    )

    # Create endpoint config
    config_name = f"{ENDPOINT_NAME}-config"
    print(f"Creating endpoint config: {config_name}...")
    try:
        sm_client.delete_endpoint_config(EndpointConfigName=config_name)
    except Exception:
        pass

    sm_client.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[{
            "VariantName":          "AllTraffic",
            "ModelName":            model_name,
            "InitialInstanceCount": 1,
            "InstanceType":         INSTANCE_TYPE,
        }],
    )

    # Create endpoint
    print(f"Deploying endpoint: {ENDPOINT_NAME} (5-8 minutes)...")
    try:
        sm_client.delete_endpoint(EndpointName=ENDPOINT_NAME)
        waiter = sm_client.get_waiter("endpoint_deleted")
        waiter.wait(EndpointName=ENDPOINT_NAME)
    except Exception:
        pass

    sm_client.create_endpoint(
        EndpointName=ENDPOINT_NAME,
        EndpointConfigName=config_name,
    )

    # Wait for endpoint to be in service
    print("Waiting for endpoint to be InService...")
    waiter = sm_client.get_waiter("endpoint_in_service")
    waiter.wait(
        EndpointName=ENDPOINT_NAME,
        WaiterConfig={"Delay": 30, "MaxAttempts": 20},
    )

    print(f"\nEndpoint deployed: {ENDPOINT_NAME} ✓")
    test_endpoint()

    print("\n" + "="*55)
    print("ADD TO YOUR .env:")
    print(f"AWS_SAGEMAKER_PHI_ENDPOINT={ENDPOINT_NAME}")
    print(f"AWS_REGION={REGION}")
    print("="*55)


def test_endpoint():
    print("\nTesting endpoint...")
    payload = json.dumps({
        "text": "Patient John Smith SSN 123-45-6789 born January 1 1980"
    })
    response = runtime.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=payload,
    )
    result = json.loads(response["Body"].read())
    print(f"PHI detected : {result['phi_detected']}")
    print(f"Entity count : {result['entity_count']}")
    print(f"Redacted text: {result['redacted_text']}")
    print("Endpoint test PASSED ✓")


def delete():
    print(f"Deleting endpoint: {ENDPOINT_NAME}...")
    try:
        sm_client.delete_endpoint(EndpointName=ENDPOINT_NAME)
        print("Endpoint deleted ✓")
    except Exception as e:
        print(f"Error: {e}")

    try:
        sm_client.delete_endpoint_config(
            EndpointConfigName=f"{ENDPOINT_NAME}-config"
        )
        print("Endpoint config deleted ✓")
    except Exception:
        pass

    try:
        sm_client.delete_model(
            ModelName=f"{ENDPOINT_NAME}-model"
        )
        print("Model deleted ✓")
    except Exception:
        pass

    print("No further charges.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        delete()
    else:
        print("="*55)
        print("MCPilot — SageMaker PHI Endpoint (BYOC)")
        print("="*55)
        print(f"Image    : {IMAGE_URI}")
        print(f"Endpoint : {ENDPOINT_NAME}")
        print(f"Instance : {INSTANCE_TYPE}")
        print("="*55 + "\n")
        deploy()