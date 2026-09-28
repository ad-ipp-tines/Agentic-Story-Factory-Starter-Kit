# terraform/stories.tf — one tines_story per managed slug, read from the committed export (DESIGN.md §3.8).
#
# The export in stories/<slug>/story.json is the truth; this file only deploys it. Review still happens on the
# JSON (lint.yml, review.yml, CODEOWNERS, a human merge) — Terraform is an alternative DEPLOY path, never an
# alternative REVIEW path. DEV TEAM ONLY until docs/VERIFY.md #22 is confirmed (see main.tf and README.md).
#
# Per-story facts come from stories/<slug>/story.meta.yaml (retention, tier) and the environment from
# stories/_manifest.yaml, so nothing environment-specific is typed twice.

locals {
  stories = {
    for slug in var.managed_slugs : slug => {
      export_path = "${path.module}/../stories/${slug}/story.json"
      export      = jsondecode(file("${path.module}/../stories/${slug}/story.json"))
      meta        = yamldecode(file("${path.module}/../stories/${slug}/story.meta.yaml"))
      manifest    = local.manifest.stories[slug]
    }
  }
}

resource "tines_story" "managed" {
  for_each = local.stories

  data                   = file(each.value.export_path)                        # the normalised export, byte for byte
  team_id                = local.team_id
  folder_id              = local.folder_id
  change_control_enabled = true                                                # "Enable by default" is the tenant policy; never switched off here
  keep_events_for        = try(each.value.meta.keep_events_for_days, 30) * 86400 # seconds; >= 30 days for tier production (lint keep_events_min_days_prod)
  tags                   = ["stories-as-code", try(each.value.meta.tier, "internal")]

  # Recipients and monitor flags are NOT set here: ship.yml sets them from the manifest, and exports carry
  # recipients cleared (clear_recipients=true). Whether tines_story would overwrite them on apply is VERIFY #22.
  # MCP connections on AI Agent actions are dropped on import and re-created by hand; Terraform does not restore them.

  lifecycle {
    # A story removed from managed_slugs, or a `terraform destroy`, must never delete a story in the tenant.
    prevent_destroy = true

    precondition {
      condition     = !startswith(try(each.value.export.description, ""), "SKELETON")
      error_message = "stories/${each.key}/story.json is still the labelled SKELETON, not an export. Build the story in the dev team and run /tines-export ${each.key} first."
    }
    precondition {
      condition     = try(each.value.meta.name, "") == try(each.value.export.name, "")
      error_message = "stories/${each.key}: story.meta.yaml name must equal story.json name (import matches by name)."
    }
    precondition {
      condition     = local.team_id != 0 && local.folder_id != 0
      error_message = "stories/_manifest.yaml environments.${var.environment}.team_id / folder_id are still 0; set the real ids first."
    }
    precondition {
      condition     = !contains(try(local.env.locked_slugs, []), each.key) || var.environment == "dev"
      error_message = "${each.key} is a locked ops story in ${var.environment}; it changes only through its own change request (policies/never-touch.yml)."
    }
  }
}

output "story_ids" {
  description = "slug => story id in the target team. Commit new ids to stories/_manifest.yaml through a PR, as ship.yml's follow-up PR does."
  value       = { for slug, story in tines_story.managed : slug => story.id }
}
