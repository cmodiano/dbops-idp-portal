# Extensibility Implementation Verification Report

**Date:** 2026-03-16  
**Reference:** [extensibility-remaining-work-state-of-the-art.md](./extensibility-remaining-work-state-of-the-art.md)

---

## Executive Summary

The codebase has **substantially implemented** the extensibility architecture described in the reference document. Most Phase 1–4 items from Epic 83 and a significant portion of Epic 84 (Phase 5) are in place. The implementation aligns with the target vision: backend as source of truth, frontend as thin client, and schema-driven rendering.

---

## 1. Implemented Components (Verified)

### 1.1 Backend Definitions & Registries

| Component | Status | Location |
|-----------|--------|----------|
| `PlatformDefinition` | ✅ Implemented | `idp-portal/django_backend/platforms/definitions.py` |
| `ServiceDefinition` | ✅ Implemented | `idp-portal/django_backend/services/definitions.py` |
| `ServiceOperationDefinition` | ✅ Implemented | Same file — `input_schema`, `output_schema`, `ui_hints` |
| `GateDefinition` | ✅ Implemented | `idp-portal/django_backend/executions/gates/definitions.py` |
| `WorkflowStepDefinition` | ✅ Implemented | `idp-portal/django_backend/capabilities/step_definitions.py` |
| `workflow_step_registry` | ✅ Implemented | Same file — all step types registered |
| `step_handler_registry` | ✅ Implemented | `idp-portal/django_backend/executions/step_handlers/registry.py` (Story 84.1) |
| `gate_registry` | ✅ Implemented | `idp-portal/django_backend/executions/gates/registry.py` |

