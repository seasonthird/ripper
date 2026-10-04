# Domain Enrichment Contract

Read this contract when a deposit includes `domain_profile`, when source code is missing, or when public same-direction practices are used to reconstruct or improve a project.

## Boundary

- Infer direction from the submitted project documents and source files only.
- Do not read, request, or use a resume, JD, target role, career direction, or desired bullet count.
- Treat deterministic keyword matches as candidates. Semantically review high-signal project excerpts, including text extracted from every submitted PDF.
- When the evidence supports several directions, keep each direction with its own confidence and search keywords.
- Search only within `retrieval_request.published_from` through `published_to`; prefer attributable public sources from domestic Chinese internet organizations of large, medium, and small sizes.
- Never invent a publication date, source, company scale, or implementation detail. Missing public coverage is a reported gap.

## `market-practices.json`

Use this minimum structure:

```json
{
  "profile_id": "domain_...",
  "project_direction_candidates": [
    {
      "name": "任务调度与工作流编排",
      "confidence": "high",
      "project_source_refs": ["/absolute/submitted/path/design.md"],
      "rationale": "DAG、心跳与重试机制直接支持该方向",
      "search_keywords": ["任务调度", "DAG", "心跳租约"]
    }
  ],
  "sources": [
    {
      "id": "source_1",
      "title": "来源标题",
      "url": "https://...",
      "published_at": "YYYY-MM-DD",
      "geography": "CN",
      "organization_size": "large"
    }
  ],
  "module_cards": [
    {
      "id": "lease_recovery",
      "name": "租约与失联恢复",
      "basis_source_ids": ["source_1"],
      "historical_fact": false,
      "project_fit": "如何延伸原有机制",
      "compatibility_requirements": ["需要任务状态持久化"],
      "conflicts_with": []
    }
  ],
  "architecture_candidates": [
    {
      "variant": "conservative",
      "module_card_ids": ["lease_recovery"],
      "preserved_terms": ["DAG", "heartbeat"],
      "historical_fact": false,
      "coherence_rationale": "只沿现有控制面扩展失联恢复"
    },
    {
      "variant": "enhanced",
      "module_card_ids": ["lease_recovery", "adaptive_retry"],
      "preserved_terms": ["DAG", "heartbeat"],
      "historical_fact": false,
      "coherence_rationale": "两个模块共用原有状态与错误分类，不引入冲突的控制面"
    }
  ]
}
```

Every `project_source_ref` must exactly match a path in `domain_profile.source_inventory`. Every module card must cite known external source IDs and set `historical_fact` to `false`. Keep at least two uniquely named architecture candidates. A candidate must select one or more module cards, preserve project terminology, explain coherence, and never select cards declared in one another's `conflicts_with`.

Run:

```bash
orchestration validate-domain-knowledge \
  --profile domain-profile.json \
  --knowledge market-practices.json
```

Do not deposit an invalid bundle. Warnings about company-size coverage or locked terms require review and disclosure; do not silence them by fabricating data.

## Evidence Mapping

Map external knowledge separately from historical facts:

```yaml
reconstruction:
  mode: market-informed-reconstruction
  profile_id: domain_...
  architecture_candidates: [conservative, enhanced]
derived_optimizations:
  - module_card_id: lease_recovery
    realization_status: derived
    historical_fact: false
    source_ids: [source_1]
```

Do not copy an external card into a historical claim's `statement`, `verified_results`, or `implemented` evidence. Later export may select one candidate for a scenario and phrase it as a design/reconstruction unless independent project evidence confirms implementation.
