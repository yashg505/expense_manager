"""Utility helpers for storing receipt artifacts in Google Cloud Storage."""

from __future__ import annotations

import os
import sys
import tempfile
from functools import lru_cache
from typing import Optional, Tuple, cast

from google.api_core.exceptions import GoogleAPIError, NotFound
from google.cloud import storage
import google.auth
from google.auth.credentials import Credentials

from expense_manager.exception import CustomException
from expense_manager.logger import get_logger
from expense_manager.utils.load_config import load_config_file

logger = get_logger(__name__)


def _load_storage_settings():
    bucket = None
    prefix = None

    try:
        config = load_config_file()
        storage_cfg = config.get("storage", {}) or {}
        bucket = storage_cfg.get("bucket_name") or storage_cfg.get("bucket")
        prefix = storage_cfg.get("artifacts_prefix") or storage_cfg.get("folder") or storage_cfg.get("prefix")
    except FileNotFoundError:
        config = {}
    except Exception as exc:
        logger.warning("Failed to load storage config: %s", exc)

    bucket = bucket or os.getenv("GCS_BUCKET_NAME") or "expense-manager-ai"
    prefix = prefix or os.getenv("GCS_ARTIFACTS_FOLDER") or "artifacts/images"
    return bucket, prefix


GCS_BUCKET, GCS_ARTIFACTS_PREFIX = _load_storage_settings()

def _build_blob_name(destination: str) -> str:
    destination = destination.lstrip("/")
    prefix = GCS_ARTIFACTS_PREFIX.strip("/")
    if prefix:
        return f"{prefix}/{destination}" if destination else prefix
    return destination


def _get_credentials() -> tuple[Optional[Credentials], Optional[str]]:
    scopes = ["https://www.googleapis.com/auth/devstorage.read_write"]
    try:
        creds, project = google.auth.default(scopes=scopes)
        creds = cast(Credentials, creds)
        project = cast(Optional[str], project)
        return creds, project
    except Exception as exc:
        logger.warning("Falling back to implicit storage credentials: %s", exc)
        return None, None


@lru_cache(maxsize=1)
def _get_storage_client() -> storage.Client:
    credentials, default_project = _get_credentials()
    project = os.getenv("GCP_PROJECT_ID")
    if credentials:
        if project:
            return storage.Client(credentials=credentials, project=project)
        return storage.Client(credentials=credentials)
    if project:
        return storage.Client(project=project)
    return storage.Client()


def is_gcs_uri(path: Optional[str]) -> bool:
    return bool(path and path.startswith("gs://"))


def parse_gcs_uri(uri: str) -> Tuple[str, str]:
    if not is_gcs_uri(uri):
        raise ValueError(f"Invalid GCS URI: {uri}")

    trimmed = uri[5:]
    bucket, _, blob = trimmed.partition("/")
    if not bucket or not blob:
        raise ValueError(f"Malformed GCS URI: {uri}")
    return bucket, blob


def upload_artifact(data: bytes, filename: str, *, content_type: Optional[str] = None) -> str:
    """Uploads raw bytes to the configured bucket and returns the gs:// URI."""

    if not GCS_BUCKET:
        raise CustomException("GCS bucket is not configured", sys)

    blob_name = _build_blob_name(filename)
    try:
        client = _get_storage_client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(blob_name)
        upload_kwargs = {}
        if content_type:
            upload_kwargs['content_type'] = content_type
        blob.upload_from_string(data, **upload_kwargs)
        gcs_uri = f"gs://{GCS_BUCKET}/{blob_name}"
        logger.info("Uploaded image to %s", gcs_uri)
        return gcs_uri
    except (GoogleAPIError, OSError) as exc:
        logger.error("Failed to upload artifact %s: %s", filename, exc)
        raise CustomException(exc, sys)


def download_artifact_to_temp(uri: str) -> str:
    """Downloads the blob to a temporary file and returns the local path."""

    bucket_name, blob_name = parse_gcs_uri(uri)
    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        suffix = os.path.splitext(blob_name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            blob.download_to_file(temp_file)
            temp_path = temp_file.name

        logger.debug("Downloaded %s to %s", uri, temp_path)
        return temp_path
    except NotFound:
        logger.error("Blob not found for uri %s", uri)
        raise CustomException(f"Blob not found: {uri}", sys)
    except GoogleAPIError as exc:
        logger.error("Failed to download %s: %s", uri, exc)
        raise CustomException(exc, sys)


def delete_artifact(uri: str) -> bool:
    """Deletes blob represented by the URI. Returns True if deleted."""

    if not is_gcs_uri(uri):
        if uri and os.path.exists(uri):
            os.remove(uri)
            return True
        return False

    bucket_name, blob_name = parse_gcs_uri(uri)
    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()
        logger.info("Deleted GCS artifact %s", uri)
        return True
    except NotFound:
        logger.warning("Attempted to delete missing GCS blob %s", uri)
        return False
    except GoogleAPIError as exc:
        logger.error("Failed to delete %s: %s", uri, exc)
        raise CustomException(exc, sys)


def ensure_local_artifact(path: str, *, existing_local: Optional[str] = None) -> str:
    """Returns a local file path for the given artifact, downloading if needed."""

    if existing_local and os.path.exists(existing_local):
        return existing_local

    if is_gcs_uri(path):
        return download_artifact_to_temp(path)

    if path and os.path.exists(path):
        return path

    raise FileNotFoundError(f"Artifact not found at: {path}")
