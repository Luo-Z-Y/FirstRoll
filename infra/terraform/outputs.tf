# -----------------------------------------------------------------------------
# Frontend addresses
# -----------------------------------------------------------------------------

output "static_web_app_default_hostname" {
  description = "Azure-generated hostname for the imported frontend."
  value       = azurerm_static_web_app.frontend.default_host_name
}

output "static_web_app_url" {
  description = "Public URL using the imported custom domain."
  value       = "https://${azurerm_static_web_app_custom_domain.apex.domain_name}"
}

# -----------------------------------------------------------------------------
# Container registry details used by the Docker build step
# -----------------------------------------------------------------------------

output "container_registry_name" {
  description = "Azure Container Registry name used by the image build step."
  value       = azurerm_container_registry.firstroll.name
}

output "container_registry_login_server" {
  description = "Azure Container Registry login server."
  value       = azurerm_container_registry.firstroll.login_server
}

# -----------------------------------------------------------------------------
# Backend hosting addresses
# -----------------------------------------------------------------------------

output "container_app_environment_name" {
  description = "Azure Container Apps managed environment name."
  value       = azurerm_container_app_environment.firstroll.name
}

output "container_app_fqdn" {
  description = "Azure-assigned API hostname; null until deploy_container_app is true."
  value       = try(azurerm_container_app.api[0].ingress[0].fqdn, null)
}

output "container_app_url" {
  description = "Azure-assigned HTTPS API origin; null until deploy_container_app is true."
  value       = try("https://${azurerm_container_app.api[0].ingress[0].fqdn}", null)
}

output "api_custom_domain_url" {
  description = "Stable custom HTTPS origin for the public FastAPI service."
  value       = try("https://${azurerm_container_app_custom_domain.api[0].name}", null)
}

output "api_domain_verification_id" {
  description = "TXT value used at asuid.api to prove domain ownership to Azure."
  value       = try(azurerm_container_app.api[0].custom_domain_verification_id, null)
  sensitive   = true
}
