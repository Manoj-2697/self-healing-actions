provider "aws" {
  # Ensure the region is explicitly set, as signature calculation can fail if the endpoint is ambiguous
  region = "us-east-1" 
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}