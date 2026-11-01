
resource "cloudflare_dns_record" "root" {
  zone_id = var.cloudflare_zone_id
  name    = "@"
  type    = "AAAA"
  content = var.vps_ipv6_address
  proxied = true
  ttl     = 1  
}

resource "cloudflare_dns_record" "www" {
  zone_id = var.cloudflare_zone_id
  name    = "www"
  type    = "AAAA"
  content = var.vps_ipv6_address
  proxied = true
  ttl     = 1
}
