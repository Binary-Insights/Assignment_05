import boto3
import os
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upload_folder_to_s3(local_folder: str, bucket_name: str, s3_prefix: str, aws_profile: str = None):
    """
    Upload all files in a local folder (recursively) to an S3 bucket under a given prefix.
    
    Args:
        local_folder (str): Path to the local folder to upload
        bucket_name (str): Name of the S3 bucket
        s3_prefix (str): S3 key prefix (folder path in bucket)
        aws_profile (str, optional): AWS profile to use (if not default)
    
    Raises:
        FileNotFoundError: If local_folder doesn't exist
        Exception: If S3 upload fails
    """
    # Validate local folder exists
    local_folder_path = Path(local_folder)
    if not local_folder_path.exists():
        raise FileNotFoundError(f"Local folder not found: {local_folder}")
    
    if not local_folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {local_folder}")
    
    # Check if folder has content
    files_to_upload = list(local_folder_path.rglob('*'))
    files_only = [f for f in files_to_upload if f.is_file()]
    
    if not files_only:
        logger.warning(f"No files found in {local_folder}")
        return 0
    
    logger.info(f"Found {len(files_only)} files to upload")
    
    try:
        # Initialize S3 client
        session = boto3.Session(profile_name=aws_profile) if aws_profile else boto3.Session()
        s3 = session.client('s3')
        
        # Upload files
        upload_count = 0
        for root, dirs, files in os.walk(local_folder_path):
            for file in files:
                local_path = Path(root) / file
                rel_path = local_path.relative_to(local_folder_path)
                s3_key = f"{s3_prefix}/{rel_path.as_posix()}"
                
                try:
                    logger.info(f"Uploading {local_path} to s3://{bucket_name}/{s3_key}")
                    s3.upload_file(str(local_path), bucket_name, s3_key)
                    upload_count += 1
                except Exception as e:
                    logger.error(f"Failed to upload {local_path}: {str(e)}")
                    raise
        
        logger.info(f"✓ Successfully uploaded {upload_count} files to s3://{bucket_name}/{s3_prefix}")
        return upload_count
        
    except Exception as e:
        logger.error(f"S3 upload failed: {str(e)}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload raw data to S3 bucket")
    parser.add_argument("--local_folder", type=str, required=True, 
                        help="Local folder to upload (e.g. data/raw/company_name)")
    parser.add_argument("--bucket", type=str, required=True, 
                        help="S3 bucket name")
    parser.add_argument("--prefix", type=str, required=True, 
                        help="S3 prefix/folder (e.g. raw/company_name)")
    parser.add_argument("--profile", type=str, default=None, 
                        help="AWS profile name (optional)")
    
    args = parser.parse_args()
    
    try:
        upload_folder_to_s3(args.local_folder, args.bucket, args.prefix, args.profile)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        exit(1)
