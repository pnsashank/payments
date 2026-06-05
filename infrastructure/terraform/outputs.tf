output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint — use this in .env and psql connections"
  value = aws_db_instance.paylens_oltp.endpoint
}

output "rds_db_name" {
  description = "RDS database name"
  value = aws_db_instance.paylens_oltp.db_name
}

output "s3_bucket_name" {
  description = "S3 data lake bucket name"
  value = aws_s3_bucket.data_lake.bucket
}

output "glue_role_arn" {
  description = "IAM role ARN for Glue jobs"
  value = aws_iam_role.glue_role.arn
}

output "glue_connection_name" {
  description = "Glue connection name for RDS"
  value = aws_glue_connection.rds_connection.name
}

output "glue_catalog_raw_db" {
  description = "Glue Data Catalog raw database name"
  value = aws_glue_catalog_database.paylens_raw.name
}

output "glue_catalog_curated_db" {
  description = "Glue Data Catalog curated database name"
  value = aws_glue_catalog_database.paylens_curated.name
}