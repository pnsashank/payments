terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Fetch Current Public IP
data "http" "my_ip" {
  url = "https://api.ipify.org?format=text"
}

# Networking: Security Group for RDS
data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "rds_sg" {
  name  = "${var.project_name}-rds-sg"
  description = "Allow PostgreSQL access from local machine and Glue"
  vpc_id = data.aws_vpc.default.id

  ingress {
    description = "PostgreSQL from local machine"
    from_port = 5432
    to_port = 5432
    protocol = "tcp"
    cidr_blocks = ["${trimspace(data.http.my_ip.response_body)}/32"]
  }

  ingress {
    description = "Allow Glue workers to communicare within the security group"
    from_port = 0
    to_port = 0
    protocol = "-1"
    self = true
  }

  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = var.project_name
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "paylens_oltp" {
  identifier = "${var.project_name}-oltp"
  engine = "postgres"
  engine_version = "16.6"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  storage_type = "gp2"

  db_name = var.db_name
  username = var.db_username
  password = var.db_password

  publicly_accessible  = true
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  backup_retention_period = 0
  skip_final_snapshot = true
  deletion_protection = false
  storage_encrypted = false
  multi_az = false

  tags = {
    Project = var.project_name
  }
}

# S3 Data Lake Bucket
resource "aws_s3_bucket" "data_lake" {
  bucket = var.s3_bucket_name
  force_destroy = true

  tags = {
    Project = var.project_name
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  versioning_configuration {
    status = "Disabled"
  }
}

# Folder structure
resource "aws_s3_object" "raw_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "raw/"
}

resource "aws_s3_object" "curated_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "curated/"
}

resource "aws_s3_object" "semantic_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "semantic/"
}

resource "aws_s3_object" "athena_results_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "athena-results/"
}

resource "aws_s3_object" "scripts_prefix" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "scripts/"
}

# IAM Role for Glue
data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "glue_role" {
  name = "${var.project_name}-glue-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json

  tags = {
    Project = var.project_name
  }
}

resource "aws_iam_role_policy_attachment" "glue_service_policy" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy_attachment" "glue_s3_policy" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Glue Connection to RDS
resource "aws_glue_connection" "rds_connection" {
  name = "${var.project_name}-rds-connection"

  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:postgresql://${aws_db_instance.paylens_oltp.endpoint}/${var.db_name}"
    USERNAME            = var.db_username
    PASSWORD            = var.db_password
  }

  connection_type = "JDBC"

  physical_connection_requirements {
    availability_zone      = "${var.aws_region}a"
    security_group_id_list = [aws_security_group.rds_sg.id]
    subnet_id              = data.aws_subnet.default.id
  }

  tags = {
    Project = var.project_name
  }
}

data "aws_subnet" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "availabilityZone"
    values = ["${var.aws_region}a"]
  }

  filter {
    name   = "defaultForAz"
    values = ["true"]
  }
}

# Glue Database in Data Catalog
resource "aws_glue_catalog_database" "paylens_raw" {
  name = "${var.project_name}_raw"
  description = "Raw OLTP tables extracted from RDS"
}

resource "aws_glue_catalog_database" "paylens_curated" {
  name = "${var.project_name}_curated"
  description = "Curated OLAP facts and dimensions"
}