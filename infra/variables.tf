variable "repository_name" {
  description = "Name of the GitHub repository"
  type        = string
  default     = "ignite-for-spotify-2"
}

variable "repository_description" {
  description = "Description of the GitHub repository"
  type        = string
  default     = "Bridge between Spotify and CustomsForge Ignition for Rocksmith"
}

variable "default_branch" {
  description = "Default branch name"
  type        = string
  default     = "main"
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for igniteforspotify.com"
  type        = string
  default     = "909b6d3a8e09224777e62afb808f119c"
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID that owns the database backup R2 bucket"
  type        = string
  default     = "a2dd27ff56de48a73e384881d22e60e2"
}

variable "database_backup_bucket_name" {
  description = "Private R2 bucket used for encrypted SQLite backups"
  type        = string
  default     = "ignite-for-spotify-db-backups"
}

variable "vps_ipv6_address" {
  description = "IPv6 address of the production VPS"
  type        = string
  default     = "2a01:4f8:1c1a:e2ea::1"
}
