data "azurerm_resource_group" "firstroll" {
  name = var.resource_group_name
}

resource "random_string" "registry_suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  registry_name = "firstroll${random_string.registry_suffix.result}"
  image         = "${azurerm_container_registry.firstroll.login_server}/${var.image_repository}:${var.image_tag}"

  application_environment = {
    PORT                             = "10000"
    FIRSTROLL_PUBLIC_MODE            = "true"
    FIRSTROLL_VIDEO_ANALYSIS_ENABLED = "false"
    FIRSTROLL_DEEP_STUDY_ENABLED     = tostring(var.deep_study_enabled)
    FIRSTROLL_CORS_ALLOWED_ORIGINS   = join(",", var.allowed_origins)
    SUPABASE_URL                     = var.supabase_url
    DEEPSEEK_MODEL                   = var.deepseek_model
  }
}

resource "azurerm_log_analytics_workspace" "firstroll" {
  name                = "firstroll-api-logs"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_container_registry" "firstroll" {
  name                = local.registry_name
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "container_pull" {
  name                = "firstroll-api-pull"
  location            = var.location
  resource_group_name = data.azurerm_resource_group.firstroll.name
  tags                = var.tags
}

resource "azurerm_role_assignment" "container_pull" {
  scope                            = azurerm_container_registry.firstroll.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_user_assigned_identity.container_pull.principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_container_app_environment" "firstroll" {
  name                       = var.environment_name
  location                   = var.location
  resource_group_name        = data.azurerm_resource_group.firstroll.name
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.firstroll.id
  tags                       = var.tags
}

resource "azurerm_container_app" "api" {
  count = var.deploy_container_app ? 1 : 0

  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.firstroll.id
  resource_group_name          = data.azurerm_resource_group.firstroll.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_pull.id]
  }

  registry {
    server   = azurerm_container_registry.firstroll.login_server
    identity = azurerm_user_assigned_identity.container_pull.id
  }

  secret {
    name  = "supabase-publishable-key"
    value = var.supabase_publishable_key
  }

  ingress {
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
    min_replicas = var.minimum_replicas
    max_replicas = var.maximum_replicas

    container {
      name   = "firstroll-api"
      image  = local.image
      cpu    = 0.5
      memory = "1Gi"

      dynamic "env" {
        for_each = local.application_environment

        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name        = "SUPABASE_PUBLISHABLE_KEY"
        secret_name = "supabase-publishable-key"
      }

      startup_probe {
        transport               = "HTTP"
        port                    = 10000
        path                    = "/api/health"
        interval_seconds        = 5
        timeout                 = 3
        failure_count_threshold = 30
      }

      liveness_probe {
        transport               = "HTTP"
        port                    = 10000
        path                    = "/api/health"
        initial_delay           = 20
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 3
      }

      readiness_probe {
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
    precondition {
      condition     = var.maximum_replicas >= var.minimum_replicas
      error_message = "maximum_replicas must be greater than or equal to minimum_replicas."
    }

    precondition {
      condition = (
        !var.deploy_container_app ||
        (startswith(var.supabase_url, "https://") && length(var.supabase_publishable_key) > 0)
      )
      error_message = "Set supabase_url and supabase_publishable_key before deploying the Container App."
    }
  }

  depends_on = [azurerm_role_assignment.container_pull]
}
