# app/infrastructure/minio_connection.py

from minio import Minio
from minio.error import S3Error
from config.settings import settings
import logging
from typing import Optional
import io

logger = logging.getLogger(__name__)


class MinIOConnection:
    """MinIO connection manager for file storage"""
    
    def __init__(self):
        self.client: Optional[Minio] = None
        self.bucket_name = settings.MINIO_BUCKET_NAME
    
    def connect(self):
        """Initialize MinIO client and ensure bucket exists"""
        try:
            self.client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            
            # Create bucket if it doesn't exist
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: {self.bucket_name}")
            else:
                logger.info(f"MinIO bucket already exists: {self.bucket_name}")
            
            # Bucket is kept private - images are accessed via presigned URLs
            # This ensures only authenticated users with valid URLs can access images
            
            logger.info("MinIO connection established successfully")
            
        except S3Error as e:
            logger.error(f"MinIO connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to MinIO: {e}")
            raise
    
    def disconnect(self):
        """Cleanup MinIO connection"""
        self.client = None
        logger.info("MinIO connection closed")
    
    def get_presigned_upload_url(
        self,
        object_name: str,
        expires_minutes: int = 15
    ) -> str:
        """
        Generate a presigned URL for uploading a file directly to MinIO
        
        Args:
            object_name: Name/path where the object will be stored
            expires_minutes: How long the URL is valid (default 15 minutes)
            
        Returns:
            Presigned upload URL
        """
        if not self.client:
            raise RuntimeError("MinIO client not initialized")
        
        from datetime import timedelta
        
        return self.client.presigned_put_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            expires=timedelta(minutes=expires_minutes)
        )
    
    def get_file_url(self, object_name: str, expires_hours: int = 24) -> str:
        """
        Get a presigned URL to access a file (private, temporary access)
        
        Args:
            object_name: Name/path of the object in the bucket
            expires_hours: How long the URL is valid in hours (default 24 hours)
            
        Returns:
            Presigned URL to access the file
        """
        from datetime import timedelta
        if not self.client:
            raise RuntimeError("MinIO client not initialized")
        
        return self.client.presigned_get_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            expires=timedelta(hours=expires_hours)
        )
    
    def delete_file(self, object_name: str):
        """
        Delete a file from MinIO
        
        Args:
            object_name: Name/path of the object in the bucket
        """
        if not self.client:
            raise RuntimeError("MinIO client not initialized")
        
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"File deleted successfully: {object_name}")
        except S3Error as e:
            logger.error(f"MinIO delete error: {e}")
            raise
    
    def file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in MinIO
        
        Args:
            object_name: Name/path of the object in the bucket
            
        Returns:
            True if file exists, False otherwise
        """
        if not self.client:
            raise RuntimeError("MinIO client not initialized")
        
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            # Other errors, re-raise
            logger.error(f"MinIO stat error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error checking file existence: {e}")
            raise


# Global MinIO connection instance
minio_connection = MinIOConnection()
