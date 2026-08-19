# -----------------------------------------------------------------------------
# Existing Azure Static Web App
# -----------------------------------------------------------------------------
#
# The frontend already exists because it was created manually in the Azure
# portal. This resource block describes that same object so Terraform can adopt
# it; it must NOT be used to create a second Static Web App.
#
# The import block at the bottom of this file connects the Terraform address
# `azurerm_static_web_app.frontend` to the existing Azure resource ID.
resource "azurerm_static_web_app" "frontend" {
  name                = var.static_web_app_name
  resource_group_name = data.azurerm_resource_group.firstroll.name
  location            = var.static_web_app_location

  # FirstRoll currently needs only the Free Static Web Apps plan. Keep the tier
  # and size together because Azure represents both values separately.
  sku_tier = var.static_web_app_sku
  sku_size = var.static_web_app_sku

  # Visitors must be able to reach the site over the public internet. Preview
  # environments allow pull requests to receive temporary preview deployments.
  public_network_access_enabled = true
  preview_environments_enabled  = true

  lifecycle {
    # The frontend is already serving firstroll.app. Refuse any normal
    # Terraform operation that would delete it, including an accidental
    # replacement caused by a mismatched location or name.
    prevent_destroy = true

    # The existing GitHub Action deploys the built `dist` directory by using
    # Azure's deployment token. Azure can update these repository metadata
    # fields during a deployment, so Terraform should not fight those changes.
    ignore_changes = [
      repository_url,
      repository_branch,
    ]
  }
}

# -----------------------------------------------------------------------------
# Existing firstroll.app custom-domain association
# -----------------------------------------------------------------------------
#
# Spaceship continues to host the DNS records themselves. This resource manages
# only Azure's side of the relationship: it tells the Static Web App that it is
# authorised to serve the firstroll.app hostname and its managed TLS certificate.
resource "azurerm_static_web_app_custom_domain" "apex" {
  static_web_app_id = azurerm_static_web_app.frontend.id
  domain_name       = var.frontend_domain

  # firstroll.app is an apex/root domain rather than a subdomain such as
  # www.firstroll.app. Azure requires TXT-token validation for apex domains.
  validation_type = "dns-txt-token"

  lifecycle {
    # Removing the association would break firstroll.app even though the Azure
    # generated hostname continued to work, so protect it from deletion too.
    prevent_destroy = true

    # Azure's import API does not return the validation method originally used
    # for an already validated domain. Without this rule, the provider treats
    # the required configuration value above as a reason to replace the healthy
    # domain association. Preserve the imported setting instead.
    ignore_changes = [validation_type]
  }
}

# -----------------------------------------------------------------------------
# One-time imports for resources that were created manually
# -----------------------------------------------------------------------------
#
# An import does not copy or recreate a resource. It records that the existing
# Azure object is now represented by the Terraform resource address in `to`.
# Terraform will show these imports in the plan and perform them during apply.
import {
  to = azurerm_static_web_app.frontend
  id = "/subscriptions/fae38f39-74b5-4255-b2fa-7d0267ee4676/resourceGroups/firstroll-production/providers/Microsoft.Web/staticSites/firstroll-web"
}

import {
  to = azurerm_static_web_app_custom_domain.apex
  id = "/subscriptions/fae38f39-74b5-4255-b2fa-7d0267ee4676/resourceGroups/firstroll-production/providers/Microsoft.Web/staticSites/firstroll-web/customDomains/firstroll.app"
}
