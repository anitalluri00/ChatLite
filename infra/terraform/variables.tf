variable "aws_region" {
  description = "AWS region for the EKS cluster."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "kscluster"
}

variable "cluster_version" {
  description = "EKS Kubernetes version. Change this if your AWS region does not support the default yet."
  type        = string
  default     = "1.36"
}

variable "environment" {
  description = "Environment tag value."
  type        = string
  default     = "production"
}

variable "vpc_name" {
  description = "VPC name."
  type        = string
  default     = "eks-vpc"
}

variable "vpc_cidr" {
  description = "CIDR block for the EKS VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for public and private subnets."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "private_subnets" {
  description = "Private subnet CIDR blocks for EKS nodes."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnets" {
  description = "Public subnet CIDR blocks for load balancers and NAT."
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "node_instance_types" {
  description = "Managed node group instance types."
  type        = list(string)
  default     = ["t3.large"]
}

variable "node_min_size" {
  description = "Minimum node count."
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Maximum node count."
  type        = number
  default     = 6
}

variable "node_desired_size" {
  description = "Desired node count."
  type        = number
  default     = 3
}

variable "node_disk_size" {
  description = "Managed node root disk size in GB."
  type        = number
  default     = 50
}

variable "create_ecr_repository" {
  description = "Create an ECR repository for the ChatLite image."
  type        = bool
  default     = true
}

variable "ecr_repository_name" {
  description = "ECR repository name for the ChatLite image."
  type        = string
  default     = "chatlite"
}

variable "force_delete_ecr_repository" {
  description = "Allow Terraform destroy to delete the ECR repository even when images exist."
  type        = bool
  default     = false
}

variable "extra_tags" {
  description = "Extra tags applied to AWS resources."
  type        = map(string)
  default     = {}
}
