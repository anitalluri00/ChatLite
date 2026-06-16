# ChatLite Infrastructure

This folder is organized for a Terraform-first AWS EKS deployment.

```text
infra/
  k8s/                  Raw Kubernetes manifests for ChatLite
  terraform/            AWS EKS foundation Terraform
    k8s-app/            Optional Terraform to deploy ChatLite to Kubernetes
```

## Deployment Order

1. Run Terraform in `infra/terraform` to create AWS VPC, EKS, node group, and add-ons.
2. Update kubeconfig for the new EKS cluster.
3. Build and push the ChatLite Docker image to Docker Hub.
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
docker login -u anitalluri00
export IMAGE_URL="anitalluri00/chatlite:latest"
docker build -t "$IMAGE_URL" .
docker push "$IMAGE_URL"
```

## 4A. Deploy With Kubernetes Manifests

Edit first:

- `k8s/secret.yaml`: replace `CHATLITE_APP_SECRET`
- `k8s/secret.yaml`: optionally set `CHATLITE_DATABASE_URL` for PostgreSQL
- `k8s/deployment.yaml`: uses `anitalluri00/chatlite:latest` by default
- `k8s/ingress.yaml`: replace `chatlite.example.com` and ingress class if needed

If your Docker Hub repository is private, create an image pull secret before
deploying:

```bash
kubectl apply -f infra/k8s/namespace.yaml
read -s DOCKERHUB_PASSWORD
kubectl -n chatlite create secret docker-registry dockerhub-credentials \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=anitalluri00 \
  --docker-password="$DOCKERHUB_PASSWORD"
kubectl -n chatlite patch serviceaccount default \
  -p '{"imagePullSecrets":[{"name":"dockerhub-credentials"}]}'
```

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

Set `image` in `terraform.tfvars` to your Docker Hub image if you change the default.

Keep `replicas = 1` when using SQLite. For multiple replicas, configure
`CHATLITE_DATABASE_URL` for PostgreSQL instead of sharing one SQLite file.
