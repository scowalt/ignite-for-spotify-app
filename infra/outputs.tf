output "repository_url" {
  description = "The URL of the GitHub repository"
  value       = github_repository.ignite.html_url
}

output "repository_clone_url" {
  description = "The HTTPS clone URL of the repository"
  value       = github_repository.ignite.http_clone_url
}

output "repository_ssh_url" {
  description = "The SSH clone URL of the repository"
  value       = github_repository.ignite.ssh_clone_url
}

output "repository_full_name" {
  description = "The full name of the repository (owner/name)"
  value       = github_repository.ignite.full_name
}

output "dns_root_record" {
  description = "The root AAAA record for igniteforspotify.com"
  value       = cloudflare_dns_record.root.name
}

output "database_backup_bucket_name" {
  description = "R2 bucket containing encrypted application database backups"
  value       = cloudflare_r2_bucket.database_backups.name
}
