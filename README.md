@'
# DocuMind Secure

A secure, containerized document intelligence platform
using FastAPI, Amazon Cognito, Amazon S3, and Amazon Bedrock.

## Local development

1. Install Python 3.12 and Docker Desktop.
2. Copy .env.example to .env.
3. Start the API using Docker Compose:

   docker compose up --build

4. Check the health endpoint:

   http://localhost:8000/health

Protected endpoints require a valid Amazon Cognito access token.
Document storage and RAG processing will be implemented in later phases.
'@ | Set-Content README.md