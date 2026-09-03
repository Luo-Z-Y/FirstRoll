# FirstRoll Azure Infrastructure

This Terraform root manages the Azure frontend and the production FastAPI service on Azure
Container Apps. It does not manage the Spaceship DNS records, Supabase project, GitHub repository
settings/secrets or Render rollback service.

## Managed resources

- the existing `firstroll-web` Azure Static Web App, adopted through an import;
- the existing `firstroll.app` Static Web App custom-domain association, adopted through an import;
- Azure Container Registry Basic;
- Log Analytics workspace with 30-day retention;
- Azure Container Apps managed environment;
- user-assigned identity with `AcrPull` only;
- branch-bound GitHub build identity with `AcrPush` on ACR and `Reader` on the app;
- protected-environment GitHub deploy identity with `Contributor` on the app only;
- Azure federated credentials that exchange GitHub OIDC assertions without passwords;
- a public Container App running the existing `Dockerfile` image;
- the existing `api.firstroll.app` Container App custom-domain association.

The application is controlled by `deploy_container_app`. It is `true` in production; use `false`
only when bootstrapping a new environment before its first image exists.

After bootstrap, Terraform deliberately ignores only `template[0].container[0].image`. The protected
backend release workflow owns that field and deploys reviewed immutable digests. Terraform continues
to own environment values, secrets, probes, scaling, identity and ingress, so a later infrastructure
apply cannot silently roll the API back to the bootstrap tag.

## Passwordless GitHub delivery

`github_repository`, `github_repository_owner_id` and `github_repository_id` fix the trusted OIDC
subjects to the exact identity-bound prefix GitHub reports for `Luo-Z-Y/FirstRoll`. The numeric IDs
are public identifiers, not credentials. This matters because the current assertion is not the older
name-only `repo:owner/repository` form. Verify the live prefix before an apply:

```bash
gh api repos/Luo-Z-Y/FirstRoll/actions/oidc/customization/sub --jq .sub_claim_prefix
```

The build identity accepts only the `refs/heads/master` subject. The deploy identity accepts only
the `production` environment subject, so GitHub does not receive its short-lived Azure token until
the protected environment has passed its required human review.

After a reviewed apply, use the non-sensitive outputs to configure GitHub as described in
[`docs/RELEASE.md`](../../docs/RELEASE.md):

```bash
terraform output -raw github_build_client_id
terraform output -raw github_deploy_client_id
terraform output -raw container_registry_login_server
```

Terraform deliberately does not create GitHub secrets or activate the workflow. Keep
`BACKEND_RELEASE_ENABLED` absent until the identities, role assignments and all GitHub values are
ready. Do not add `AZURE_CREDENTIALS`, `ACR_USERNAME` or `ACR_PASSWORD`; the workflow does not use
them.

## Existing frontend import

The frontend was originally created manually in the Azure portal. `frontend.tf` describes that
same resource and contains import blocks that connect it to Terraform state. Azure Resource Manager
reports its immutable location as `centralus`, its SKU as `Free`, and `firstroll.app` as its
validated default domain. The portal's Overview label says `Global`, but Terraform must use the
underlying API value `centralus` to avoid replacing the resource.

Both imported resources use `prevent_destroy = true`. If a plan says either resource must be
replaced or destroyed, stop and correct the configuration rather than applying it. The ideal first
plan reports two imports and no frontend replacement.

The GitHub Actions workflow continues to build and deploy the frontend. Terraform manages the
Azure resource; GitHub Actions manages the website content deployed into that resource. Spaceship
continues to manage the domain's DNS records.

## State and secrets

Use an Azure Storage backend. `backend.hcl`, `terraform.tfvars`, state files and saved plans are
ignored by Git.

The NUS tenant currently permits Azure management operations but blocks local user tokens for the
Storage data plane through Conditional Access. The state account key is therefore stored in macOS
Keychain under service `firstroll-terraform-state-access-key`; it is never written to Terraform
configuration or Git. Before running local Terraform commands, load it only into the current shell:

```bash
export ARM_SUBSCRIPTION_ID="fae38f39-74b5-4255-b2fa-7d0267ee4676"
export ARM_ACCESS_KEY="$(security find-generic-password \
  -a firstroll-terraform \
  -s firstroll-terraform-state-access-key \
  -w)"
```

The access key grants broad state-account access. Do not print, share or commit it. For CI/CD, use
Azure workload identity/OIDC rather than copying this local key into GitHub.

The Supabase publishable key is not a privileged credential, but the local variable file is still
excluded. Do not pass DeepSeek, YouTube, Supabase service-role or deployment credentials through
Terraform variables: ordinary Terraform values are recorded in state.

The generic PostgreSQL connection URL is currently an explicit exception: `database_url` is a
sensitive Terraform variable so the Container App can declare the matching secret atomically with
its provider switch. Load it from macOS Keychain through `TF_VAR_database_url`; never write it to a
file or command history. It will be present in the encrypted remote state, so access to the state
account remains privileged. Moving this secret to Azure Key Vault is the next hardening step.

The GitHub identity client IDs are identifiers rather than passwords. They are outputs so the owner
can place them in the appropriate GitHub secret boundaries; Terraform state contains no GitHub token
and cannot approve a deployment.

## Bootstrap sequence

Run these commands from a workstation with Azure CLI and Terraform:

