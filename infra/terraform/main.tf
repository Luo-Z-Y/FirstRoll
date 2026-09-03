# -----------------------------------------------------------------------------
# Existing resource group
# -----------------------------------------------------------------------------
# A data source reads an Azure object that already exists. Terraform uses this
# resource group but does not create or own the resource group itself.
data "azurerm_resource_group" "firstroll" {
  name = var.resource_group_name
}

# -----------------------------------------------------------------------------
# Globally unique registry name
# -----------------------------------------------------------------------------
# Azure Container Registry names must be unique across all Azure customers. The
# random suffix is generated once and then preserved in Terraform state.
resource "random_string" "registry_suffix" {
  length  = 6
  upper   = false
  special = false
}

# -----------------------------------------------------------------------------
# Reusable calculated values
# -----------------------------------------------------------------------------
# `locals` are internal calculations rather than user inputs. They build the
# complete Docker image address and the environment variables passed to FastAPI.
locals {
  registry_name  = "firstroll${random_string.registry_suffix.result}"
  image          = "${azurerm_container_registry.firstroll.login_server}/${var.image_repository}:${var.image_tag}"
  needs_supabase = var.auth_provider == "supabase" || var.quota_provider == "supabase"

  application_environment = merge(
    {
      PORT                             = "10000"
      FIRSTROLL_PUBLIC_MODE            = "true"
      FIRSTROLL_VIDEO_ANALYSIS_ENABLED = "false"
      FIRSTROLL_DEEP_STUDY_ENABLED     = tostring(var.deep_study_enabled)
      FIRSTROLL_CORS_ALLOWED_ORIGINS   = join(",", var.allowed_origins)
      DEEPSEEK_MODEL                   = var.deepseek_model
    },
    local.needs_supabase ? {
      SUPABASE_URL = var.supabase_url
    } : {},
    # Keep the current revision byte-for-byte stable while Supabase is active.
    # Entra values appear together only when the explicit provider switch is made.
    var.auth_provider == "entra" ? {
      FIRSTROLL_AUTH_PROVIDER = "entra"
      ENTRA_AUTHORITY         = var.entra_authority
      ENTRA_API_CLIENT_ID     = var.entra_api_client_id
      ENTRA_SPA_CLIENT_ID     = var.entra_spa_client_id
      ENTRA_API_SCOPE         = var.entra_api_scope
      ENTRA_REQUIRED_SCOPE    = var.entra_required_scope
    } : {},
    var.quota_provider == "postgres" ? {
      FIRSTROLL_QUOTA_PROVIDER = "postgres"
    } : {}
  )
}

