output "repository_url" {
  value = github_repository.app.html_url
}

output "repository_full_name" {
  value = github_repository.app.full_name
}

output "production_environment" {
  value = github_repository_environment.production.environment
}
