# terraform/main.tf — the OPTIONAL Terraform deploy path (DESIGN.md §3.8).
#
# Not wired to CI. Not on the default pipeline. `terraform apply` is denied in the IDE (.claude/settings.json).
# DEV TEAM ONLY until docs/VERIFY.md #22 is confirmed: how `tines_story` applies to a change-controlled story
# (into a draft, or straight to live) is unverified, and a live write would bypass the draft → change request →
# named approver path that is the only way into production in this repository.
#
# No secrets in this directory, ever:
#   - the provider reads its tenant and key from the environment (TINES_TENANT, TINES_API_KEY), never from a file;
#   - credential values arrive as EPHEMERAL variables and land in write-only arguments (value_wo), so they are
#     never stored in state or shown in a plan;
#   - Resource values (ops_limits) come from a gitignored *.tfvars file (.gitignore: terraform/*.tfvars).
#
# Argument names beyond those DESIGN.md §3.8 names (data, team_id, folder_id, change_control_enabled,
# keep_events_for, tags, value_wo, value_wo_version) are marked VERIFY: read the provider's registry page for the
# pinned version before the first plan.

terraform {
  required_version = ">= 1.11.0" # write-only arguments (value_wo) and ephemeral variables need Terraform 1.11+

  required_providers {
    tines = {
      source  = "tines/tines"
      version = "~> 0.3.0" # registry 0.3.0 (2025-08-01). 0.x may break in minor releases: read the changelog before any bump — VERIFY #22 "provider still 0.3.0"
    }
  }

  # Configure a remote, encrypted, access-controlled backend per organisation (state holds story JSON — no
  # secrets by design, but internal). Never commit state: .gitignore covers terraform/*.tfstate*.
  # backend "<your-backend>" {}
}

# The provider is configured from the environment (DESIGN.md §3.8): TINES_TENANT and TINES_API_KEY.
# VERIFY #22: whether the provider expects this repository's host-prefix form of TINES_TENANT or a full
# https://<your-tenant>.tines.com URL. If it wants the URL, export it in the shell that runs terraform — never in a file.
# The key must be a TEAM-scoped key for the dev team (Editor role), never a personal key.
provider "tines" {}

# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

variable "environment" {
  description = "Which environment in stories/_manifest.yaml to target. Only `dev` is allowed until docs/VERIFY.md #22 is confirmed."
  type        = string
  default     = "dev"

  validation {
    condition     = var.environment == "dev" || var.verify_22_confirmed
    error_message = "Terraform targets the dev team only until docs/VERIFY.md #22 (tines_story on a change-controlled story) is confirmed and verify_22_confirmed is set to true in a reviewed PR."
  }
}

variable "verify_22_confirmed" {
  description = "Set to true only in a reviewed PR that also records the outcome of docs/VERIFY.md #22. Even then, production stays on ship.yml unless the README says otherwise."
  type        = bool
  default     = false
}

variable "managed_slugs" {
  description = "The story slugs this configuration manages — explicit, never 'every folder under stories/'. Each must be in stories/_manifest.yaml and have a real export (not a SKELETON)."
  type        = list(string)
  default     = []
}

variable "manage_ops_limits" {
  description = "Create or update the ops_limits Resource in the target team from var.ops_limits_json."
  type        = bool
  default     = false
}

variable "ops_limits_json" {
  description = "The tenant's ops_limits Resource value as a JSON string (shape: stories/ops-story-health-monitor/resources/ops_limits.example.json). Supplied from a gitignored *.tfvars file; never committed."
  type        = string
  default     = "{}"
}

variable "text_credential_versions" {
  description = "TEXT credentials to manage, as name => version. Bump the version to rotate. Empty by default: credentials are created [BY HAND] with allowed_hosts unless an owner opts in here."
  type        = map(number)
  default     = {}
}

variable "text_credential_values" {
  description = "Credential values as name => value. EPHEMERAL and sensitive: supplied through TF_VAR_text_credential_values in the shell for one run, never written to a file, never stored in state (they only reach value_wo)."
  type        = map(string)
  default     = {}
  sensitive   = true
  ephemeral   = true
}

# --------------------------------------------------------------------------- #
# The environment map — stories/_manifest.yaml is the ONLY place environment differences live
# --------------------------------------------------------------------------- #

locals {
  manifest  = yamldecode(file("${path.module}/../stories/_manifest.yaml"))
  env       = local.manifest.environments[var.environment]
  team_id   = local.env.team_id
  folder_id = local.env.folder_id
}

# --------------------------------------------------------------------------- #
# The ops_limits Resource (value from a tfvar, never committed)
# --------------------------------------------------------------------------- #

resource "tines_resource" "ops_limits" {
  count = var.manage_ops_limits ? 1 : 0

  name    = "ops_limits"          # must match the name every ops story references (<<RESOURCE.ops_limits>>)
  value   = var.ops_limits_json   # argument name VERIFY #22
  team_id = local.team_id         # argument name VERIFY #22

  lifecycle {
    precondition {
      condition     = local.team_id != 0
      error_message = "stories/_manifest.yaml environments.${var.environment}.team_id is still 0; set the real team id first."
    }
    precondition {
      condition     = can(jsondecode(var.ops_limits_json).enabled)
      error_message = "ops_limits_json must be the full ops_limits object (it has no `enabled` key); see stories/ops-story-health-monitor/resources/ops_limits.example.json."
    }
  }
}

# --------------------------------------------------------------------------- #
# TEXT credentials (the only credential type the provider manages) — write-only values
# --------------------------------------------------------------------------- #

resource "tines_credential" "text" {
  for_each = var.text_credential_versions

  name             = each.key                                   # e.g. tines_api_readonly — must equal the name stories reference
  mode             = "TEXT"                                     # argument name and value VERIFY #22
  team_id          = local.team_id                              # argument name VERIFY #22
  value_wo         = var.text_credential_values[each.key]       # write-only: never in state, never in a plan
  value_wo_version = each.value                                 # bump to rotate

  # allowed_hosts and Workbench access (off for pipeline keys) are set in the tenant [BY HAND] unless the pinned
  # provider version exposes them — VERIFY #22. A credential without allowed_hosts is not done.

  lifecycle {
    precondition {
      condition     = local.team_id != 0
      error_message = "stories/_manifest.yaml environments.${var.environment}.team_id is still 0; set the real team id first."
    }
  }
}
