provider "google" {
  project = var.project_id
}

resource "google_project_service" "required" {
  for_each = toset(var.enabled_project_services)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
