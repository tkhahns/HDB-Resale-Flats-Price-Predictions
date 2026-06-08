terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — fill in bucket/table before first apply.
  # Create the bucket and DynamoDB table manually once (they can't bootstrap themselves).
  backend "s3" {
    bucket         = "hdb-avm-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "hdb-avm-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
