data "github_repository" "existing" {
  full_name = "scowalt/ignite-for-spotify-app"

  lifecycle {
    postcondition {
      condition = (
        self.repo_id == 1441388195 &&
        self.visibility == "public" &&
        self.default_branch == "main"
      )
      error_message = "Adoption requires the reviewed existing public repository and main branch."
    }
  }
}

resource "github_repository" "app" {
  name        = data.github_repository.existing.name
  description = "Bridge between Spotify and CustomsForge Ignition for Rocksmith"
  visibility  = "public"

  has_issues      = true
  has_projects    = false
  has_wiki        = false
  has_discussions = false

  auto_init              = false
  allow_auto_merge       = false
  allow_merge_commit     = true
  allow_squash_merge     = true
  allow_rebase_merge     = true
  delete_branch_on_merge = false

  lifecycle {
    prevent_destroy = true

    postcondition {
      condition     = self.repo_id == 1441388195
      error_message = "The repository resource must adopt the reviewed existing GitHub ID."
    }
  }
}

resource "github_branch_default" "main" {
  repository = github_repository.app.name
  branch     = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "github_repository_environment" "production" {
  repository          = github_repository.app.name
  environment         = "production"
  can_admins_bypass   = false
  prevent_self_review = false

  reviewers {
    users = [1100550]
  }

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "github_repository_environment_deployment_policy" "main" {
  repository     = github_repository.app.name
  environment    = github_repository_environment.production.environment
  branch_pattern = "main"

  lifecycle {
    prevent_destroy = true
  }
}

resource "github_actions_variable" "publishing_enabled" {
  repository    = github_repository.app.name
  variable_name = "PRODUCTION_PUBLISHING_ENABLED"
  value         = "false"
}