# -----------------------------------------------------------------------------
# Central application logs
# -----------------------------------------------------------------------------
# Container Apps sends stdout, stderr and platform diagnostics here so that API
# failures and container restarts can be investigated after they occur.
resource "azurerm_log_analytics_workspace" "firstroll" {
  name                = "firstroll-api-logs"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

# -----------------------------------------------------------------------------
# Private Docker image registry
# -----------------------------------------------------------------------------
# ACR stores versioned FirstRoll API images. It does not run the application;
# Azure Container Apps later pulls an image from this registry and runs it.
resource "azurerm_container_registry" "firstroll" {
  name                = local.registry_name
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

# -----------------------------------------------------------------------------
# Passwordless identity used to pull images
# -----------------------------------------------------------------------------
# This managed identity is an Azure service identity. Azure manages its
# credentials, so the Container App does not need a registry password.
resource "azurerm_user_assigned_identity" "container_pull" {
  name                = "firstroll-api-pull"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  tags                = var.tags
}

# Grant only image-download permission on this registry to the identity above.
resource "azurerm_role_assignment" "container_pull" {
  scope                            = azurerm_container_registry.firstroll.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_user_assigned_identity.container_pull.principal_id
  skip_service_principal_aad_check = true
}

# -----------------------------------------------------------------------------
# Passwordless identities used by GitHub Actions
# -----------------------------------------------------------------------------
# The build identity can exchange a GitHub-signed OIDC token only for a run on
# master. It can push an image to ACR, but it cannot update the Container App.
resource "azurerm_user_assigned_identity" "github_build" {
  name                = "firstroll-github-build"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "github_build" {
  name      = "github-master-build"
  parent_id = azurerm_user_assigned_identity.github_build.id
  issuer    = "https://token.actions.githubusercontent.com"
  subject   = "repo:${var.github_repository}:ref:refs/heads/master"
  audience  = ["api://AzureADTokenExchange"]
}

# AcrPush includes upload and metadata-read operations for this registry only.
resource "azurerm_role_assignment" "github_build_registry" {
  scope                            = azurerm_container_registry.firstroll.id
  role_definition_name             = "AcrPush"
  principal_id                     = azurerm_user_assigned_identity.github_build.principal_id
  skip_service_principal_aad_check = true
}

# The deploy identity has a different OIDC subject. Azure issues its token only
# to a job that GitHub identifies as using the protected production environment.
resource "azurerm_user_assigned_identity" "github_deploy" {
  name                = "firstroll-github-deploy"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "github_deploy" {
  name      = "github-production-deploy"
  parent_id = azurerm_user_assigned_identity.github_deploy.id
  issuer    = "https://token.actions.githubusercontent.com"
  subject   = "repo:${var.github_repository}:environment:production"
  audience  = ["api://AzureADTokenExchange"]
}

# -----------------------------------------------------------------------------
# Shared Container Apps hosting environment
# -----------------------------------------------------------------------------
# The environment supplies the networking and logging boundary. It is not the
# API itself; the API Container App is created inside it below.
resource "azurerm_container_app_environment" "firstroll" {
  name                       = var.environment_name
  location                   = var.location
  resource_group_name        = data.azurerm_resource_group.firstroll.name
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.firstroll.id
  tags                       = var.tags

  # Azure automatically gives a new environment the serverless Consumption
  # profile. Declaring that default prevents a perpetual post-create diff and
  # documents that FirstRoll is not reserving dedicated compute capacity.
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    minimum_count         = 0
    maximum_count         = 0
  }
}

# -----------------------------------------------------------------------------
# Running FastAPI service
# -----------------------------------------------------------------------------
resource "azurerm_container_app" "api" {
  # During bootstrap the registry is empty, so this switch creates zero API
  # apps. After an image is uploaded, setting the flag to true creates one app.
  count = var.deploy_container_app ? 1 : 0

  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.firstroll.id
  resource_group_name          = data.azurerm_resource_group.firstroll.name
  revision_mode                = "Single"
  # Match the environment's explicitly declared serverless profile. Azure
  # writes this default back after creation, so declaring it prevents drift.
  workload_profile_name = "Consumption"
  tags                  = var.tags

  identity {
    # Attach the passwordless identity that has the AcrPull role.
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_pull.id]
  }

  registry {
    # Tell Container Apps which registry to use and which identity authenticates.
    server   = azurerm_container_registry.firstroll.login_server
    identity = azurerm_user_assigned_identity.container_pull.id
  }

  dynamic "secret" {
    # Container Apps stores this value as a named secret. The environment
    # variable below refers to its name instead of duplicating the value.
    for_each = local.needs_supabase ? [1] : []

    content {
      name  = "supabase-publishable-key"
      value = var.supabase_publishable_key
    }
  }

  dynamic "secret" {
    # The PostgreSQL URL contains the dedicated backend role's password. It is
    # stored as a Container Apps secret and never enters the browser bundle.
    for_each = var.quota_provider == "postgres" ? [1] : []

    content {
      name  = "firstroll-database-url"
      value = var.database_url
    }
  }

  ingress {
    # Public HTTPS traffic terminates at Azure and is forwarded to FastAPI on
    # port 10000. Plain HTTP is not allowed.
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 10000
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # Replicas are independent running copies of the same Docker image.
    min_replicas = var.minimum_replicas
    max_replicas = var.maximum_replicas

    container {
      name   = "firstroll-api"
      image  = local.image
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        # Generate one Container Apps env block for each entry in the local map.
        for_each = local.application_environment

        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.needs_supabase ? [1] : []

        content {
          name        = "SUPABASE_PUBLISHABLE_KEY"
          secret_name = "supabase-publishable-key"
        }
      }

      dynamic "env" {
        for_each = var.quota_provider == "postgres" ? [1] : []

        content {
          name        = "FIRSTROLL_DATABASE_URL"
          secret_name = "firstroll-database-url"
        }
      }

      startup_probe {
        # Give imports and service initialisation time to finish before Azure
        # decides that the new container failed to start.
        transport               = "HTTP"
        port                    = 10000
        path                    = "/api/health"
        interval_seconds        = 5
        timeout                 = 3
        failure_count_threshold = 30
      }

      liveness_probe {
        # Restart a container that was running but repeatedly becomes unhealthy.
        transport               = "HTTP"
        port                    = 10000
        path                    = "/api/health"
        initial_delay           = 20
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 3
      }

      readiness_probe {
        # Stop routing visitor traffic to a temporarily unhealthy container.
        transport               = "HTTP"
        port                    = 10000
        path                    = "/api/health"
        interval_seconds        = 10
        timeout                 = 5
        failure_count_threshold = 3
        success_count_threshold = 1
      }
    }
  }

  lifecycle {
    # Terraform owns the app, configuration, secrets, probes and scaling. The
    # release workflow owns only the running image after bootstrap; ignoring
    # this one field prevents a later infrastructure apply from rolling back a
    # newer, human-approved digest.
    ignore_changes = [template[0].container[0].image]

    # Reject invalid configurations before Azure receives a deployment request.
    precondition {
      condition     = var.maximum_replicas >= var.minimum_replicas
      error_message = "maximum_replicas must be greater than or equal to minimum_replicas."
    }

    precondition {
      condition = (
        !var.deploy_container_app ||
        (
          (
            !local.needs_supabase
            || (startswith(var.supabase_url, "https://") && length(var.supabase_publishable_key) > 0)
          )
          && (
            var.quota_provider != "postgres"
            || (
              startswith(var.database_url, "postgresql://")
              && length(var.database_url) > length("postgresql://user:password@host/database")
            )
          )
          && (
            var.auth_provider != "entra"
            || (
              startswith(var.entra_authority, "https://")
              && length(var.entra_api_client_id) > 0
              && length(var.entra_spa_client_id) > 0
              && length(var.entra_api_scope) > 0
              && var.quota_provider == "postgres"
            )
          )
        )
      )
      error_message = "Configure every value required by the selected auth_provider before deploying the Container App."
    }
  }

  depends_on = [azurerm_role_assignment.container_pull]
}

# The build job may read the current image and revision for its approval
# summary. It cannot change the app. The conditional mirrors the app resource.
resource "azurerm_role_assignment" "github_build_app_reader" {
  count = var.deploy_container_app ? 1 : 0

  scope                            = azurerm_container_app.api[0].id
  role_definition_name             = "Reader"
  principal_id                     = azurerm_user_assigned_identity.github_build.principal_id
  skip_service_principal_aad_check = true
}

# Contributor is deliberately scoped to this one Container App rather than its
# resource group or subscription. It cannot alter ACR, DNS or unrelated apps.
resource "azurerm_role_assignment" "github_deploy_app" {
  count = var.deploy_container_app ? 1 : 0

  scope                            = azurerm_container_app.api[0].id
  role_definition_name             = "Contributor"
  principal_id                     = azurerm_user_assigned_identity.github_deploy.principal_id
  skip_service_principal_aad_check = true
}

# Azure owns and renews the managed TLS certificate. DNS remains in Spaceship,
# while Terraform records the hostname association and protects it from removal.
resource "azurerm_container_app_custom_domain" "api" {
  count = var.deploy_container_app ? 1 : 0

  name             = var.api_domain
  container_app_id = azurerm_container_app.api[0].id

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      certificate_binding_type,
      container_app_environment_certificate_id,
    ]
  }
}