```bash
az account show
export ARM_SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
```

The AzureRM provider is configured with `resource_provider_registrations = "none"` because the NUS
subscription restricts unrelated Azure services. Register only the services FirstRoll needs:

```bash
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.ManagedIdentity
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.App
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
apply, then initialise and inspect both the frontend imports and API foundation:

```bash
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan -out=foundation.tfplan
terraform apply foundation.tfplan
```

Review the plan before applying it. The apply creates billable Azure resources, including Container
Registry Basic and Log Analytics. For the existing frontend, verify that the plan shows imports and
does not show replacement or destruction.

## Build the API image

After the foundation exists, build from the repository root. This subscription does not permit ACR
Tasks, so `az acr build` cannot be used; the image is built with local Docker and pushed to ACR.
The explicit platform makes the image compatible with Azure's Linux/amd64 Container Apps workers
even when the build runs on an Apple Silicon Mac.

```bash
FIRSTROLL_IMAGE_TAG="$(git rev-parse --short HEAD)"
FIRSTROLL_IMAGE="firstroll46ikj8.azurecr.io/firstroll-api:${FIRSTROLL_IMAGE_TAG}"

docker buildx build --platform linux/amd64 --tag "$FIRSTROLL_IMAGE" --load .

# Test the exact image before publishing it.
docker run -d --rm --name firstroll-api-smoke -p 18000:10000 \
  -e PORT=10000 \
  -e FIRSTROLL_PUBLIC_MODE=true \
  -e FIRSTROLL_VIDEO_ANALYSIS_ENABLED=false \
  -e FIRSTROLL_DEEP_STUDY_ENABLED=false \
  "$FIRSTROLL_IMAGE"
curl --fail --show-error http://127.0.0.1:18000/api/health
docker stop firstroll-api-smoke

az acr login --name firstroll46ikj8
docker push "$FIRSTROLL_IMAGE"
```

Set that immutable tag and the Supabase project URL in the ignored `terraform.tfvars`, then change
`deploy_container_app` to `true`. Store the browser-safe Supabase publishable key in macOS Keychain
instead of source control:

```bash
security add-generic-password \
  -a firstroll-terraform \
  -s firstroll-supabase-publishable-key \
  -w '<Supabase publishable key>' \
  -U

export TF_VAR_supabase_publishable_key="$(
  security find-generic-password \
    -a firstroll-terraform \
    -s firstroll-supabase-publishable-key \
    -w
)"
```

Run a new `terraform plan` and apply the reviewed saved plan. Keep the Keychain-derived environment
variable available for both operations.

## API custom domain

Spaceship owns the DNS records and Terraform owns Azure's association. Production uses:

```text
CNAME  api        firstroll-api.blackground-8d64e931.southeastasia.azurecontainerapps.io
TXT    asuid.api  <Container App custom-domain verification ID>
```

The live Azure association was imported as
`azurerm_container_app_custom_domain.api[0]`. Azure owns and renews its managed certificate.
`prevent_destroy` protects the association; the certificate fields are ignored because Azure
manages them outside Terraform. A normal plan must not replace or remove this resource.

## Authentication provider switch

Production remains on `auth_provider = "supabase"`. The staged alternative is
`auth_provider = "entra"`, which requires all of these values:

```hcl
auth_provider          = "entra"
entra_authority        = "https://TENANT.ciamlogin.com/TENANT_ID"
entra_api_client_id    = "<FirstRoll API application ID>"
entra_spa_client_id    = "<FirstRoll Web application ID>"
entra_api_scope        = "api://<FirstRoll API application ID>/access_as_user"
entra_required_scope   = "access_as_user"
```

Use an Entra External ID **customer** tenant with an email-and-password sign-up/sign-in flow. Do not
use a workforce or university tenant for public accounts. The Container App precondition rejects an
incomplete Entra selection, and Entra environment values are absent while Supabase is active so a
documentation-only migration does not create a needless production revision.

## Backend-owned quota persistence

The generic migration is
`database/migrations/202608200001_identity_neutral_deep_study_quotas.sql`. Install it on PostgreSQL,
create a dedicated login with only the grants documented at the end of that file, and store its URL
in macOS Keychain:

```bash
security add-generic-password \
  -a firstroll-terraform \
  -s firstroll-database-url \
  -w '<postgresql connection URL with sslmode=require>' \
  -U

export TF_VAR_database_url="$(
  security find-generic-password \
    -a firstroll-terraform \
    -s firstroll-database-url \
    -w
)"
```

Set `quota_provider = "postgres"` while keeping `auth_provider = "supabase"` for the first cut-over.
This proves quota storage independently of the Entra change. FastAPI then passes only the verified
provider and subject to PostgreSQL; browser bearer tokens never cross the database boundary.

After one healthy UTC quota day, the identity release may set `auth_provider = "entra"`. Terraform
requires Entra to use the PostgreSQL quota provider, preventing an invalid Entra-plus-legacy-RPC
deployment.

## Production verification

After any apply, verify:

```bash
curl --fail --show-error https://api.firstroll.app/api/health
curl --fail --show-error \
  'https://api.firstroll.app/api/discovery/search?q=In%20the%20Mood%20for%20Love&year=2000'
```

Also send a CORS preflight with origin `https://firstroll.app` and confirm the response returns that
exact origin. The current production plan should report `No changes` when no deployment is pending.
