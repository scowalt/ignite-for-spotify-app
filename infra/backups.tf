resource "cloudflare_r2_bucket" "database_backups" {
  account_id = var.cloudflare_account_id
  name       = var.database_backup_bucket_name
}

