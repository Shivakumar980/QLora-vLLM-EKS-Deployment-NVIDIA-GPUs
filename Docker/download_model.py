import os
import boto3
from pathlib import Path

S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "llama-2-7b-merged-vllm")
LOCAL_MODEL_PATH = os.getenv("MODEL_PATH", "/models/llama-2-7b-merged-vllm")

def download_model_from_s3():
    """Download model from S3 to local path"""
    print(f"📥 Downloading model from s3://{S3_BUCKET}/{S3_PREFIX}...")
    
    s3 = boto3.client('s3')
    
    # Create local directory
    Path(LOCAL_MODEL_PATH).mkdir(parents=True, exist_ok=True)
    
    # List all objects in S3 prefix
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX)
    
    file_count = 0
    for page in pages:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            s3_key = obj['Key']
            
            # Skip if it's a directory marker
            if s3_key.endswith('/'):
                continue
            
            # Calculate local file path
            relative_path = s3_key.replace(S3_PREFIX, '').lstrip('/')
            local_file = os.path.join(LOCAL_MODEL_PATH, relative_path)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            
            # Download file
            print(f"  Downloading: {s3_key}")
            s3.download_file(S3_BUCKET, s3_key, local_file)
            file_count += 1
    
    print(f"✅ Downloaded {file_count} files to {LOCAL_MODEL_PATH}")

if __name__ == "__main__":
    download_model_from_s3()
