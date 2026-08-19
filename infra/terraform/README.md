# FirstRoll Azure API Infrastructure

This Terraform root defines the Azure foundation for migrating the public FastAPI service from
Render to Azure Container Apps. It does not manage the existing Azure Static Web App, custom domain,
Supabase project or Render rollback service.

## Managed resources

- Azure Container Registry Basic;
- Log Analytics workspace with 30-day retention;
- Azure Container Apps managed environment;
- user-assigned identity with `AcrPull` only;
- an optional public Container App running the existing `Dockerfile` image.

The application is gated by `deploy_container_app=false`. This lets the first apply create the
registry before an image is expected to exist.

## State and secrets

Use an Azure Storage backend. `backend.hcl`, `terraform.tfvars`, state files and saved plans are
ignored by Git.

The Supabase publishable key is not a privileged credential, but the local variable file is still
excluded. Do not pass DeepSeek, YouTube, Supabase service-role or deployment credentials through
Terraform variables: ordinary Terraform values are recorded in state. Those secrets will be added
to Azure separately before Deep Study is enabled.

## Bootstrap sequence

Run these commands from Azure Cloud Shell or a workstation with Azure CLI and Terraform:

```bash
az account show
export ARM_SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
```

Create a globally unique storage account for Terraform state once. Replace the example name before
running the commands:

```bash
az storage account create \
  --name REPLACE_WITH_GLOBALLY_UNIQUE_NAME \
  --resource-group firstroll-production \
  --location southeastasia \
  --sku Standard_LRS \
  --allow-blob-public-access false

az storage container create \
  --name tfstate \
  --account-name REPLACE_WITH_GLOBALLY_UNIQUE_NAME \
  --auth-mode login
```

Prepare untracked configuration:

```bash
cd infra/terraform
cp backend.hcl.example backend.hcl
cp terraform.tfvars.example terraform.tfvars
```

Replace the storage account name in `backend.hcl`. Leave `deploy_container_app=false` for the first
apply, then initialise and inspect the foundation:

```bash
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan -out=foundation.tfplan
terraform apply foundation.tfplan
```

Review the plan before applying it. The apply creates billable Azure resources, including Container
Registry Basic and Log Analytics.

## Build the API image

After the foundation exists, run from `infra/terraform`:

```bash
FIRSTROLL_ACR_NAME="$(terraform output -raw container_registry_name)"
FIRSTROLL_IMAGE_TAG="$(git rev-parse --short HEAD)"

az acr build \
  --registry "$FIRSTROLL_ACR_NAME" \
  --image "firstroll-api:$FIRSTROLL_IMAGE_TAG" \
  ../..
```

Set that immutable tag in `terraform.tfvars`, add the real Supabase public values, change
`deploy_container_app` to `true`, and run a new `terraform plan` and `terraform apply`.

Do not change the frontend API origin or DNS yet. First verify the Azure-assigned URL and
`/api/health`; domain cut-over is a later, reversible step.
