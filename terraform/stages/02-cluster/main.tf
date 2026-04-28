provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_container_cluster" "sandbox" {
  name                     = var.gke_cluster_name
  location                 = var.region
  initial_node_count       = 1
  remove_default_node_pool = true
  deletion_protection      = var.gke_deletion_protection
  networking_mode          = "VPC_NATIVE"

  ip_allocation_policy {}

  addons_config {
    http_load_balancing {
      disabled = false
    }
  }

  gateway_api_config {
    channel = "CHANNEL_STANDARD"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = var.gke_release_channel
  }

  node_config {
    machine_type = var.system_machine_type
    image_type   = "COS_CONTAINERD"
    disk_size_gb = var.system_disk_size_gb
    disk_type    = var.system_disk_type

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

resource "google_container_node_pool" "system" {
  name     = var.system_node_pool_name
  project  = var.project_id
  location = var.region
  cluster  = google_container_cluster.sandbox.name

  initial_node_count = var.system_node_count

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.system_machine_type
    image_type   = "COS_CONTAINERD"
    disk_size_gb = var.system_disk_size_gb
    disk_type    = var.system_disk_type

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

resource "google_container_node_pool" "sandbox" {
  name     = var.sandbox_node_pool_name
  project  = var.project_id
  location = var.region
  cluster  = google_container_cluster.sandbox.name

  initial_node_count = var.sandbox_node_count

  autoscaling {
    min_node_count = var.sandbox_node_min_count
    max_node_count = var.sandbox_node_max_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.sandbox_machine_type
    image_type   = "COS_CONTAINERD"
    disk_size_gb = var.sandbox_disk_size_gb
    disk_type    = var.sandbox_disk_type

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    sandbox_config {
      type = "GVISOR"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}
