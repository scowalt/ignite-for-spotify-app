terraform {
  required_version = ">= 1.13.2, < 2.0.0"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "6.13.0"
    }
  }

  backend "s3" {
    bucket = "opentofu-state"
    key    = "ignite-for-spotify-app/github.tfstate"
    region = "auto"

    endpoints = {
      s3 = "https://a2dd27ff56de48a73e384881d22e60e2.r2.cloudflarestorage.com"
    }

    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    use_path_style              = true
  }
}

provider "github" {
  owner = "scowalt"
}
