# Conflicting architecture decision

The team selected PostgreSQL as the primary knowledge store. Markdown files are generated only as
a presentation layer and must not be treated as the authoritative knowledge source.

Every published claim must retain a reference to the database record and the source document from
which that record was compiled.
