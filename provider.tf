provider "aws" {
  region = "us-east-1"

  # These flags help bypass initial STS checks that often fail in CI/CD due to 
  # environment-specific signing issues or Metadata API restrictions.
  skip_metadata_api_check     = true
  skip_credentials_validation = true
  skip_requesting_account_id  = true

  # IMPORTANT: Ensure AWS_SECRET_ACCESS_KEY in your CI/CD settings 
  # does not contain trailing spaces, newlines, or hidden characters.
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}