### 1.2 Capabilities API

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/v1/capabilities/integrations/` | ✅ Implemented | Exposes platforms, services, operations, schemas, labels |
| `GET /api/v1/capabilities/workflow-steps/` | ✅ Implemented | Exposes step types, variants (gates), config_schema, constraints |

### 1.3 Runtime Execution

| Item | Status | Notes |
|------|--------|-------|
| Step type dispatch via registry | ✅ Implemented | `container_workflow_runtime.py` uses `step_handler_registry.get(step_type)` (Story 84.1) |
| No central `match step_type` | ✅ Implemented | Replaced by registry lookup |
| Gate evaluation strategies | ✅ Implemented | `MaintenanceWindowEvaluationStrategy`, manual for approval |

### 1.4 Manual Gate Resolution

| Item | Status | Notes |
|------|--------|-------|
| `gate_registry.is_manual_condition_type()` | ✅ Implemented | Used in `approval_views.py` instead of hardcoding `approval_granted` |
| Delegation to registry | ✅ Implemented | `_is_manual_resolution_condition()` delegates to registry |

### 1.5 Frontend Components

| Component | Status | Notes |
|-----------|--------|-------|
| `SchemaFormRenderer` | ✅ Implemented | `idp-portal/frontend/src/components/shared/SchemaFormRenderer.tsx` |
| `ActionPalette` backend-driven | ✅ Implemented | Special steps from `capabilities?.stepTypes` (Story 84.3 AC3) |
| `StepConfigPanel` titles | ✅ Implemented | `stepTypeTitle` from `capabilities?.stepTypes` (Story 84.3 AC5) |
| `GateStepConfig` schema-driven | ✅ Implemented | Uses `SchemaFormRenderer` + `config_schema` from backend (Story 84-5) |
| `ServiceCallStepConfig` capabilities | ✅ Implemented | Operations from capabilities, `ui_hints`, `input_schema` (Story 83-10, 84-4) |
| `workflowValidation` backend-driven | ✅ Implemented | `required_fields` from `stepTypeCapabilities` (Story 84.3 AC6) |
| `WorkflowStepNode` labels | ✅ Implemented | Labels from `useCapabilities()` (Story 84.3 AC4) |

### 1.6 Removed Legacy Files

| File | Status |
|------|--------|
| `serviceCallConstants.ts` | ✅ Removed (no file found) |
| `integrationHelpers.ts` | ✅ Removed (no file found) |

### 1.7 AAP Exception Reduction

| Item | Status | Notes |
|------|--------|-------|
| WizardStep2Automatisme | ✅ Reduced | Story 84-6: Single `SchemaFormRenderer` for all connectors including AAP |
| AAPTemplateIdRenderer | ✅ Isolated | Used only for `template_id` (external API) via `customRenderers` |

---

## 2. Remaining Work / Gaps

### 2.1 Backend — Minor Coupling to `approval_granted`

| Location | Issue | Severity |
|----------|-------|----------|
| `approval_views.py` L290–310 | Raw SQL filter `OUTPUT...'approval_granted'` for DB query | Low — Documented as intentional for Oracle CLOB indexing; comment says "Ne pas généraliser sans migration" |
| `container_workflow_runtime.py` L1057–1076 | `gate_output['gate_type'] = 'approval' if cond_type == 'approval_granted' else 'maintenance_window'`; `is_approval_gate = any(...c.get('type') == 'approval_granted'...)` | Medium — Could use `gate_registry.get_for_condition_type(cond_type)` to derive display info and approval-specific behavior |

### 2.2 Frontend — Local Labels / Types

| Location | Issue | Severity |
|----------|-------|----------|
| `TimelineStepItem.tsx` L34–41 | Hardcoded `gateType === 'approval'` → 'Approbation', `first === 'approval_granted'` → 'Approbation' | Medium — Should derive from capabilities or gate variants |
| `workflowStepLabels.ts` L44–46 | `step.gate_type === 'approval'` → 'Approbation', else 'Fenêtre maintenance' | Medium — Should derive from capabilities |

### 2.3 Service Forms — Schema-Driven Completeness

| Item | Status |
|------|--------|
| `ServiceCallStepConfig` uses `input_schema` when available | ✅ `hasSchemaProperties` + `SchemaInputMappingEditor` |
| Full schema-driven form for operations | ⚠️ Partial — Key/value editor still used when schema is empty; `SchemaInputMappingEditor` used when schema has properties |

### 2.4 ActionPlatform Legacy

| Item | Status |
|------|--------|
| `ActionPlatform` model / conversions | ⚠️ Still present — Document notes this as Phase 4 / 84-7 work |

---

## 3. Alignment with Document Sections

### 3.1 "État actuel - ce qu'il reste à enlever"

| Section | Document Claim | Verification |
|---------|----------------|--------------|
| A.1 Resolution manuelle gates | Couplage à `approval_granted` | **Partially addressed** — `approval_views` uses `gate_registry.is_manual_condition_type()`; runtime still has some coupling |
| A.2 Dispatch runtime step types | `match step_type` fermé | **Addressed** — `step_handler_registry` used (Story 84.1) |
| A.3 Usage des schemas | Pas complet partout | **Partially addressed** — Schemas exposed and used in GateStepConfig, ServiceCallStepConfig, WizardStep2Automatisme |
| A.4 ActionPlatform legacy | Encore présent | **Confirmed** — Still present |
| B.1 ActionWizard AAP | Exception AAP | **Addressed** — Reduced to minimum (Story 84-6) |
| B.2 GateStepConfig | Rendu conditionnel manuel | **Addressed** — Uses SchemaFormRenderer |
| B.3 Workflow UI types/labels | Listes locales | **Mostly addressed** — ActionPalette, StepConfigPanel, WorkflowStepNode use capabilities; TimelineStepItem and workflowStepLabels still have local mappings |
| B.4 workflowValidation switch | `switch(stepType)` | **Addressed** — Uses `stepTypeCapabilities` for required_fields |
| B.5 SchemaFormRenderer partout | Pas utilisé partout | **Mostly addressed** — Used in GateStepConfig, WizardStep2Automatisme |
| B.6 Palette / panneau | Listes connues | **Addressed** — ActionPalette derives from capabilities; StepConfigPanel derives titles |

### 3.2 Roadmap cible — 9/10 par composant

| Composant | Document Estimate | Verified State |
|-----------|------------------|----------------|
| Plateformes | 8/10 | ~8/10 — AAP reduced, schemas exposed |
| Services | 8/10 | ~8/10 — Schema-driven where schema exists |
| Gates | 6.5/10 | ~7.5/10 — GateStepConfig schema-driven; runtime still has approval_granted coupling |
| Workflow UI | 6.5/10 | ~8/10 — Palette, validation, StepConfigPanel backend-driven; TimelineStepItem and workflowStepLabels have local mappings |
| Runtime | 7/10 | ~8.5/10 — Registry-based dispatch implemented |

---

## 4. Recommendations

1. **TimelineStepItem / workflowStepLabels** — Derive gate display names from capabilities (e.g. `gate_registry` or workflow-step variants) instead of hardcoding `approval` / `maintenance_window`.
2. **container_workflow_runtime** — Use `gate_registry.get_for_condition_type(cond_type)` to derive `gate_type` for display and to detect approval-specific behavior, removing direct `approval_granted` checks.
3. **ActionPlatform** — Proceed with Epic 84-7 to simplify legacy conversions.
4. **ServiceCallStepConfig** — Continue extending schema-driven rendering for operations with richer `input_schema`.

---

## 5. Conclusion

The implementation is **largely aligned** with the extensibility vision. The main architectural goals are met:

- Backend is the source of truth for platforms, services, gates, and step types.
- Capabilities API exposes definitions and schemas.
- Frontend uses capabilities for palette, validation, and most labels.
- Runtime uses a step handler registry instead of a central `match step_type`.
- Manual gate resolution delegates to the gate registry.

Remaining gaps are localized (TimelineStepItem, workflowStepLabels, runtime gate_output mapping) and do not undermine the overall architecture.
