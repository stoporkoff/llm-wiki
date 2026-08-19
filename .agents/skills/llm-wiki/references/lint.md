# Lint and Refresh Workflow

Run `llm-wiki lint` first. Fix broken links, missing metadata, mutated raw sources, and other
deterministic failures before semantic review.

Then inspect the wiki for:

- claims supported only by generated pages;
- conflicting claims that are not labeled;
- stale claims whose source has been superseded;
- entity aliases split across multiple pages;
- orphan pages and missing reciprocal links;
- concepts repeatedly mentioned without a canonical page;
- source pages with evidence that was never integrated;
- synthesis pages whose conclusions no longer follow from active claims.

Semantic lint is review-oriented. Propose changes when evidence is ambiguous; do not manufacture a
resolution. After approved or unambiguous repairs, rebuild index and graph, rerun deterministic
lint, and append a concise `lint` or `refresh` log entry.
