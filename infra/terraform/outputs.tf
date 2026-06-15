output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "EKS cluster version."
  value       = module.eks.cluster_version
}

output "cluster_security_group_id" {
  description = "EKS cluster security group ID."
  value       = module.eks.cluster_security_group_id
}

output "region" {
  description = "AWS region."
  value       = var.aws_region
}

output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs used by EKS."
  value       = module.vpc.private_subnets
}

output "ecr_repository_url" {
  description = "ECR repository URL for the ChatLite image."
  value       = try(aws_ecr_repository.chatlite[0].repository_url, null)
}

output "update_kubeconfig_command" {
  description = "Command to configure kubectl for the new EKS cluster."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
