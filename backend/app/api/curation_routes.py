"""
Project Vulcan: Curation Gateway REST Endpoints (REG-01 / REG-02)
Exposes the Human-in-the-Loop Curation Gate:
1. Viewing unvetted candidates crawled from public registries.
2. Drafting internal Git vendoring PRs.
3. Approving candidates into CURATED status with verified internal Git SHAs.
4. Rejecting uncompliant candidates.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

from app.adapters.registry_crawler import (
    CurationCandidateStore,
    CurationGateService,
    RegistryCrawlerAgent,
)
from app.domain.entities import CurationStatus
from app.domain.exceptions import ParameterValidationError, PolicyViolationError
from app.api.routes import container

curation_router = APIRouter(prefix="/curation", tags=["Curation Gate"])

candidate_store = CurationCandidateStore()
curation_service = CurationGateService(candidate_store)
crawler_agent = RegistryCrawlerAgent(candidate_store)


class CrawlRequest(BaseModel):
    tf_count: int = Field(default=10, ge=1, le=50, description="Terraform modules to fetch")
    galaxy_count: int = Field(default=10, ge=1, le=50, description="Ansible Galaxy roles to fetch")


class DraftPRRequest(BaseModel):
    target_internal_repo: str = Field(
        default="git@github.internal.bank.com:automation/catalog-modules.git",
        description="Internal corporate Git repo for vendored code"
    )


class ApproveCandidateRequest(BaseModel):
    approver_id: str = Field(..., description="Corporate ID of the approving platform engineer")
    internal_git_repo: str = Field(..., description="Target internal Git repository URL")
    internal_commit_sha: str = Field(..., pattern=r"^[0-9a-f]{40}$", description="Reviewed 40-character commit SHA")


class RejectCandidateRequest(BaseModel):
    reviewer_id: str = Field(..., description="Corporate ID of the reviewing engineer")
    reason: str = Field(..., description="Reason for rejecting candidate admission")


@curation_router.get("/candidates")
def list_candidates(
    source: Optional[str] = Query(None, description="Filter by source registry (terraform_registry, ansible_galaxy)"),
    status: Optional[str] = Query(None, description="Filter by curation status (CANDIDATE, DRAFTED_PR, CURATED, REJECTED)"),
    search: Optional[str] = Query(None, description="Search query")
):
    """Lists candidates from the public registry candidate store."""
    items = candidate_store.list_all(source=source, status=status, search=search)
    return [
        {
            "id": it.id,
            "identifier": it.identifier,
            "name": it.name,
            "engine": it.engine.value,
            "category": it.category,
            "risk_tier": it.risk_tier.value,
            "curation_status": it.curation_status.value,
            "description": it.description,
            "tags": it.tags,
            "provenance": it.provenance or {}
        }
        for it in items
    ]


@curation_router.post("/crawl")
async def trigger_crawler(req: CrawlRequest):
    """Triggers the registry crawler agent to discover new upstream candidates."""
    new_candidates = await crawler_agent.crawl_registries(
        tf_count=req.tf_count,
        galaxy_count=req.galaxy_count
    )
    return {
        "status": "SUCCESS",
        "crawled_count": len(new_candidates),
        "candidates": [
            {
                "identifier": c.identifier,
                "name": c.name,
                "engine": c.engine.value,
                "license": c.provenance.get("license") if c.provenance else "UNKNOWN",
                "license_compliant": c.provenance.get("license_compliant") if c.provenance else False
            }
            for c in new_candidates
        ]
    }


@curation_router.post("/candidates/{identifier}/draft-pr")
def draft_pr(identifier: str, req: DraftPRRequest):
    """Drafts an internal Git onboarding PR bundle for a candidate."""
    try:
        pr_bundle = curation_service.draft_registration_pr(
            identifier=identifier,
            target_internal_repo=req.target_internal_repo
        )
        return pr_bundle
    except ParameterValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@curation_router.post("/candidates/{identifier}/approve")
def approve_candidate(identifier: str, req: ApproveCandidateRequest):
    """
    Human-in-the-Loop Curation Approval:
    Validates internal Git repo + 40-char commit SHA, promotes candidate to CURATED status,
    and admits the item into Vulcan's active catalog for governed execution.
    """
    try:
        curated_item = curation_service.approve_candidate(
            identifier=identifier,
            approver_id=req.approver_id,
            internal_git_repo=req.internal_git_repo,
            internal_commit_sha=req.internal_commit_sha
        )
        # Register into in-memory active catalog container
        existing_idx = next((i for i, c in enumerate(container.catalog) if c.identifier == curated_item.identifier), None)
        if existing_idx is not None:
            container.catalog[existing_idx] = curated_item
        else:
            container.catalog.append(curated_item)

        return {
            "status": "APPROVED",
            "message": f"Candidate '{identifier}' successfully promoted to CURATED and admitted to catalog.",
            "item": {
                "identifier": curated_item.identifier,
                "name": curated_item.name,
                "curation_status": curated_item.curation_status.value,
                "internal_git_repo": curated_item.git_repo,
                "internal_commit_sha": curated_item.git_commit_sha
            }
        }
    except ParameterValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PolicyViolationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@curation_router.post("/candidates/{identifier}/reject")
def reject_candidate(identifier: str, req: RejectCandidateRequest):
    """Rejects a candidate from catalog admission."""
    try:
        rejected_item = curation_service.reject_candidate(
            identifier=identifier,
            reviewer_id=req.reviewer_id,
            reason=req.reason
        )
        return {
            "status": "REJECTED",
            "message": f"Candidate '{identifier}' rejected: {req.reason}",
            "identifier": rejected_item.identifier,
            "curation_status": rejected_item.curation_status.value
        }
    except ParameterValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
