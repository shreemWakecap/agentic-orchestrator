"""
Rule Checker for Plan Validation.

Checks plans against coding rules extracted during scouting.
Provides soft-enforcement through warnings, not hard blocks.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.knowledge_store import KnowledgeStore, CodingRule
from db import get_knowledge_repository


@dataclass
class Violation:
    """Represents a coding rule violation in a plan."""
    rule: CodingRule
    severity: str
    description: str
    location: str = ""  # File path or step ID
    suggested_fix: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule.id,
            "category": self.rule.category,
            "rule_text": self.rule.rule,
            "severity": self.severity,
            "description": self.description,
            "location": self.location,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class RuleCheckResult:
    """Result of checking a plan against coding rules."""
    plan_id: str
    violations: list[Violation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed: bool = True

    def add_violation(self, violation: Violation):
        self.violations.append(violation)
        self.warnings.append(f"[{violation.severity}] {violation.description}")
        if violation.severity == "error":
            self.passed = False

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "error" for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        return any(v.severity == "warning" for v in self.violations)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "passed": self.passed,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
        }


class RuleChecker:
    """
    Checks plans against extracted coding rules.

    Usage:
        checker = RuleChecker(project_root)
        result = checker.check_plan(plan)

        if not result.passed:
            for warning in result.warnings:
                print(warning)
    """

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.knowledge_store = KnowledgeStore(self.project_root)
        self._knowledge_repo = get_knowledge_repository()

    def get_rules(self, min_confidence: float = 0.5) -> list[CodingRule]:
        """Get coding rules from the database."""
        rule_dicts = self._knowledge_repo.get_coding_rules(min_confidence=min_confidence)
        return [CodingRule.from_dict(r) for r in rule_dicts]

    def check_plan(self, plan, rules: list[CodingRule] = None) -> RuleCheckResult:
        """
        Check if a plan violates any coding rules.

        Args:
            plan: ParsedPlan object or plan dictionary
            rules: Optional list of rules to check against (fetches from DB if not provided)

        Returns:
            RuleCheckResult with any violations found
        """
        plan_id = self._get_plan_id(plan)
        result = RuleCheckResult(plan_id=plan_id)

        if rules is None:
            rules = self.get_rules()

        if not rules:
            return result

        # Extract plan details for checking
        plan_files = self._extract_plan_files(plan)
        plan_steps = self._extract_plan_steps(plan)
        plan_text = self._extract_plan_text(plan)

        # Check each rule
        for rule in rules:
            violations = self._check_rule(rule, plan_files, plan_steps, plan_text)
            for violation in violations:
                result.add_violation(violation)

        return result

    def check_file_naming(self, file_path: str, rules: list[CodingRule] = None) -> list[Violation]:
        """
        Check if a file path follows naming conventions.

        Args:
            file_path: Path to check
            rules: Rules to check against

        Returns:
            List of violations
        """
        if rules is None:
            rules = self.get_rules()

        violations = []
        naming_rules = [r for r in rules if r.category == "naming"]

        for rule in naming_rules:
            if self._violates_naming_rule(file_path, rule):
                violations.append(Violation(
                    rule=rule,
                    severity=rule.severity,
                    description=f"File '{file_path}' may violate: {rule.rule}",
                    location=file_path,
                    suggested_fix=self._suggest_naming_fix(file_path, rule)
                ))

        return violations

    def _get_plan_id(self, plan) -> str:
        """Extract plan ID from plan object or dict."""
        if hasattr(plan, 'plan_id'):
            return plan.plan_id
        elif isinstance(plan, dict):
            return plan.get('plan_id', 'unknown')
        return 'unknown'

    def _extract_plan_files(self, plan) -> list[str]:
        """Extract file paths mentioned in the plan."""
        files = []

        if hasattr(plan, 'steps'):
            for step in plan.steps:
                if hasattr(step, 'target') and step.target:
                    files.append(step.target)
        elif isinstance(plan, dict):
            for step in plan.get('steps', []):
                if step.get('target'):
                    files.append(step['target'])

        return files

    def _extract_plan_steps(self, plan) -> list[dict]:
        """Extract steps from plan as dictionaries."""
        steps = []

        if hasattr(plan, 'steps'):
            for step in plan.steps:
                steps.append({
                    'id': getattr(step, 'id', ''),
                    'action': getattr(step, 'action', ''),
                    'target': getattr(step, 'target', ''),
                    'description': getattr(step, 'description', ''),
                })
        elif isinstance(plan, dict):
            for step in plan.get('steps', []):
                steps.append(step)

        return steps

    def _extract_plan_text(self, plan) -> str:
        """Extract all text content from plan for keyword matching."""
        text_parts = []

        if hasattr(plan, 'goal'):
            text_parts.append(plan.goal or '')
        if hasattr(plan, 'raw_content'):
            text_parts.append(plan.raw_content or '')
        if hasattr(plan, 'steps'):
            for step in plan.steps:
                if hasattr(step, 'description'):
                    text_parts.append(step.description or '')
        elif isinstance(plan, dict):
            text_parts.append(plan.get('goal', ''))
            text_parts.append(plan.get('raw_content', ''))
            for step in plan.get('steps', []):
                text_parts.append(step.get('description', ''))

        return '\n'.join(text_parts)

    def _check_rule(
        self,
        rule: CodingRule,
        plan_files: list[str],
        plan_steps: list[dict],
        plan_text: str
    ) -> list[Violation]:
        """Check a single rule against plan details."""
        violations = []

        if rule.category == "naming":
            for file_path in plan_files:
                if self._violates_naming_rule(file_path, rule):
                    violations.append(Violation(
                        rule=rule,
                        severity=rule.severity,
                        description=f"File '{file_path}' may violate naming rule: {rule.rule}",
                        location=file_path,
                        suggested_fix=self._suggest_naming_fix(file_path, rule)
                    ))

        elif rule.category == "structure":
            for step in plan_steps:
                target = step.get('target', '')
                if target and self._violates_structure_rule(target, rule):
                    violations.append(Violation(
                        rule=rule,
                        severity=rule.severity,
                        description=f"File placement '{target}' may violate: {rule.rule}",
                        location=target,
                        suggested_fix=f"Consider placing file according to: {rule.rule}"
                    ))

        elif rule.category == "patterns":
            # Check if plan mentions patterns that violate rules
            if self._violates_pattern_rule(plan_text, rule):
                violations.append(Violation(
                    rule=rule,
                    severity=rule.severity,
                    description=f"Plan may violate pattern: {rule.rule}",
                    suggested_fix=f"Review and apply: {rule.rule}"
                ))

        return violations

    def _violates_naming_rule(self, file_path: str, rule: CodingRule) -> bool:
        """Check if file path violates a naming rule."""
        rule_lower = rule.rule.lower()
        path = Path(file_path)
        file_name = path.stem  # Without extension

        # Check for snake_case rule
        if "snake_case" in rule_lower:
            if file_path.endswith('.py') and not self._is_snake_case(file_name):
                return True

        # Check for PascalCase rule
        if "pascalcase" in rule_lower or "pascal case" in rule_lower:
            if (file_path.endswith('.tsx') or file_path.endswith('.jsx')) and \
               file_name[0].islower() and '_' not in file_name:
                return True

        # Check for specific naming patterns from examples
        for example in rule.examples:
            if "(bad)" in example.lower():
                # Extract the bad pattern
                bad_pattern = example.split("(bad)")[0].strip()
                if bad_pattern and bad_pattern.lower() in file_name.lower():
                    return True

        return False

    def _violates_structure_rule(self, file_path: str, rule: CodingRule) -> bool:
        """Check if file placement violates a structure rule."""
        rule_lower = rule.rule.lower()

        # Extract directory expectations from rule
        # e.g., "API routes go in routes/ directory"
        directory_patterns = [
            (r"routes?\s+(?:go\s+)?in\s+(\w+/?)", "routes"),
            (r"services?\s+(?:go\s+)?in\s+(\w+/?)", "services"),
            (r"models?\s+(?:go\s+)?in\s+(\w+/?)", "models"),
            (r"tests?\s+(?:go\s+)?in\s+(\w+/?)", "tests"),
        ]

        for pattern, file_type in directory_patterns:
            match = re.search(pattern, rule_lower)
            if match:
                expected_dir = match.group(1).rstrip('/')
                # Check if the file should be in this directory but isn't
                if file_type in file_path.lower() and expected_dir not in file_path:
                    return True

        return False

    def _violates_pattern_rule(self, plan_text: str, rule: CodingRule) -> bool:
        """Check if plan text violates a pattern rule."""
        # Simple heuristic: check if bad examples appear in plan
        for example in rule.examples:
            if "(bad)" in example.lower():
                bad_pattern = example.split("(bad)")[0].strip()
                if bad_pattern and bad_pattern.lower() in plan_text.lower():
                    return True

        return False

    def _is_snake_case(self, name: str) -> bool:
        """Check if a name follows snake_case convention."""
        # Snake case: lowercase with underscores, no capitals
        if not name:
            return True
        # Allow leading underscores for private/dunder
        stripped = name.lstrip('_')
        if not stripped:
            return True
        return stripped.islower() and not any(c.isupper() for c in name)

    def _suggest_naming_fix(self, file_path: str, rule: CodingRule) -> str:
        """Suggest a fix for naming violations."""
        path = Path(file_path)
        file_name = path.stem
        extension = path.suffix

        if "snake_case" in rule.rule.lower():
            # Convert to snake_case
            snake_name = self._to_snake_case(file_name)
            return f"Consider renaming to: {path.parent / (snake_name + extension)}"

        return f"Review naming according to: {rule.rule}"

    def _to_snake_case(self, name: str) -> str:
        """Convert a name to snake_case."""
        # Insert underscore before uppercase letters and lowercase everything
        result = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        # Remove double underscores
        result = re.sub(r'_+', '_', result)
        return result


def check_plan_rules(plan, project_root: Path = None) -> RuleCheckResult:
    """
    Convenience function to check a plan against coding rules.

    Args:
        plan: Plan to check
        project_root: Optional project root path

    Returns:
        RuleCheckResult with violations
    """
    checker = RuleChecker(project_root)
    return checker.check_plan(plan)


def get_plan_warnings(plan, project_root: Path = None) -> list[str]:
    """
    Convenience function to get warning strings for a plan.

    Args:
        plan: Plan to check
        project_root: Optional project root path

    Returns:
        List of warning strings
    """
    result = check_plan_rules(plan, project_root)
    return result.warnings
