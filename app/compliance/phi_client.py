"""
MCPilot — PHI Client
Abstraction layer over PHI detection.

In development/test:  calls local spaCy pipeline directly
In production:        calls AWS SageMaker endpoint

Controlled by ENVIRONMENT setting:
  development → local spaCy
  test        → local spaCy
  production  → SageMaker endpoint
"""
import json
import boto3
from app.compliance.phi_detector import detect, scan_dict, scan_list, DetectionResult
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PHIClient:
    """
    Unified interface for PHI detection regardless of backend.
    Swap between local and SageMaker transparently.
    """

    def __init__(self):
        self._use_sagemaker = (
            settings.environment == "production"
            and bool(settings.aws_sagemaker_phi_endpoint)
        )
        self._runtime = None

        if self._use_sagemaker:
            self._runtime = boto3.client(
                "sagemaker-runtime",
                region_name=settings.aws_region,
            )
            logger.info(
                f"PHI client using SageMaker endpoint: "
                f"{settings.aws_sagemaker_phi_endpoint}"
            )
        else:
            logger.info("PHI client using local spaCy pipeline")

    def detect(self, text: str) -> DetectionResult:
        """Detect and redact PHI in a text string."""
        if self._use_sagemaker:
            return self._detect_sagemaker(text)
        return detect(text)

    def scan_dict(self, data: dict) -> tuple[dict, bool]:
        """Scan a dictionary for PHI in string values."""
        if self._use_sagemaker:
            redacted = {}
            any_phi = False
            for key, value in data.items():
                if isinstance(value, str):
                    result = self._detect_sagemaker(value)
                    redacted[key] = result.redacted_text
                    if result.phi_detected:
                        any_phi = True
                elif isinstance(value, dict):
                    redacted[key], child_phi = self.scan_dict(value)
                    any_phi = any_phi or child_phi
                else:
                    redacted[key] = value
            return redacted, any_phi
        return scan_dict(data)

    def _detect_sagemaker(self, text: str) -> DetectionResult:
        """Call SageMaker endpoint for PHI detection."""
        payload = json.dumps({"text": text})
        response = self._runtime.invoke_endpoint(
            EndpointName=settings.aws_sagemaker_phi_endpoint,
            ContentType="application/json",
            Body=payload,
        )
        result = json.loads(response["Body"].read())

        # Convert SageMaker response back to DetectionResult
        from app.compliance.phi_detector import PHIEntity
        from app.compliance.patterns import PHI_LABELS, REDACT_LABELS

        entities = [
            PHIEntity(
                text=e["text"],
                label=e["label"],
                start=e["start"],
                end=e["end"],
                redact=e["redact"],
                label_name=PHI_LABELS.get(e["label"], e["label"]),
            )
            for e in result.get("entities", [])
        ]

        return DetectionResult(
            original_text=text,
            entities=entities,
            phi_detected=result["phi_detected"],
            redacted_text=result["redacted_text"],
            entity_count=result["entity_count"],
            redacted_count=result["redacted_count"],
        )


# Module-level singleton
phi_client = PHIClient()