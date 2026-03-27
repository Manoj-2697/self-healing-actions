output "s3_bucket_id" {
  value = aws_s3_bucket.etl_bucket.id
}

output "lambda_arn" {
  value = aws_lambda_function.etl_lambda.arn
}

output "iam_role_arn" {
  value = aws_iam_role.lambda_exec_role.arn
}
