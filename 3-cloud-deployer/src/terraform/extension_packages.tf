# Immutable extension package evidence.
#
# The secure #113 prerequisite verifies the artifact and its provider package
# before Terraform. Phase 8.3 owns the reviewed catalog-to-resource binding;
# this resource deliberately does not invent provider topology.

resource "terraform_data" "validated_extension_package" {
  for_each = {
    for package in var.validated_extension_packages :
    "${package.slot_id}@${package.slot_version}" => package
  }

  input = {
    slot_id         = each.value.slot_id
    slot_version    = each.value.slot_version
    artifact_id     = each.value.artifact_id
    artifact_digest = each.value.artifact_digest
    package_digest  = each.value.package_digest
    adapter_id      = each.value.adapter_id
    adapter_version = each.value.adapter_version
  }

  lifecycle {
    precondition {
      condition = (
        fileexists(each.value.package_path) &&
        "sha256:${filesha256(each.value.package_path)}" == each.value.package_digest
      )
      error_message = "Validated extension package is missing or its digest drifted."
    }
  }
}
