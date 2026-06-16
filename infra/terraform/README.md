# AWS EKS Terraform

This folder creates the AWS foundation first:

- VPC with public/private subnets
- NAT gateway
- EKS cluster
- EKS managed node group
- EKS add-ons

The defaults match the requested production setup:

- AWS region: `us-east-1`
- Cluster name: `kscluster`
- EKS version: `1.36`
- Node group: `t3.large`, desired size `3`

If AWS does not support the default EKS version in your account or region, change
`cluster_version` in `terraform.tfvars`.

## 1. Configure AWS

```bash
aws configure
aws sts get-caller-identity
```

## 2. Create EKS

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan
terraform apply
```

If a previous apply failed while creating the managed node group with
`NodeCreationFailure`, delete the failed node group and apply again:

```bash
aws eks list-nodegroups --region us-east-1 --cluster-name kscluster
aws eks delete-nodegroup --region us-east-1 --cluster-name kscluster --nodegroup-name general
aws eks wait nodegroup-deleted --region us-east-1 --cluster-name kscluster --nodegroup-name general

terraform apply
```

If your failed node group has a generated name such as
`general-2026061509201577870000000b`, use that exact name in the delete and wait
commands.

## 3. Configure kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name kscluster
kubectl get nodes
```

## 4. Build And Push ChatLite Image

Log in to Docker Hub without saving the password in files:

```bash
docker login -u anitalluri00
```

Build and push from the project root:

```bash
cd ../..
export IMAGE_URL="anitalluri00/chatlite:latest"
docker build -t "$IMAGE_URL" .
docker push "$IMAGE_URL"
```

## 5. Deploy ChatLite

Use Kubernetes manifests:

If your Docker Hub repository is private, create an image pull secret first:

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

```bash
kubectl apply -k infra/k8s
kubectl -n chatlite get pods,svc,pvc,ingress
```

Or use the app Terraform in `infra/terraform/k8s-app`.

## Destroy

Delete the app first, then the AWS foundation:

```bash
kubectl delete -k infra/k8s
cd infra/terraform
terraform destroy
```
