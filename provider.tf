provider "aws" {
  region = "us-east-1"

  # Note: The SignatureDoesNotMatch error is almost always due to the 
  # AWS_SECRET_ACCESS_KEY containing a trailing newline, space, or quotes.
  # Ensure your CI/CD secrets are stored as raw strings without extra characters.
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}