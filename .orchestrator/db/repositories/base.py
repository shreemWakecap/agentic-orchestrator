"""Base repository class with shared utilities.

This module provides a base class for all repositories that includes:
- Common JSON deserialization patterns
- Safe dynamic query building with column whitelisting
- Shared utility methods

By inheriting from BaseRepository, individual repositories can eliminate
duplicate code and maintain consistent patterns.
"""
from typing import List, Optional, Set, Any, Dict

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

    def __init__(self, db: "Database"):
        """Initialize repository with database connection.

        Args:
            db: Database connection instance
        """
        self.db = db

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
