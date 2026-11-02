variable "frontend_posthog_key" {
  type        = string
  sensitive   = true
  description = "Existing public browser analytics key, supplied privately from app Doppler prd."

  validation {
    condition     = can(regex("^phc_[A-Za-z0-9_-]+$", var.frontend_posthog_key))
    error_message = "A public PostHog project key is required, not a personal API credential."
  }
}

variable "frontend_sentry_dsn" {
  type        = string
  sensitive   = true
  description = "Public ingest DSN for the isolated frontend project 8, not an API upload credential."

  validation {
    condition     = can(regex("^https://[A-Za-z0-9_-]+@glitchtip\\.scowalt\\.com/8/?$", var.frontend_sentry_dsn))
    error_message = "The frontend DSN must use the reviewed GlitchTip host and isolated project 8."
  }
}

locals {
  release_inputs = {
    VITE_POSTHOG_KEY              = var.frontend_posthog_key
    VITE_SENTRY_DSN               = var.frontend_sentry_dsn
    LOCAL_SQLITE_CUTOVER_COMPLETE = "true"
    GLITCHTIP_SOURCEMAPS_ENABLED  = "true"
  }
}

resource "github_actions_environment_variable" "release_inputs" {
  for_each = toset([
    "VITE_POSTHOG_KEY",
    "VITE_SENTRY_DSN",
    "LOCAL_SQLITE_CUTOVER_COMPLETE",
    "GLITCHTIP_SOURCEMAPS_ENABLED",
  ])

  repository    = github_repository.app.name
  environment   = github_repository_environment.production.environment
  variable_name = each.key
  value         = local.release_inputs[each.key]
}
