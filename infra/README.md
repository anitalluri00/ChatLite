# ChatLite Infrastructure

This folder is organized for a Terraform-first AWS EKS deployment.

```text
infra/
  k8s/                  Raw Kubernetes manifests for ChatLite
  terraform/            AWS EKS foundation Terraform
    k8s-app/            Optional Terraform to deploy ChatLite to Kubernetes
```

## Deployment Order

1. Run Terraform in `infra/terraform` to create AWS VPC, EKS, node group, add-ons,
   and optional ECR repository.
2. Update kubeconfig for the new EKS cluster.
3. Build and push the ChatLite Docker image to ECR.
4. Deploy ChatLite with `kubectl apply -k infra/k8s` or Terraform in
   `infra/terraform/k8s-app`.

## 1. Run AWS EKS Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan
terraform apply
```

## 2. Configure kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name kscluster
kubectl get nodes
```

## 3. Build And Push Image

From the project root:

```bash
export IMAGE_URL="$(terraform -chdir=infra/terraform output -raw ecr_repository_url):latest"
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin "$(echo "$IMAGE_URL" | cut -d/ -f1)"
docker build -t "$IMAGE_URL" .
docker push "$IMAGE_URL"
```

## 4A. Deploy With Kubernetes Manifests

Edit first:

- `k8s/secret.yaml`: replace `CHATLITE_APP_SECRET`
- `k8s/secret.yaml`: optionally set `CHATLITE_DATABASE_URL` for PostgreSQL
- `k8s/deployment.yaml`: replace `image: chatlite:latest` with your ECR image
- `k8s/ingress.yaml`: replace `chatlite.example.com` and ingress class if needed

Apply:

```bash
kubectl apply -k infra/k8s
kubectl -n chatlite get pods,svc,pvc,ingress
```

Port-forward without ingress:

```bash
kubectl -n chatlite port-forward svc/chatlite 8501:80
```

Open:

```text
http://localhost:8501
```

## 4B. Deploy With App Terraform

```bash
cd infra/terraform/k8s-app
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan
terraform apply
```

Set `image` in `terraform.tfvars` to your ECR image URL.

Keep `replicas = 1` when using SQLite. For multiple replicas, configure
`CHATLITE_DATABASE_URL` for PostgreSQL instead of sharing one SQLite file.
