# ChatLite App Terraform

This folder deploys ChatLite to an existing Kubernetes cluster. For AWS EKS,
run the Terraform in `infra/terraform` first, then configure kubeconfig:

```bash
aws eks update-kubeconfig --region us-east-1 --name kscluster
```

Then deploy the app:

```bash
cd infra/terraform/k8s-app
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan
terraform apply
```

Set `image` in `terraform.tfvars` to the pushed image, for example:

```hcl
image = "anitalluri00/chatlite:latest"
```

Keep `replicas = 1` if you use SQLite storage. Use PostgreSQL with
`database_url` before increasing replicas.
