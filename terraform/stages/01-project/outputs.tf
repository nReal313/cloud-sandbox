output "enabled_project_services" {
  value = sort(keys(google_project_service.required))
}
