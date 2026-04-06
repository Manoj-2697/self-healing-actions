terraform {
  backend "s3" {
    bucket         = "terraform-tfstate-bucket-aiuscase"
    key            = "self-healing-ai-demo/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
  }
}