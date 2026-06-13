# deploy/lab-range/main.tf — per-learner EPHEMERAL pentest range (CORE 4).
#
# Terraform provisions an ISOLATED, internal-only Docker network with vulnerable
# targets and a maybot_agent (the attacker box) per learner. Spin it up for a
# graduation lab, then `terraform destroy` to reclaim it — nothing persists.
#
#   terraform init
#   terraform apply -var="learner=scholar" -var="range_id=rng-123"
#   ...run the lab; the agent posts a verified execution proof...
#   terraform destroy -var="learner=scholar" -var="range_id=rng-123"
#
# !!! Run on an ISOLATED host. The targets are intentionally vulnerable. The
# network below is `internal = true` (NO egress to the host LAN or internet). !!!
# For stronger isolation, run the Docker daemon under a Kata/Firecracker runtime
# (see docs/REAL_LABS.md) so each container is a lightweight VM.

terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

variable "learner"  { type = string,  default = "scholar" }
variable "range_id" { type = string,  default = "adhoc" }

locals {
  name = "maybot-lab-${var.learner}-${var.range_id}"
}

# Internal-only lab network: no egress. This is the containment boundary.
resource "docker_network" "lab" {
  name     = local.name
  internal = true
  driver   = "bridge"
}

# --- vulnerable targets (the "network" the learner attacks) ---
resource "docker_image" "juice" { name = "bkimminich/juice-shop:latest" }
resource "docker_container" "web" {
  name     = "${local.name}-web"
  image    = docker_image.juice.image_id
  networks_advanced { name = docker_network.lab.name }
  must_run = true
}

resource "docker_image" "dvwa" { name = "vulnerables/web-dvwa:latest" }
resource "docker_container" "app" {
  name     = "${local.name}-app"
  image    = docker_image.dvwa.image_id
  networks_advanced { name = docker_network.lab.name }
  must_run = true
}

# --- the attacker box: a maybot_agent INSIDE the isolated network ---
# It runs the allow-listed pentest tools against the targets above (and ONLY
# them — the network has no egress) and reports a verified execution proof back
# to the control center. Build an image with the toolkit (see docs/REAL_LABS.md).
resource "docker_container" "attacker" {
  name     = "${local.name}-attacker"
  image    = "maybot/lab-attacker:latest" # Kali-based + maybot_agent + toolkit
  networks_advanced { name = docker_network.lab.name }
  env = [
    "MAYBOT_AGENT_NAME=lab-attacker-${var.learner}",
    "MAYBOT_LAB_RANGE=${var.range_id}",
  ]
  must_run = true
}

output "network"  { value = docker_network.lab.name }
output "attacker" { value = docker_container.attacker.name }
