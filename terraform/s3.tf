resource "aws_s3_bucket" "etl_bucket" {
  bucket = var.bucket_name
  tags = {
    Name        = "AI Healer ETL Bucket"
    Environment = "Dev"
  }
}

resource "aws_s3_bucket_public_access" "etl_bucket_block" {
  bucket = aws_s3_bucket.etl_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
