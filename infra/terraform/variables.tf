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
