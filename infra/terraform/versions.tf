terraform {
  # Keep Terraform within the tested major version. A future 2.x release may
  # contain breaking language or state-format changes.
  required_version = ">= 1.8.0, < 2.0.0"

  # Providers are plugins that translate Terraform resources into calls to a
  # particular platform. AzureRM manages Azure; Random creates the stable ACR
  # name suffix stored in Terraform state.
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Supply the storage account and container through backend.hcl during init.
  # The state store is bootstrapped separately because Terraform cannot create
  # the backend in which its own state is already expected to live.
  backend "azurerm" {}
}

provider "azurerm" {
  # `features {}` activates the Azure provider with its standard behaviour.
  features {}

  # The NUS subscription restricts some Azure services. Register only the
  # providers FirstRoll actually uses instead of asking AzureRM to register a
  # broad catalogue of unrelated services during every first plan.
  resource_provider_registrations = "none"
}
