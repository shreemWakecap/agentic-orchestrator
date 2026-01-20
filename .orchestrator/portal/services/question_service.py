"""Question service for business logic related to Q&A module."""
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from db import QuestionRepository


@dataclass
class QuestionSummary:
    """Summary of a question for list views."""
    id: str
    question_text: str
    source_type: str
    status: str
    answer_count: int
    created_at: str
    updated_at: Optional[str] = None


@dataclass
class AnswerSummary:
    """Summary of an answer."""
    id: str
    answer_text: str
    source_details: Dict = field(default_factory=dict)
    is_obsolete: bool = False
    created_at: str = ""


@dataclass
class QuestionDetail:
    """Detailed question with answers."""
    id: str
    question_text: str
    source_type: str
    status: str
    answers: List[AnswerSummary] = field(default_factory=list)
    created_at: str = ""
    updated_at: Optional[str] = None


@dataclass
class QAStats:
    """Q&A module statistics."""
    total_questions: int = 0
    pending: int = 0
    answered: int = 0
    obsolete: int = 0
    knowledge_base: int = 0
    code_exploration: int = 0
    total_answers: int = 0
    obsolete_answers: int = 0


class QuestionService:
    """Service for Q&A business logic.

    Encapsulates question and answer data retrieval and transformation
    logic for the portal layer.
    """

    def __init__(self, question_repo: QuestionRepository):
        self.question_repo = question_repo

    async def create_question(
        self,
        question_text: str,
        source_preference: str = "auto",
    ) -> QuestionSummary:
        """Create a new question.

        Args:
            question_text: The question text
            source_preference: Preferred answer source ('knowledge_base', 'code_exploration', 'auto')

        Returns:
            Created question summary
        """
        # Map 'auto' to 'knowledge_base' as default
        source_type = "knowledge_base" if source_preference == "auto" else source_preference

        question_id = self.question_repo.create_question(
            question_text=question_text,
            source_type=source_type,
        )

        question = self.question_repo.get_question(question_id)
        return self._to_question_summary(question)

    async def get_question(self, question_id: str) -> Optional[QuestionDetail]:
        """Get a question with all its answers.

        Args:
            question_id: The question identifier

        Returns:
            Question detail with answers, or None if not found
        """
        question = self.question_repo.get_question_with_answers(question_id)
        if not question:
            return None
        return self._to_question_detail(question)

    async def list_questions(
        self,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict:
        """List questions with pagination.

        Args:
            status: Filter by status
            source_type: Filter by source type
            search: Search in question text
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with questions list and pagination info
        """
        offset = (page - 1) * page_size

        questions = self.question_repo.list_questions(
            status=status,
            source_type=source_type,
            search=search,
            limit=page_size,
            offset=offset,
        )

        total = self.question_repo.count_questions(
            status=status,
            source_type=source_type,
            search=search,
        )

        return {
            "questions": [self._to_question_summary(q) for q in questions],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": offset + len(questions) < total,
        }

    async def update_question(
        self,
        question_id: str,
        question_text: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[QuestionSummary]:
        """Update a question.

        Args:
            question_id: The question identifier
            question_text: New question text
            status: New status

        Returns:
            Updated question summary, or None if not found
        """
        success = self.question_repo.update_question(
            question_id=question_id,
            question_text=question_text,
            status=status,
        )
        if not success:
            return None

        question = self.question_repo.get_question(question_id)
        return self._to_question_summary(question) if question else None

    async def delete_question(self, question_id: str) -> bool:
        """Delete a question and all its answers.

        Args:
            question_id: The question identifier

        Returns:
            True if deleted, False if not found
        """
        return self.question_repo.delete_question(question_id)

    async def get_recent_questions(self, limit: int = 5) -> List[QuestionSummary]:
        """Get recent questions for dashboard.

        Args:
            limit: Maximum number of questions

        Returns:
            List of recent question summaries
        """
        questions = self.question_repo.get_recent_questions(limit=limit)
        return [self._to_question_summary(q) for q in questions]

    # --- Answer Operations ---

    async def create_answer(
        self,
        question_id: str,
        answer_text: str,
        source: str = "manual",
        source_references: Optional[List[str]] = None,
        confidence: Optional[float] = None,
    ) -> Optional[AnswerSummary]:
        """Create an answer for a question.

        Args:
            question_id: Parent question identifier
            answer_text: The answer content
            source: Answer source ('knowledge_base', 'code_exploration', 'manual')
            source_references: References to source files
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            Created answer summary, or None if question not found
        """
        # Verify question exists
        question = self.question_repo.get_question(question_id)
        if not question:
            return None

        source_details = {
            "source": source,
            "references": source_references or [],
            "confidence": confidence,
        }

        answer_id = self.question_repo.create_answer(
            question_id=question_id,
            answer_text=answer_text,
            source_details=source_details,
        )

        answer = self.question_repo.get_answer(answer_id)
        return self._to_answer_summary(answer) if answer else None

    async def get_answer(self, answer_id: str) -> Optional[AnswerSummary]:
        """Get an answer by ID.

        Args:
            answer_id: The answer identifier

        Returns:
            Answer summary, or None if not found
        """
        answer = self.question_repo.get_answer(answer_id)
        return self._to_answer_summary(answer) if answer else None

    async def update_answer(
        self,
        answer_id: str,
        answer_text: Optional[str] = None,
        is_obsolete: Optional[bool] = None,
    ) -> Optional[AnswerSummary]:
        """Update an answer.

        Args:
            answer_id: The answer identifier
            answer_text: New answer text
            is_obsolete: Mark as obsolete

        Returns:
            Updated answer summary, or None if not found
        """
        success = self.question_repo.update_answer(
            answer_id=answer_id,
            answer_text=answer_text,
            is_obsolete=is_obsolete,
        )
        if not success:
            return None

        answer = self.question_repo.get_answer(answer_id)
        return self._to_answer_summary(answer) if answer else None

    async def mark_answer_obsolete(self, answer_id: str) -> Optional[AnswerSummary]:
        """Mark an answer as obsolete.

        Args:
            answer_id: The answer identifier

        Returns:
            Updated answer summary, or None if not found
        """
        return await self.update_answer(answer_id, is_obsolete=True)

    async def delete_answer(self, answer_id: str) -> bool:
        """Delete an answer.

        Args:
            answer_id: The answer identifier

        Returns:
            True if deleted, False if not found
        """
        return self.question_repo.delete_answer(answer_id)

    # --- Statistics ---

    async def get_stats(self) -> QAStats:
        """Get Q&A module statistics.

        Returns:
            QAStats with counts
        """
        stats = self.question_repo.get_stats()
        return QAStats(**stats)

    async def get_questions_for_template(self) -> Dict:
        """Get questions data transformed for template rendering.

        Returns dict with:
            - questions: list of question dicts
            - stats: Q&A statistics
        """
        result = await self.list_questions(page_size=50)
        stats = await self.get_stats()

        return {
            "questions": [self._summary_to_dict(q) for q in result["questions"]],
            "stats": {
                "total": stats.total_questions,
                "pending": stats.pending,
                "answered": stats.answered,
                "knowledge_base": stats.knowledge_base,
                "code_exploration": stats.code_exploration,
            },
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }

    # --- Private Helpers ---

    def _to_question_summary(self, data: Dict) -> QuestionSummary:
        """Convert repository data to QuestionSummary."""
        return QuestionSummary(
            id=data.get("question_id", data.get("id", "")),
            question_text=data.get("question_text", ""),
            source_type=data.get("source_type", "knowledge_base"),
            status=data.get("status", "pending"),
            answer_count=data.get("answer_count", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
        )

    def _to_answer_summary(self, data: Dict) -> AnswerSummary:
        """Convert repository data to AnswerSummary."""
        return AnswerSummary(
            id=data.get("answer_id", data.get("id", "")),
            answer_text=data.get("answer_text", ""),
            source_details=data.get("source_details", {}),
            is_obsolete=data.get("is_obsolete", False),
            created_at=data.get("created_at", ""),
        )

    def _to_question_detail(self, data: Dict) -> QuestionDetail:
        """Convert repository data to QuestionDetail."""
        answers = [
            self._to_answer_summary(a)
            for a in data.get("answers", [])
        ]
        return QuestionDetail(
            id=data.get("question_id", data.get("id", "")),
            question_text=data.get("question_text", ""),
            source_type=data.get("source_type", "knowledge_base"),
            status=data.get("status", "pending"),
            answers=answers,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
        )

    def _summary_to_dict(self, summary: QuestionSummary) -> Dict:
        """Convert QuestionSummary to template-friendly dict."""
        return {
            "id": summary.id,
            "question_text": summary.question_text,
            "source_type": summary.source_type,
            "status": summary.status,
            "answer_count": summary.answer_count,
            "created_at": summary.created_at,
            "updated_at": summary.updated_at,
        }
