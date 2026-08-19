# Architecture decision: primary knowledge store

The team selected a file-based Markdown workspace as the primary knowledge store. Immutable raw
sources remain separate from agent-maintained entity, concept, and synthesis pages.

The repository-scoped agent skill owns the compilation workflow. It chooses specialized file
skills when a source format requires them and loads only the instructions relevant to the current
operation.

Every extracted claim must retain an exact source location. Answers must cite the evidence used.
If the available evidence does not support an answer, the agent must say that it does not know.
