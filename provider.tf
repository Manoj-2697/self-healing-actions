provider "aws" {
  region = "us-east-1"

  # Setting regional endpoints can help resolve signature mismatch issues in specific environments
  # and ensures the client uses the correct signing method for the region.
  # Note: Ensure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correctly set in your environment variables
  # without trailing spaces or hidden characters.
  endpoints {
    sts = "https://sts.us-east-1.amazonaws.com"
  }
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}