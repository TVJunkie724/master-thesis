# User-function extension development

User functions are a bounded part of the evaluated Twin scenario, not a plugin
marketplace or general artifact platform.

The canonical Twin interchange may contain allowlisted processor, action and
feedback source plus typed metadata. The validator enforces:

- one supported schema and runtime boundary;
- allowlisted file types and paths;
- archive, source and dependency size limits;
- syntax and entry-point checks;
- secret and unsafe-path rejection;
- exact dependency pins and approved package shapes where dependencies are
  supported; and
- deterministic source and package digests.

Provider adapters wrap validated source in repository-owned runtime packages.
User content cannot choose Terraform modules, provider credentials, resource
names, arbitrary commands or package destinations.

To change the boundary, update the typed Twin schema, validator, package
builder, every relevant provider adapter and the offline contract/negative
tests together. The deployment graph must identify the exact component that
executes the function and the cost/verification evidence it owns.

Do not add general artifact listing, ownership, history, migration, discovery,
legacy import or marketplace behavior. Editing a draft replaces its current
bounded source; a deployed Twin remains immutable.
