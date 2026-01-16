#!/bin/bash
set -e

# Configuration (Populated by the pipeline or defaults)
TAG=${1:-latest}
REGION=${2:-us-central1}
PROJECT_ID=${3}
REPO_NAME=${4}
IMAGE_NAME=${5:-expense-manager}

# Construct the full image URL
FULL_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${TAG}"

echo "🚀 Deploying Image: ${FULL_IMAGE}"

# Ensure we are authenticated to pull (uses VM's service account)
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Fetch Secrets from Google Secret Manager
echo "🔐 Fetching secrets..."
OPENAI_API_KEY=$(gcloud secrets versions access latest --secret="OPENAI_API_KEY" --quiet)
NEON_CONN_STR=$(gcloud secrets versions access latest --secret="NEON_CONN_STR" --quiet)

# Pull the new image
docker pull "${FULL_IMAGE}"

# Stop and remove the old container if it exists
if [ "$(docker ps -aq -f name=${IMAGE_NAME})" ]; then
    echo "🛑 Stopping existing container..."
    docker stop ${IMAGE_NAME} || true
    docker rm ${IMAGE_NAME} || true
fi

# Run the new container
echo "▶️ Starting new container..."
docker run -d \
  --name ${IMAGE_NAME} \
  -p 8501:8501 \
  --restart unless-stopped \
  -e OPENAI_API_KEY=${OPENAI_API_KEY} \
  -e NEON_CONN_STR=${NEON_CONN_STR} \
  "${FULL_IMAGE}"

echo "✅ Deployment Complete!"
