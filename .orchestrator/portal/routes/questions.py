"""Questions & Answers API routes."""
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query

from db import QuestionRepository
from portal.dependencies import get_question_repo
from portal.schemas.requests import (
    CreateQuestionRequest,
    UpdateQuestionRequest,
    CreateAnswerRequest,
    UpdateAnswerRequest,
)
from portal.services.question_service import QuestionService

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _get_question_service(
    question_repo: QuestionRepository = Depends(get_question_repo),
) -> QuestionService:
    """Get question service with injected dependencies."""
    return QuestionService(question_repo)


# --- Question Endpoints ---

@router.get("")
async def list_questions(
    status: Optional[str] = Query(None, description="Filter by status: pending, answered, obsolete"),
    source: Optional[str] = Query(None, description="Filter by source: knowledge_base, code_exploration"),
    search: Optional[str] = Query(None, description="Search in question text"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """List questions with optional filtering and pagination.

    Returns questions sorted by creation date (newest first).
    """
    result = await question_service.list_questions(
        status=status,
        source_type=source,
        search=search,
        page=page,
        page_size=page_size,
    )

    # Convert QuestionSummary objects to dicts
    questions = []
    for q in result["questions"]:
        questions.append({
            "id": q.id,
            "question": q.question_text,
            "source_type": q.source_type,
            "status": q.status,
            "answer_count": q.answer_count,
            "created_at": q.created_at,
            "updated_at": q.updated_at,
        })

    return {
        "questions": questions,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "has_more": result["has_more"],
    }


@router.post("")
async def create_question(
    request: CreateQuestionRequest,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Create a new question.

    The question will be queued for processing. An answer will be
    generated from the knowledge base or code exploration based on
    the source preference.
    """
    question = await question_service.create_question(
        question_text=request.question,
        source_preference=request.source_preference or "auto",
    )

    return {
        "id": question.id,
        "question": question.question_text,
        "source_type": question.source_type,
        "status": question.status,
        "created_at": question.created_at,
        "message": "Question created successfully",
    }


@router.get("/stats")
async def get_question_stats(
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Get Q&A module statistics.

    Returns counts by status and source type.
    """
    stats = await question_service.get_stats()
    return {
        "total_questions": stats.total_questions,
        "pending": stats.pending,
        "answered": stats.answered,
        "obsolete": stats.obsolete,
        "by_source": {
            "knowledge_base": stats.knowledge_base,
            "code_exploration": stats.code_exploration,
        },
        "total_answers": stats.total_answers,
        "obsolete_answers": stats.obsolete_answers,
    }


@router.get("/recent")
async def get_recent_questions(
    limit: int = Query(5, ge=1, le=20, description="Maximum number of questions"),
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Get recent questions for dashboard display.

    Returns the most recently created questions.
    """
    questions = await question_service.get_recent_questions(limit=limit)

    return {
        "questions": [
            {
                "id": q.id,
                "question": q.question_text,
                "source_type": q.source_type,
                "status": q.status,
                "answer_count": q.answer_count,
                "created_at": q.created_at,
            }
            for q in questions
        ],
    }


@router.get("/{question_id}")
async def get_question(
    question_id: str,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Get a question with all its answers.

    Returns the question details including all associated answers.
    """
    question = await question_service.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "id": question.id,
        "question": question.question_text,
        "source_type": question.source_type,
        "status": question.status,
        "created_at": question.created_at,
        "updated_at": question.updated_at,
        "answers": [
            {
                "id": a.id,
                "content": a.answer_text,
                "source_details": a.source_details,
                "is_obsolete": a.is_obsolete,
                "created_at": a.created_at,
            }
            for a in question.answers
        ],
    }


@router.put("/{question_id}")
async def update_question(
    question_id: str,
    request: UpdateQuestionRequest,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Update a question.

    Can update the question text or status.
    """
    question = await question_service.update_question(
        question_id=question_id,
        question_text=request.question,
        status=request.status,
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "id": question.id,
        "question": question.question_text,
        "status": question.status,
        "updated_at": question.updated_at,
        "message": "Question updated successfully",
    }


@router.delete("/{question_id}")
async def delete_question(
    question_id: str,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Delete a question and all its answers.

    This action is permanent and cannot be undone.
    """
    success = await question_service.delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "status": "deleted",
        "question_id": question_id,
        "message": "Question and all answers deleted successfully",
    }


# --- Answer Endpoints ---

@router.post("/{question_id}/answers")
async def create_answer(
    question_id: str,
    request: CreateAnswerRequest,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Create an answer for a question.

    Manually add an answer to a question. The question status will
    be updated to 'answered'.
    """
    answer = await question_service.create_answer(
        question_id=question_id,
        answer_text=request.content,
        source=request.source,
        source_references=request.source_references,
        confidence=request.confidence,
    )
    if not answer:
        raise HTTPException(status_code=404, detail="Question not found")

    return {
        "id": answer.id,
        "question_id": question_id,
        "content": answer.answer_text,
        "source_details": answer.source_details,
        "created_at": answer.created_at,
        "message": "Answer created successfully",
    }


@router.get("/answers/{answer_id}")
async def get_answer(
    answer_id: str,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Get an answer by ID.

    Returns the answer details including source information.
    """
    answer = await question_service.get_answer(answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    return {
        "id": answer.id,
        "content": answer.answer_text,
        "source_details": answer.source_details,
        "is_obsolete": answer.is_obsolete,
        "created_at": answer.created_at,
    }


@router.put("/answers/{answer_id}")
async def update_answer(
    answer_id: str,
    request: UpdateAnswerRequest,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Update an answer.

    Can update the answer content or mark it as obsolete.
    """
    answer = await question_service.update_answer(
        answer_id=answer_id,
        answer_text=request.content,
        is_obsolete=request.is_obsolete,
    )
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    return {
        "id": answer.id,
        "content": answer.answer_text,
        "is_obsolete": answer.is_obsolete,
        "message": "Answer updated successfully",
    }


@router.put("/answers/{answer_id}/obsolete")
async def mark_answer_obsolete(
    answer_id: str,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Mark an answer as obsolete/outdated.

    This indicates the answer may no longer be accurate but
    keeps it visible for reference.
    """
    answer = await question_service.mark_answer_obsolete(answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    return {
        "id": answer.id,
        "is_obsolete": True,
        "message": "Answer marked as obsolete",
    }


@router.delete("/answers/{answer_id}")
async def delete_answer(
    answer_id: str,
    question_service: QuestionService = Depends(_get_question_service),
) -> Dict[str, Any]:
    """Delete an answer.

    This action is permanent. If this is the last answer for a question,
    the question status will be updated to 'pending'.
    """
    success = await question_service.delete_answer(answer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Answer not found")

    return {
        "status": "deleted",
        "answer_id": answer_id,
        "message": "Answer deleted successfully",
    }
