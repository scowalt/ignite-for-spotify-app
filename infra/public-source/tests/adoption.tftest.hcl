variables {
  frontend_posthog_key = "phc_fixture_browser_key"
  frontend_sentry_dsn  = "https://fixture-key@glitchtip.scowalt.com/8"
}

mock_provider "github" {
  mock_data "github_repository" {
    defaults = {
      name           = "ignite-for-spotify-app"
      repo_id        = 1441388195
      visibility     = "public"
      default_branch = "main"
    }
  }

  mock_resource "github_repository" {
    defaults = {
      repo_id = 1441388195
    }
  }
}

run "preserve_repository_and_gate_production" {
  command = plan

  assert {
    condition = (
      github_repository.app.name == "ignite-for-spotify-app" &&
      github_repository.app.visibility == "public" &&
      !github_repository.app.auto_init &&
      !github_repository.app.allow_auto_merge &&
      !github_repository.app.delete_branch_on_merge &&
      github_repository.app.allow_merge_commit &&
      github_repository.app.allow_squash_merge &&
      github_repository.app.allow_rebase_merge &&
      github_branch_default.main.branch == "main"
    )
    error_message = "Repository adoption must preserve existing identity and merge settings."
  }

  assert {
    condition = (
      github_repository_environment.production.environment == "production" &&
      !github_repository_environment.production.can_admins_bypass &&
      !github_repository_environment.production.prevent_self_review &&
      toset(github_repository_environment.production.reviewers[0].users) == toset([1100550]) &&
      github_repository_environment.production.deployment_branch_policy[0].custom_branch_policies &&
      !github_repository_environment.production.deployment_branch_policy[0].protected_branches &&
      github_repository_environment_deployment_policy.main.branch_pattern == "main" &&
      github_repository_environment_deployment_policy.main.tag_pattern == null
    )
    error_message = "Production requires owner approval with no bypass and only the main branch."
  }

  assert {
    condition = (
      github_actions_variable.publishing_enabled.variable_name == "PRODUCTION_PUBLISHING_ENABLED" &&
      github_actions_variable.publishing_enabled.value == "false"
    )
    error_message = "Publication must remain fenced until a separately reviewed retry is approved."
  }

  assert {
    condition = (
      length(github_actions_environment_variable.release_inputs) == 4 &&
      alltrue([for input in github_actions_environment_variable.release_inputs :
        input.repository == "ignite-for-spotify-app" && input.environment == "production"
      ]) &&
      github_actions_environment_variable.release_inputs["VITE_POSTHOG_KEY"].value == var.frontend_posthog_key &&
      github_actions_environment_variable.release_inputs["VITE_SENTRY_DSN"].value == var.frontend_sentry_dsn &&
      github_actions_environment_variable.release_inputs["LOCAL_SQLITE_CUTOVER_COMPLETE"].value == "true" &&
      github_actions_environment_variable.release_inputs["GLITCHTIP_SOURCEMAPS_ENABLED"].value == "true"
    )
    error_message = "Exactly the four approved production inputs must be staged without publishing."
  }
}

run "reject_empty_analytics_key" {
  command = plan

  variables {
    frontend_posthog_key = " "
  }

  expect_failures = [var.frontend_posthog_key]
}

run "reject_personal_analytics_token" {
  command = plan

  variables {
    frontend_posthog_key = "phx_fixture_personal_token"
  }

  expect_failures = [var.frontend_posthog_key]
}

run "reject_legacy_frontend_dsn" {
  command = plan

  variables {
    frontend_sentry_dsn = "https://fixture-key@glitchtip.scowalt.com/1"
  }

  expect_failures = [var.frontend_sentry_dsn]
}

run "reject_unreviewed_dsn_host" {
  command = plan

  variables {
    frontend_sentry_dsn = "https://fixture-key@example.invalid/8"
  }

  expect_failures = [var.frontend_sentry_dsn]
}

run "reject_wrong_repository_id" {
  command = plan

  override_data {
    target = data.github_repository.existing
    values = {
      name           = "ignite-for-spotify-app"
      repo_id        = 1122952429
      visibility     = "public"
      default_branch = "main"
    }
  }

  expect_failures = [data.github_repository.existing]
}

run "reject_private_destination" {
  command = plan

  override_data {
    target = data.github_repository.existing
    values = {
      name           = "ignite-for-spotify-app"
      repo_id        = 1441388195
      visibility     = "private"
      default_branch = "main"
    }
  }

  expect_failures = [data.github_repository.existing]
}

run "reject_changed_default_branch" {
  command = plan

  override_data {
    target = data.github_repository.existing
    values = {
      name           = "ignite-for-spotify-app"
      repo_id        = 1441388195
      visibility     = "public"
      default_branch = "release"
    }
  }

  expect_failures = [data.github_repository.existing]
}
