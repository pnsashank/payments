variable "aws_region" {
    description = "AWS region to deploy resources"
    type = string
    default = "ap-southeast-2"
}

variable "db_password" {
    description = "Master password for RDS PostgreSQL instance"
    type = string
    sensitive = true
}

variable "db_username" {
    description = "Master username for RDS PostgreSQL"
    type = string
    default = "postgres"
}

variable "db_name" {
    description = "Intial database name"
    type = string 
    default = "paylens"
}

variable "s3_bucket_name" {
    description = "Name of the S3 data lake bucket"
    type = string 
    default = "paylens-data-lake"
}

variable "project_name" {
    description = "Project name used for tagging and naming resources"
    type = string 
    default = "paylens"
}