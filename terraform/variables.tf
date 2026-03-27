variable "aws_region" {
  description = "The AWS region to deploy in"
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "The name of the S3 bucket"
  default     = "ai-healer-etl-bucket-unique-001"
}

variable "lambda_function_name" {
  description = "The name of the Lambda function"
  default     = "etl-data-processor-lambda"
}
