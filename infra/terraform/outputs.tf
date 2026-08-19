output "container_registry_name" {
  description = "Azure Container Registry name used by the image build step."
  value       = azurerm_container_registry.firstroll.name
}

output "container_registry_login_server" {
  description = "Azure Container Registry login server."
  value       = azurerm_container_registry.firstroll.login_server
}

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
