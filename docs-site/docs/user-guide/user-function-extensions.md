# User functions

A draft Twin can include bounded source code for the supported processing,
event-action and feedback responsibilities. Use the typed editor or import the
corresponding validated source file.

Before calculation or deployment the application checks the source shape,
entry point, limits, supported dependency metadata and absence of forbidden
paths or secrets. Invalid source remains part of the editable draft but cannot
enter a deployment package.

User functions cannot upload an arbitrary project, select Terraform modules,
execute setup commands or carry cloud credentials. Provider wrappers and
runtime packages are owned by Twin2MultiCloud.

Changing function source on a deployed Twin is not supported. Duplicate or
export/import the Twin under a new name, change the new draft, calculate it and
deploy it independently.
