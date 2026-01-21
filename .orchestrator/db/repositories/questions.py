"""
Question Repository.

Handles questions and answers CRUD operations for the Q&A module.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database


class QuestionRepository:
    """Repository for question and answer operations."""

    def __init__(self, db: "Database"):
        self.db = db

    # --- Question Operations ---

    def create_question(
        self,
        question_text: str,
        source_type: str = "knowledge_base",
    ) -> str:
        """Create a new question.

        Args:
            question_text: The question text
            source_type: Source type ('knowledge_base' or 'code_exploration')

        Returns:
            The generated question_id
        """
        question_id = f"q-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO questions (question_id, question_text, source_type, status, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
            """, (question_id, question_text, source_type, now, now))

        return question_id

    def get_question(self, question_id: str) -> Optional[Dict]:
        """Get a question by its ID.

        Args:
            question_id: The question identifier

        Returns:
            Question dict or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM questions WHERE question_id = ?",
            (question_id,)
        )
        if not row:
            return None

        # Get answer count
        count_row = self.db.fetchone(
            "SELECT COUNT(*) as count FROM answers WHERE question_id = ?",
            (question_id,)
        )
        answer_count = count_row["count"] if count_row else 0

        return {
            "id": row["question_id"],
            "question_id": row["question_id"],
            "question_text": row["question_text"],
            "source_type": row["source_type"],
            "status": row["status"],
            "answer_count": answer_count,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_question_with_answers(self, question_id: str) -> Optional[Dict]:
        """Get a question with all its answers.

        Args:
            question_id: The question identifier

        Returns:
            Question dict with answers list, or None if not found
        """
        question = self.get_question(question_id)
        if not question:
            return None

        answers = self.get_answers_for_question(question_id)
        question["answers"] = answers
        return question

    def list_questions(
        self,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        """List questions with optional filtering.

        Args:
            status: Filter by status ('pending', 'answered', 'obsolete')
            source_type: Filter by source type
            search: Search in question text
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of question dicts
        """
        conditions = []
        params = []

        if status:
            conditions.append("q.status = ?")
            params.append(status)
        if source_type:
            conditions.append("q.source_type = ?")
            params.append(source_type)
        if search:
            conditions.append("q.question_text LIKE ?")
            params.append(f"%{search}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT q.*,
                   (SELECT COUNT(*) FROM answers a WHERE a.question_id = q.question_id) as answer_count
            FROM questions q
            WHERE {where_clause}
            ORDER BY q.created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = self.db.fetchall(query, tuple(params))
        return [
            {
                "id": row["question_id"],
                "question_id": row["question_id"],
                "question_text": row["question_text"],
                "source_type": row["source_type"],
                "status": row["status"],
                "answer_count": row["answer_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def count_questions(
        self,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        """Count questions matching filters.

        Args:
            status: Filter by status
            source_type: Filter by source type
            search: Search in question text

        Returns:
            Count of matching questions
        """
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)
        if search:
            conditions.append("question_text LIKE ?")
            params.append(f"%{search}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        row = self.db.fetchone(
            f"SELECT COUNT(*) as count FROM questions WHERE {where_clause}",
            tuple(params)
        )
        return row["count"] if row else 0

    def update_question(
        self,
        question_id: str,
        question_text: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bool:
        """Update a question.

        Args:
            question_id: The question identifier
            question_text: New question text
            status: New status

        Returns:
            True if updated, False if not found
        """
        updates = []
        params = []

        if question_text is not None:
            updates.append("question_text = ?")
            params.append(question_text)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(question_id)

        with self.db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE questions SET {', '.join(updates)} WHERE question_id = ?",
                tuple(params)
            )
            return cursor.rowcount > 0

    def delete_question(self, question_id: str) -> bool:
        """Delete a question and all its answers.

        Args:
            question_id: The question identifier

        Returns:
            True if deleted, False if not found
        """
        with self.db.transaction() as conn:
            # Answers are deleted via CASCADE
            cursor = conn.execute(
                "DELETE FROM questions WHERE question_id = ?",
                (question_id,)
            )
            return cursor.rowcount > 0

    def get_recent_questions(self, limit: int = 5) -> List[Dict]:
        """Get most recent questions for dashboard display.

        Args:
            limit: Maximum number of questions to return

        Returns:
            List of recent question dicts
        """
        return self.list_questions(limit=limit, offset=0)

    # --- Answer Operations ---

    def create_answer(
        self,
        question_id: str,
        answer_text: str,
        source_details: Optional[Dict] = None,
    ) -> str:
        """Create an answer for a question.

        Args:
            question_id: The parent question identifier
            answer_text: The answer content
            source_details: Optional source details (files, references)

        Returns:
            The generated answer_id
        """
        answer_id = f"a-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO answers (answer_id, question_id, answer_text, source_details_json, is_obsolete, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
            """, (
                answer_id,
                question_id,
                answer_text,
                self.db.to_json(source_details) if source_details else None,
                now
            ))

            # Update question status to answered and update timestamp
            conn.execute("""
                UPDATE questions SET status = 'answered', updated_at = ? WHERE question_id = ?
            """, (now, question_id))

        return answer_id

    def get_answer(self, answer_id: str) -> Optional[Dict]:
        """Get an answer by its ID.

        Args:
            answer_id: The answer identifier

        Returns:
            Answer dict or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM answers WHERE answer_id = ?",
            (answer_id,)
        )
        if not row:
            return None

        return {
            "id": row["answer_id"],
            "answer_id": row["answer_id"],
            "question_id": row["question_id"],
            "answer_text": row["answer_text"],
            "source_details": self.db.from_json(row["source_details_json"], {}),
            "is_obsolete": bool(row["is_obsolete"]),
            "created_at": row["created_at"],
        }

    def get_answers_for_question(self, question_id: str) -> List[Dict]:
        """Get all answers for a question.

        Args:
            question_id: The question identifier

        Returns:
            List of answer dicts
        """
        rows = self.db.fetchall(
            "SELECT * FROM answers WHERE question_id = ? ORDER BY created_at DESC",
            (question_id,)
        )
        return [
            {
                "id": row["answer_id"],
                "answer_id": row["answer_id"],
                "question_id": row["question_id"],
                "answer_text": row["answer_text"],
                "source_details": self.db.from_json(row["source_details_json"], {}),
                "is_obsolete": bool(row["is_obsolete"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def update_answer(
        self,
        answer_id: str,
        answer_text: Optional[str] = None,
        is_obsolete: Optional[bool] = None,
    ) -> bool:
        """Update an answer.

        Args:
            answer_id: The answer identifier
            answer_text: New answer text
            is_obsolete: Mark as obsolete

        Returns:
            True if updated, False if not found
        """
        updates = []
        params = []

        if answer_text is not None:
            updates.append("answer_text = ?")
            params.append(answer_text)
        if is_obsolete is not None:
            updates.append("is_obsolete = ?")
            params.append(1 if is_obsolete else 0)

        if not updates:
            return False

        params.append(answer_id)

        with self.db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE answers SET {', '.join(updates)} WHERE answer_id = ?",
                tuple(params)
            )
            return cursor.rowcount > 0

    def mark_answer_obsolete(self, answer_id: str) -> bool:
        """Mark an answer as obsolete.

        Args:
            answer_id: The answer identifier

        Returns:
            True if marked, False if not found
        """
        return self.update_answer(answer_id, is_obsolete=True)

    def delete_answer(self, answer_id: str) -> bool:
        """Delete an answer.

        Args:
            answer_id: The answer identifier

        Returns:
            True if deleted, False if not found
        """
        # Get the question_id before deleting
        answer = self.get_answer(answer_id)
        if not answer:
            return False

        question_id = answer["question_id"]

        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM answers WHERE answer_id = ?",
                (answer_id,)
            )
            deleted = cursor.rowcount > 0

            if deleted:
                # Check if question still has answers, update status if not
                count_row = conn.execute(
                    "SELECT COUNT(*) as count FROM answers WHERE question_id = ?",
                    (question_id,)
                ).fetchone()

                if count_row and count_row["count"] == 0:
                    conn.execute(
                        "UPDATE questions SET status = 'pending', updated_at = ? WHERE question_id = ?",
                        (datetime.now().isoformat(), question_id)
                    )

            return deleted

    # --- Statistics ---

    def get_stats(self) -> Dict:
        """Get Q&A statistics.

        Returns:
            Dict with counts by status and source
        """
        stats = {
            "total_questions": 0,
            "pending": 0,
            "answered": 0,
            "obsolete": 0,
            "knowledge_base": 0,
            "code_exploration": 0,
            "total_answers": 0,
            "obsolete_answers": 0,
        }

        # Count questions by status
        for status in ["pending", "answered", "obsolete"]:
            row = self.db.fetchone(
                "SELECT COUNT(*) as count FROM questions WHERE status = ?",
                (status,)
            )
            stats[status] = row["count"] if row else 0
            stats["total_questions"] += stats[status]

        # Count by source type
        for source in ["knowledge_base", "code_exploration"]:
            row = self.db.fetchone(
                "SELECT COUNT(*) as count FROM questions WHERE source_type = ?",
                (source,)
            )
            stats[source] = row["count"] if row else 0

        # Count answers
        row = self.db.fetchone("SELECT COUNT(*) as count FROM answers")
        stats["total_answers"] = row["count"] if row else 0

        row = self.db.fetchone("SELECT COUNT(*) as count FROM answers WHERE is_obsolete = true")
        stats["obsolete_answers"] = row["count"] if row else 0

        return stats
