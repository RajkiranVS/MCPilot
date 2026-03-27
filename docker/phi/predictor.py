"""
MCPilot — SageMaker PHI Inference Server
Flask app served by gunicorn inside the Docker container.
SageMaker calls /ping for health check and /invocations for inference.
"""
import json
import logging
import flask
import spacy
from spacy.language import Language

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = flask.Flask(__name__)

# ── Load model at startup ─────────────────────────────────────────────────────
_nlp = None

REDACT_LABELS = {"PERSON", "SSN", "MRN", "DOB", "PHONE", "EMAIL"}

REGEX_PATTERNS = [
    # SSN: 123-45-6789
    {"label": "SSN", "pattern": [
        {"TEXT": {"REGEX": r"^\d{3}$"}},
        {"TEXT": "-"},
        {"TEXT": {"REGEX": r"^\d{2}$"}},
        {"TEXT": "-"},
        {"TEXT": {"REGEX": r"^\d{4}$"}},
    ]},
    # SSN: 123456789
    {"label": "SSN", "pattern": [
        {"TEXT": {"REGEX": r"^\d{9}$"}},
    ]},
    # MRN
    {"label": "MRN", "pattern": [
        {"TEXT": {"REGEX": r"^MRN[-:]?\d{6,10}$"}},
    ]},
    # Phone: 555-123-4567
    {"label": "PHONE", "pattern": [
        {"TEXT": {"REGEX": r"^\d{3}$"}},
        {"TEXT": "-"},
        {"TEXT": {"REGEX": r"^\d{3}$"}},
        {"TEXT": "-"},
        {"TEXT": {"REGEX": r"^\d{4}$"}},
    ]},
    # Email
    {"label": "EMAIL", "pattern": [
        {"TEXT": {"REGEX": r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"}},
    ]},
]

DOB_KEYWORDS = {"born", "dob", "birthdate", "birth date", "date of birth", "birthday"}


def load_model():
    global _nlp
    if _nlp is not None:
        return _nlp

    logger.info("Loading spaCy PHI model...")

    if not Language.has_factory("dob_context_detector"):
        @Language.component("dob_context_detector")
        def dob_context_detector(doc):
            new_ents = []
            for ent in doc.ents:
                if ent.label_ == "DATE":
                    ctx_start = max(0, ent.start - 5)
                    ctx_text = " ".join(
                        t.text.lower() for t in doc[ctx_start:ent.start]
                    )
                    if any(kw in ctx_text for kw in DOB_KEYWORDS):
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

    nlp = spacy.load("en_core_web_sm")
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    ruler.add_patterns(REGEX_PATTERNS)
    nlp.add_pipe("dob_context_detector", after="ner")

    _nlp = nlp
    logger.info("PHI model loaded ✓")
    return _nlp


def detect_phi(text: str) -> dict:
    if not text or not text.strip():
        return {
            "entities": [], "phi_detected": False,
            "redacted_text": text, "entity_count": 0, "redacted_count": 0,
        }

    nlp = load_model()
    doc = nlp(text)

    entities = []
    for ent in doc.ents:
        entities.append({
            "text":   ent.text,
            "label":  ent.label_,
            "start":  ent.start_char,
            "end":    ent.end_char,
            "redact": ent.label_ in REDACT_LABELS,
        })

    redactable = sorted(
        [e for e in entities if e["redact"]],
        key=lambda e: e["start"],
        reverse=True,
    )
    redacted = text
    for ent in redactable:
        redacted = redacted[:ent["start"]] + f"[{ent['label']}]" + redacted[ent["end"]:]

    return {
        "entities":      entities,
        "phi_detected":  len(redactable) > 0,
        "redacted_text": redacted,
        "entity_count":  len(entities),
        "redacted_count": len(redactable),
    }


# ── SageMaker endpoints ───────────────────────────────────────────────────────
@app.route("/ping", methods=["GET"])
def ping():
    """SageMaker health check — load model here to warm up."""
    load_model()
    return flask.Response(
        response=json.dumps({"status": "healthy"}),
        status=200,
        mimetype="application/json",
    )


@app.route("/invocations", methods=["POST"])
def invocations():
    """SageMaker inference endpoint."""
    if flask.request.content_type != "application/json":
        return flask.Response(
            response=json.dumps({"error": "Content type must be application/json"}),
            status=415,
            mimetype="application/json",
        )

    data = flask.request.get_json()
    text = data.get("text", "")
    result = detect_phi(text)

    return flask.Response(
        response=json.dumps(result),
        status=200,
        mimetype="application/json",
    )


if __name__ == "__main__":
    load_model()
    app.run(host="0.0.0.0", port=8080)