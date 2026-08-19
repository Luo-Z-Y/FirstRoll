terraform {
  required_version = ">= 1.8.0, < 2.0.0"

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
  features {}
}
