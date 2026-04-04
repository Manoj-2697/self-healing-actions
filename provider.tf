provider "aws" {
  region = "us-east-1"

  # Removed explicit STS endpoint configuration which can cause SignatureDoesNotMatch errors.
  # The AWS provider (v5.0+) handles regional STS endpoints automatically.
  # Ensure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correctly set in the CI/CD secrets
  # without any trailing spaces or newlines.
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}