resource "github_repository" "ignite" {
  name        = var.repository_name
  description = var.repository_description
  visibility  = "private"

  has_issues      = true
  has_projects    = false
  has_wiki        = false
  has_discussions = false

  auto_init          = false
  allow_auto_merge   = true
  allow_merge_commit = true
  allow_squash_merge = true
  allow_rebase_merge = true

  delete_branch_on_merge = true

  vulnerability_alerts = true
}

resource "github_branch_default" "main" {
  repository = github_repository.ignite.name
  branch     = var.default_branch
}

resource "github_branch_protection" "main" {
  repository_id = github_repository.ignite.node_id
  pattern       = var.default_branch

  required_status_checks {
    strict = true
    contexts = [
      "backend",
      "backup",
      "frontend"
    ]
  }

  require_conversation_resolution = true

  allows_deletions    = false
  allows_force_pushes = false
}
