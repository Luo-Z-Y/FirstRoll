# -----------------------------------------------------------------------------
# Shared Azure placement
# -----------------------------------------------------------------------------

variable "resource_group_name" {
  description = "Existing Azure resource group that contains the FirstRoll production resources."
  type        = string
  default     = "firstroll-production"
}

variable "location" {
  description = "Azure region for the API infrastructure."
  type        = string
  default     = "Southeast Asia"
}

# -----------------------------------------------------------------------------
# Existing frontend configuration
# -----------------------------------------------------------------------------

variable "static_web_app_name" {
  description = "Name of the existing Azure Static Web App that Terraform will import."
  type        = string
  default     = "firstroll-web"
}

variable "static_web_app_location" {
  description = "Immutable API location of the existing Static Web App. Azure Portal labels it Global, but Azure Resource Manager reports centralus."
  type        = string
  default     = "centralus"

  validation {
    condition     = var.static_web_app_location == "centralus"
    error_message = "The imported firstroll-web resource reports its immutable API location as centralus; changing it would replace the live site."
  }
}

variable "static_web_app_sku" {
  description = "Hosting plan used by the existing Static Web App. FirstRoll should normally use Free."
  type        = string
  default     = "Free"

  validation {
    condition     = contains(["Free", "Standard"], var.static_web_app_sku)
    error_message = "static_web_app_sku must be either Free or Standard."
  }
}

variable "frontend_domain" {
  description = "Existing apex domain associated with the Azure Static Web App."
  type        = string
  default     = "firstroll.app"
}

variable "github_repository" {
  description = "GitHub owner/repository allowed to exchange Actions OIDC tokens for Azure identities."
  type        = string
  default     = "Luo-Z-Y/FirstRoll"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must use the owner/repository form."
  }
}

variable "github_repository_owner_id" {
  description = "Immutable numeric GitHub owner ID included in this repository's OIDC subject prefix."
  type        = string
  default     = "97681546"

  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_owner_id))
    error_message = "github_repository_owner_id must contain digits only."
  }
}

variable "github_repository_id" {
  description = "Immutable numeric GitHub repository ID included in this repository's OIDC subject prefix."
  type        = string
  default     = "1166686059"

  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_id))
    error_message = "github_repository_id must contain digits only."
  }
}

# -----------------------------------------------------------------------------
# Container Apps names and image selection
# -----------------------------------------------------------------------------

variable "environment_name" {
  description = "Azure Container Apps managed environment name."
  type        = string
  default     = "firstroll-container-env"
}

variable "container_app_name" {
  description = "Azure Container App name for the public FastAPI service."
  type        = string
  default     = "firstroll-api"
}

variable "api_domain" {
  description = "Custom HTTPS hostname bound to the public FastAPI Container App."
  type        = string
  default     = "api.firstroll.app"

  validation {
    condition     = can(regex("^[a-z0-9.-]+$", var.api_domain)) && strcontains(var.api_domain, ".")
    error_message = "api_domain must be a lower-case fully qualified domain name."
  }
}

variable "image_repository" {
  description = "Repository name inside Azure Container Registry."
  type        = string
  default     = "firstroll-api"
}

variable "image_tag" {
  description = "Immutable image tag to deploy, normally the short Git commit SHA."
  type        = string
  default     = "bootstrap"

  validation {
    condition     = length(trimspace(var.image_tag)) > 0 && var.image_tag != "latest"
    error_message = "image_tag must be a non-empty immutable tag; do not use latest."
  }
}

variable "deploy_container_app" {
  description = "Create the Container App only after its image exists in the registry."
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# API scaling and browser access
# -----------------------------------------------------------------------------

variable "minimum_replicas" {
  description = "Minimum warm replicas. Use 1 to avoid cold starts or 0 to minimise compute cost."
  type        = number
  default     = 1

  validation {
    condition     = var.minimum_replicas >= 0 && var.minimum_replicas <= 2
    error_message = "minimum_replicas must be between 0 and 2 for the demo environment."
  }
}

variable "maximum_replicas" {
  description = "Maximum replicas permitted for the public demo."
  type        = number
  default     = 2

  validation {
    condition     = var.maximum_replicas >= 1 && var.maximum_replicas <= 5
    error_message = "maximum_replicas must be between 1 and 5 for the demo environment."
  }
}

variable "allowed_origins" {
  description = "Exact browser origins allowed to send credentialed requests to FastAPI."
  type        = list(string)
  default     = ["https://firstroll.app"]

  validation {
    condition = alltrue([
      for origin in var.allowed_origins : startswith(origin, "https://") && !endswith(origin, "/")
    ])
    error_message = "Every allowed origin must be an https origin without a trailing slash."
  }
}

# -----------------------------------------------------------------------------
# Runtime integration and feature configuration
# -----------------------------------------------------------------------------

variable "supabase_url" {
  description = "Supabase project URL used for bearer-token verification."
  type        = string
  default     = ""
}

variable "supabase_publishable_key" {
  description = "Browser-safe Supabase publishable key used by the hosted API."
  type        = string
  sensitive   = true
  default     = ""
}

variable "quota_provider" {
  description = "Deep Study quota persistence boundary: legacy Supabase RPC or backend-owned PostgreSQL."
  type        = string
  default     = "supabase"

  validation {
    condition     = contains(["supabase", "postgres"], var.quota_provider)
    error_message = "quota_provider must be either supabase or postgres."
  }
}

variable "database_url" {
  description = "Backend-only PostgreSQL URL used when quota_provider is postgres. This sensitive value is stored in encrypted remote Terraform state and as a Container Apps secret."
  type        = string
  sensitive   = true
  default     = ""
}

variable "auth_provider" {
  description = "Single identity provider trusted by FastAPI during migration: supabase or entra."
  type        = string
  default     = "supabase"

  validation {
    condition     = contains(["supabase", "entra"], var.auth_provider)
    error_message = "auth_provider must be either supabase or entra."
  }
}

variable "entra_authority" {
  description = "External ID authority, for example https://TENANT.ciamlogin.com/TENANT_ID."
  type        = string
  default     = ""
}

variable "entra_api_client_id" {
  description = "Application client ID of the FirstRoll API registration in the external tenant."
  type        = string
  default     = ""
}

variable "entra_spa_client_id" {
  description = "Application client ID of the FirstRoll browser SPA registration."
  type        = string
  default     = ""
}

variable "entra_api_scope" {
  description = "Complete delegated API scope requested by MSAL, normally api://API_CLIENT_ID/access_as_user."
  type        = string
  default     = ""
}

variable "entra_required_scope" {
  description = "Scope claim FastAPI requires after validating an Entra access token."
  type        = string
  default     = "access_as_user"
}

variable "deep_study_enabled" {
  description = "Enable paid Deep Study only after the DeepSeek secret has been configured in Azure."
  type        = bool
  default     = false
}

variable "deepseek_model" {
  description = "DeepSeek model selected by the hosted study service."
  type        = string
  default     = "deepseek-v4-flash"
}

variable "tags" {
  description = "Tags applied to Terraform-managed Azure resources."
  type        = map(string)
  default = {
    application = "firstroll"
    environment = "production"
    managed-by  = "terraform"
  }
}
