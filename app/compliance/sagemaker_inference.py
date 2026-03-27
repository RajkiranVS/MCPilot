"""
MCPilot — SageMaker PHI Inference Script
Runs inside the SageMaker container.
Loaded by SageMaker as the model server entry point.

Endpoints:
  model_fn     → loads spaCy model at container startup
  input_fn     → deserialises incoming JSON request
  predict_fn   → runs PHI detection
  output_fn    → serialises response to JSON
"""
import os
import json
import spacy
from spacy.language import Language

_nlp = None


def model_fn(model_dir: str):
    """
    Load spaCy model from the model directory.
    Called once at container startup.
    """
    global _nlp

    # Register DOB context detector component
    if not Language.has_factory("dob_context_detector"):
        @Language.component("dob_context_detector")
        def dob_context_detector(doc):
            DOB_KEYWORDS = {
                "born", "dob", "birthdate", "birth date",
                "date of birth", "birthday"
            }
            new_ents = []
            for ent in doc.ents:
                if ent.label_ == "DATE":
                    context_start = max(0, ent.start - 5)
                    context_tokens = [
                        t.text.lower()
                        for t in doc[context_start:ent.start]
                    ]
                    context_text = " ".join(context_tokens)
                    if any(kw in context_text for kw in DOB_KEYWORDS):
                        new_ent = doc.char_span(
                            ent.start_char, ent.end_char, label="DOB"
                        )
                        new_ents.append(new_ent if new_ent else ent)
                    else:
                        new_ents.append(ent)
                else:
                    new_ents.append(ent)
            doc.ents = new_ents
            return doc

    model_path = os.path.join(model_dir, "phi_model")
    _nlp = spacy.load(model_path)
    return _nlp


def input_fn(request_body: str, content_type: str = "application/json"):
    """Deserialise incoming request."""
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type: {content_type}")
    return json.loads(request_body)


def predict_fn(input_data: dict, model):
    """
    Run PHI detection on input text.
    Input:  {"text": "Patient John Smith SSN 123-45-6789"}
    Output: {"entities": [...], "phi_detected": true, "redacted_text": "..."}
    """
    text = input_data.get("text", "")

    if not text or not text.strip():
        return {
            "entities":     [],
            "phi_detected": False,
            "redacted_text": text,
            "entity_count": 0,
            "redacted_count": 0,
        }

    REDACT_LABELS = {"PERSON", "SSN", "MRN", "DOB", "PHONE", "EMAIL"}

    doc = model(text)
    entities = []
    for ent in doc.ents:
        entities.append({
            "text":   ent.text,
            "label":  ent.label_,
            "start":  ent.start_char,
            "end":    ent.end_char,
            "redact": ent.label_ in REDACT_LABELS,
        })

    # Redact from end to start to preserve positions
    redactable = [e for e in entities if e["redact"]]
    sorted_ents = sorted(redactable, key=lambda e: e["start"], reverse=True)
    redacted = text
    for ent in sorted_ents:
        redacted = redacted[:ent["start"]] + f"[{ent['label']}]" + redacted[ent["end"]:]

    return {
        "entities":      entities,
        "phi_detected":  len(redactable) > 0,
        "redacted_text": redacted,
        "entity_count":  len(entities),
        "redacted_count": len(redactable),
    }


def output_fn(prediction: dict, accept: str = "application/json") -> str:
    """Serialise response."""
    return json.dumps(prediction)