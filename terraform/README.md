# 🌍 Infrastructure as Code (Terraform)

This directory contains the Terraform configuration to deploy the **AI-Resilient ETL Pipeline** infrastructure on AWS.

## 📦 Resources Created
*   **S3 Bucket**: Private storage for ETL data with secure public access blocking.
*   **AWS Lambda**: A Python 3.12 runtime function to process the ETL tasks.
*   **IAM Roles & Policies**: Fine-grained "Least Privilege" access for the Lambda function.

## 🏗️ Folder Structure
```text
terraform/
├── main.tf         # Providers and backend setup
├── variables.tf    # Configurable inputs (Region, Names, etc.)
├── s3.tf           # S3 bucket definitions
├── iam.tf          # Security roles and policies
├── lambda.tf       # Lambda function configuration
└── outputs.tf      # Key deployment values (Bucket ID, Lambda ARN)
```

## 🔐 Prerequisites (AWS IAM)
To deploy this infrastructure, you must have an IAM User with the following permissions:
*   `AmazonS3FullAccess`
*   `AWSLambda_FullAccess`
*   `IAMFullAccess`

### 🔑 GitHub Secrets Configuration
For the automated pipeline to work, the following **Secrets** must be added to your GitHub repository settings:
1.  `AWS_ACCESS_KEY_ID`: Your IAM user access key.
2.  `AWS_SECRET_ACCESS_KEY`: Your IAM user secret key.

## 🚀 Local Deployment Commands
If you wish to test or deploy manually from your machine:
```bash
# 1. Initialize (Downloads AWS provider)
terraform init

# 2. Plan (Preview what will be built)
terraform plan

# 3. Apply (Execute the deployment)
terraform apply -auto-approve
```

## 🔄 CI/CD Integration
*   The **AI-Driven ETL Self-Healing Pipeline** ([`.github/workflows/cd.yaml`](../.github/workflows/cd.yaml)) contains commented-out steps for automated infrastructure deployment.
*   **Deployment Rule**: `terraform apply` is configured to only run on the `master` branch and only if the code verification tests pass.

## ⚠️ Important Note: State Management
By default, this project uses a **Local Backend**.
*   **Warning**: GitHub Actions runners are ephemeral. If you deploy using the pipeline without a **Remote Backend** (e.g., S3), the `terraform.tfstate` file will be lost after each run.
*   **Recommendation**: Configure an S3 remote backend in `main.tf` for production-scale use.
