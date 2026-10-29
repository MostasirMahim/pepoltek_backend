"""
core/storage.py
Profile picture upload and management utilities.
"""
import hashlib
import io
import uuid
from typing import Optional, Tuple
from PIL import Image
from django.conf import settings
import boto3
from botocore.exceptions import ClientError


# Allowed image formats and constraints
ALLOWED_FORMATS = {'image/jpeg', 'image/png', 'image/webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_DIMENSIONS = (2000, 2000)
THUMBNAIL_SIZE = (400, 400)


class ProfilePictureService:
    """
    Handles profile picture upload, validation, resizing, and S3 storage.
    """
    
    def __init__(self):
        self.s3_client = None
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        
        if self.bucket_name:
            self.s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
            )
    
    def validate_image(self, file_data: bytes, content_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate image file format, size, and dimensions.
        Returns: (is_valid, error_message)
        """
        # Check content type
        if content_type not in ALLOWED_FORMATS:
            return False, f"Invalid format. Allowed: {', '.join(ALLOWED_FORMATS)}"
        
        # Check file size
        if len(file_data) > MAX_FILE_SIZE:
            return False, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        
        # Validate image with Pillow (prevents malicious files)
        try:
            img = Image.open(io.BytesIO(file_data))
            img.verify()
            
            # Reopen to check dimensions (verify() closes the image)
            img = Image.open(io.BytesIO(file_data))
            width, height = img.size
            
            if width > MAX_DIMENSIONS[0] or height > MAX_DIMENSIONS[1]:
                return False, f"Image too large. Maximum dimensions: {MAX_DIMENSIONS[0]}x{MAX_DIMENSIONS[1]}px"
            
            return True, None
        
        except Exception as e:
            return False, f"Invalid or corrupted image file: {str(e)}"
    
    def resize_and_optimize(self, file_data: bytes, target_size: Tuple[int, int] = THUMBNAIL_SIZE) -> bytes:
        """
        Resize image to target size while maintaining aspect ratio.
        Converts to RGB and optimizes for web.
        """
        img = Image.open(io.BytesIO(file_data))
        
        # Convert to RGB (handles RGBA, P, etc.)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize with aspect ratio preservation
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Save optimized image to bytes
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        return output.getvalue()
    
    def generate_storage_key(self, user_id: str, file_extension: str = 'jpg') -> str:
        """
        Generate unique S3 object key for profile picture.
        Format: profile-pictures/{user_id}/{unique_id}.{ext}
        """
        unique_id = str(uuid.uuid4())[:8]
        return f"profile-pictures/{user_id}/{unique_id}.{file_extension}"
    
    def upload_to_s3(self, file_data: bytes, storage_key: str, content_type: str = 'image/jpeg') -> Tuple[bool, Optional[str]]:
        """
        Upload image to S3 private bucket.
        Returns: (success, error_message)
        """
        if not self.s3_client or not self.bucket_name:
            return False, "S3 storage not configured"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_key,
                Body=file_data,
                ContentType=content_type,
                CacheControl='max-age=31536000',  # 1 year cache
                Metadata={
                    'uploaded-by': 'profile-picture-service',
                    'sha256': hashlib.sha256(file_data).hexdigest(),
                }
            )
            return True, None
        
        except ClientError as e:
            return False, f"S3 upload failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def delete_from_s3(self, storage_key: str) -> Tuple[bool, Optional[str]]:
        """
        Delete profile picture from S3.
        Returns: (success, error_message)
        """
        if not self.s3_client or not self.bucket_name:
            return False, "S3 storage not configured"
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
            return True, None
        
        except ClientError as e:
            return False, f"S3 deletion failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def get_presigned_url(self, storage_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for private S3 object.
        Default expiration: 1 hour.
        """
        if not self.s3_client or not self.bucket_name or not storage_key:
            return None
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': storage_key,
                },
                ExpiresIn=expiration,
            )
            return url
        
        except Exception:
            return None
    
    def process_and_upload(
        self, 
        file_data: bytes, 
        content_type: str, 
        user_id: str,
        old_storage_key: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Complete profile picture upload pipeline:
        1. Validate image
        2. Resize and optimize
        3. Upload to S3
        4. Delete old image if exists
        
        Returns: (success, storage_key or error_message, presigned_url)
        """
        # Validate
        is_valid, error = self.validate_image(file_data, content_type)
        if not is_valid:
            return False, error, None
        
        # Resize and optimize
        try:
            optimized_data = self.resize_and_optimize(file_data)
        except Exception as e:
            return False, f"Image processing failed: {str(e)}", None
        
        # Generate storage key
        storage_key = self.generate_storage_key(user_id)
        
        # Upload to S3
        success, error = self.upload_to_s3(optimized_data, storage_key)
        if not success:
            return False, error, None
        
        # Delete old image if exists
        if old_storage_key:
            self.delete_from_s3(old_storage_key)  # Fire and forget
        
        # Generate presigned URL
        presigned_url = self.get_presigned_url(storage_key)
        
        return True, storage_key, presigned_url


# Singleton instance
profile_picture_service = ProfilePictureService()
