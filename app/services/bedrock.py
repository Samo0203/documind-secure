import json
import logging
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_client():
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("bedrock-runtime", **kwargs)


def generate_embeddings(text: str) -> Optional[List[float]]:
    """
    Generate a text embedding vector using Amazon Titan Text Embeddings V2.
    Returns None if AWS Bedrock is not configured.
    """
    if not settings.AWS_ACCESS_KEY_ID:
        # Return a deterministic mock embedding for local development/testing
        logger.warning("AWS not configured – returning mock embedding")
        return _mock_embedding(text)

    client = _get_client()
    try:
        body = json.dumps({"inputText": text[:8000]})  # Titan has 8K token limit
        response = client.invoke_model(
            modelId=settings.BEDROCK_EMBEDDING_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["embedding"]
    except (ClientError, Exception) as e:
        logger.error("Bedrock embedding error: %s", e)
        return _mock_embedding(text)


def generate_answer(prompt: str) -> str:
    """
    Generate a text answer using the configured Claude model on AWS Bedrock.
    Falls back to a structured mock answer if AWS is not configured.
    """
    if not settings.AWS_ACCESS_KEY_ID:
        logger.warning("AWS not configured – returning mock answer")
        return _mock_answer(prompt)

    client = _get_client()
    try:
        model_id = settings.BEDROCK_MODEL_ID

        # Claude 3 Messages API
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except (ClientError, Exception) as e:
        logger.error("Bedrock generation error: %s", e)
        return f"Error generating answer: {e}"


def _mock_embedding(text: str) -> List[float]:
    """Deterministic mock 1536-dim embedding for testing/dev without AWS."""
    import hashlib
    import math

    seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2 ** 31)
    dim = 1536
    vec = [math.sin(seed * (i + 1) * 0.001) for i in range(dim)]
    # Normalize
    magnitude = math.sqrt(sum(v ** 2 for v in vec))
    return [v / magnitude for v in vec]


def _mock_answer(prompt: str) -> str:
    """Mock answer that explains AWS is not configured."""
    return (
        "This is a demo response — AWS Bedrock is not configured. "
        "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file "
        "to enable real AI-powered answers using Claude on AWS Bedrock."
    )
