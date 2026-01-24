"""Base repository class with shared utilities.

This module provides a base class for all repositories that includes:
- Common JSON deserialization patterns
- Safe dynamic query building with column whitelisting
- Shared utility methods
- Project scoping for multi-project support

By inheriting from BaseRepository, individual repositories can eliminate
duplicate code and maintain consistent patterns.

For project-scoped data, inherit from ProjectScopedRepository which
automatically filters by the current project context.
"""
from typing import List, Optional, Set, Any, Dict
from contextlib import contextmanager

# Import will be done at runtime to avoid circular imports
# from db.connection import Database


class BaseRepository:
    """Base repository with common utilities to eliminate duplication.

    Subclasses should:
    1. Call super().__init__(db) in their constructor
    2. Define ALLOWED_UPDATE_COLUMNS for safe dynamic updates
    3. Define JSON_FIELDS for automatic deserialization
    """

    # Override in subclasses to define allowed update columns
    ALLOWED_UPDATE_COLUMNS: Set[str] = set()

    # Override in subclasses to define fields that need JSON deserialization
    JSON_FIELDS: List[str] = []

    # Override in subclasses: the SQLAlchemy model class
    model = None

    # Override in subclasses: the table name for raw SQL queries
    table_name: str = None

    def __init__(self, db: "Database" = None):
        """Initialize repository with database connection.

        Args:
            db: Database connection instance (optional for ORM repositories)
        """
        self.db = db
        self._engine = None
        self._session_factory = None

    @contextmanager
    def session(self):
        """Get a database session (ORM style).

        For repositories using SQLAlchemy ORM instead of raw SQL.
        """
        if self.db:
            # Legacy mode: use db.session()
            with self.db.session() as session:
                yield session
        else:
            # New mode: create session directly
            from db.connection import Database
            db = Database()
            with db.session() as session:
                yield session

    def _deserialize_json_fields(
        self, row: Optional[Dict], fields: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Deserialize JSON fields in a database row.

        This eliminates the 58+ duplicate deserialization patterns found
        across repositories.

        Args:
            row: Database row as dict, or None
            fields: List of field names to deserialize. If None, uses self.JSON_FIELDS

        Returns:
            Row with JSON fields deserialized, or None if input was None
        """
        if row is None:
            return None

        fields = fields or self.JSON_FIELDS

        for field in fields:
            json_key = f"{field}_json"
            if json_key in row:
                row[field] = self.db.from_json(row.get(json_key), [])

        return row

    def _deserialize_rows(
        self, rows: List[Dict], fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """Deserialize JSON fields in multiple database rows.

        Args:
            rows: List of database rows
            fields: List of field names to deserialize

        Returns:
            List of rows with JSON fields deserialized
        """
        return [self._deserialize_json_fields(row, fields) for row in rows]

    def _build_update_query(
        self,
        table: str,
        key_col: str,
        key_val: Any,
        allowed_columns: Optional[Set[str]] = None,
        **kwargs
    ) -> tuple[str, list]:
        """Build a safe UPDATE query with column whitelisting.

        This prevents SQL injection via column names by only allowing
        updates to pre-defined columns.

        Args:
            table: Table name to update
            key_col: Primary key column name
            key_val: Primary key value
            allowed_columns: Set of allowed column names (defaults to ALLOWED_UPDATE_COLUMNS)
            **kwargs: Column name -> value pairs to update

        Returns:
            Tuple of (query string, list of values)

        Raises:
            ValueError: If no valid columns are provided
        """
        allowed = allowed_columns or self.ALLOWED_UPDATE_COLUMNS

        # Filter to allowed columns only
        valid_kwargs = {k: v for k, v in kwargs.items() if k in allowed}

        if not valid_kwargs:
            raise ValueError(f"No valid columns to update. Allowed: {allowed}")

        set_clause = ", ".join(f"{k} = ?" for k in valid_kwargs.keys())
        values = list(valid_kwargs.values()) + [key_val]
        query = f"UPDATE {table} SET {set_clause} WHERE {key_col} = ?"

        return query, values

    def _build_insert_query(
        self, table: str, data: Dict[str, Any]
    ) -> tuple[str, list]:
        """Build an INSERT query from a dictionary.

        Args:
            table: Table name
            data: Column name -> value pairs

        Returns:
            Tuple of (query string, list of values)
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        values = list(data.values())
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        return query, values

    def _prepare_json_fields(
        self, data: Dict[str, Any], fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Prepare data dict by serializing specified fields to JSON.

        Converts fields like 'completed_steps' to 'completed_steps_json' with
        JSON serialized value.

        Args:
            data: Input data dictionary
            fields: Fields to serialize (defaults to JSON_FIELDS)

        Returns:
            New dict with JSON-serialized fields
        """
        fields = fields or self.JSON_FIELDS
        result = dict(data)

        for field in fields:
            if field in result:
                value = result.pop(field)
                result[f"{field}_json"] = self.db.to_json(value)

        return result


class ProjectScopedRepository(BaseRepository):
    """
    Base repository for project-scoped data.

    This repository automatically filters all queries by the current
    project context. It's designed for tables that have a project_id
    foreign key.

    Subclasses should:
    1. Define the model class
    2. Define the table_name
    3. Optionally override methods for custom behavior

    Example:
        class MyRepository(ProjectScopedRepository):
            model = MyModel
            table_name = "my_table"

            def get_all(self):
                # This automatically filters by project_id
                return self._query_all()
    """

    # Whether project context is required for operations
    require_project_context: bool = True

    def _get_project_id(self) -> Optional[str]:
        """
        Get the current project ID from context.

        Returns:
            The current project ID or None.

        Raises:
            ProjectContextError: If project context is required but not set.
        """
        from db.project_context import project_context, require_project_context as require_ctx

        if self.require_project_context:
            return require_ctx()
        return project_context.get_project_id()

    def _add_project_filter(self, query: str, params: tuple) -> tuple:
        """
        Add project_id filter to a raw SQL query.

        Args:
            query: The SQL query
            params: Query parameters

        Returns:
            Tuple of (modified_query, modified_params)
        """
        project_id = self._get_project_id()
        if not project_id:
            return query, params

        # Check if WHERE clause exists
        if "WHERE" in query.upper():
            # Add to existing WHERE clause
            modified_query = query.replace("WHERE", "WHERE project_id = ? AND", 1)
        else:
            # Find position to insert WHERE (before ORDER BY, LIMIT, etc.)
            insert_pos = len(query)
            for keyword in ["ORDER BY", "LIMIT", "GROUP BY", "HAVING"]:
                pos = query.upper().find(keyword)
                if pos != -1 and pos < insert_pos:
                    insert_pos = pos

            modified_query = query[:insert_pos] + " WHERE project_id = ? " + query[insert_pos:]

        modified_params = (project_id,) + params
        return modified_query, modified_params

    def _query_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """
        Execute query with project filter and return one result.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row as dict or None
        """
        modified_query, modified_params = self._add_project_filter(query, params)
        return self.db.fetchone(modified_query, modified_params)

    def _query_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """
        Execute query with project filter and return all results.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of rows as dicts
        """
        modified_query, modified_params = self._add_project_filter(query, params)
        return self.db.fetchall(modified_query, modified_params)

    def _insert_with_project(self, data: Dict[str, Any]) -> tuple:
        """
        Build an INSERT query that includes project_id.

        Args:
            data: Column name -> value pairs

        Returns:
            Tuple of (query string, list of values)
        """
        project_id = self._get_project_id()
        if project_id:
            data = dict(data)
            data["project_id"] = project_id
        return self._build_insert_query(self.table_name, data)

    def _orm_filter_by_project(self, stmt):
        """
        Add project_id filter to an ORM select statement.

        Args:
            stmt: SQLAlchemy select statement

        Returns:
            Filtered statement
        """
        project_id = self._get_project_id()
        if project_id and self.model and hasattr(self.model, 'project_id'):
            return stmt.where(self.model.project_id == project_id)
        return stmt

    def list_all_for_project(self) -> List[Any]:
        """
        List all entities for the current project.

        Returns:
            List of model instances.
        """
        from sqlalchemy import select

        with self.session() as session:
            stmt = select(self.model)
            stmt = self._orm_filter_by_project(stmt)
            result = session.execute(stmt)
            return list(result.scalars().all())

    def count_for_project(self) -> int:
        """
        Count entities for the current project.

        Returns:
            Number of entities.
        """
        from sqlalchemy import select, func

        with self.session() as session:
            stmt = select(func.count()).select_from(self.model)
            stmt = self._orm_filter_by_project(stmt)
            result = session.execute(stmt)
            return result.scalar() or 0


def get_current_project_id_or_none() -> Optional[str]:
    """
    Get the current project ID if set, otherwise None.

    This is a convenience function for code that needs to check
    project context without raising an error.

    Returns:
        The current project ID or None.
    """
    from db.project_context import project_context
    return project_context.get_project_id()


def require_project_id() -> str:
    """
    Get the current project ID, raising if not set.

    This is a convenience function for code that requires
    a project context.

    Returns:
        The current project ID.

    Raises:
        ProjectContextError: If no project context is set.
    """
    from db.project_context import require_project_context
    return require_project_context()
