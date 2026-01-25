"""
Unit tests for PlanParser.
"""
import pytest

from orchestrator.core.plan_parser import (
    PlanParser,
    ParsedPlan,
    PlanStep,
    PlanPhase,
    StepAction,
    ParseError,
    ParseResult,
    parse_plan,
    validate_plan_coverage,
    validate_integration_completeness,
)


class TestPlanParser:
    """Tests for PlanParser operations."""

    def test_parse_valid_plan(self):
        """Test parsing a complete, valid plan."""
        content = """
GOAL: Implement a user authentication module

CONTEXT:
- Using FastAPI framework
- JWT-based authentication
- User model exists in db/models

STEPS:
1. Create auth service
   ACTION: create
   DO: Implement authentication service with login/logout methods
   IN: db/models/user.py
   OUT: portal/services/auth_service.py
   DONE: Service file exists with login and logout methods
   NEEDS: none

2. Create auth routes
   ACTION: create
   DO: Implement API routes for login and logout
   IN: portal/services/auth_service.py
   OUT: portal/routes/auth.py
   DONE: Routes file exists with POST /login and POST /logout endpoints
   NEEDS: 1

VERIFY:
- Run pytest tests/auth/
- Check endpoints respond correctly
"""
        parser = PlanParser()
        result = parser.parse(content, plan_id="auth-feature")

        assert result.success is True
        assert result.plan is not None
        assert result.plan.plan_id == "auth-feature"
        assert result.plan.goal == "Implement a user authentication module"
        assert len(result.plan.context) == 3
        assert result.plan.total_steps == 2
        assert len(result.plan.verify) == 2

    def test_parse_goal_section(self):
        """Test GOAL extraction from various formats."""
        # Test GOAL: format
        content1 = "GOAL: Create a simple API endpoint\n\nSTEPS:\n1. Do something\n   DO: Do it\n   OUT: file.py"
        result1 = PlanParser().parse(content1)
        assert result1.success is True
        assert result1.plan.goal == "Create a simple API endpoint"

        # Test multiline GOAL
        content2 = """GOAL: Create a complex feature
that spans multiple lines

STEPS:
1. Do something
   DO: Do it
   OUT: file.py
"""
        result2 = PlanParser().parse(content2)
        assert result2.success is True
        assert "Create a complex feature" in result2.plan.goal

    def test_parse_context_section(self):
        """Test CONTEXT bullet extraction."""
        content = """
GOAL: Test context parsing

CONTEXT:
- First context item
- Second context item
- Third context item with details

STEPS:
1. Do something
   DO: Execute the task
   OUT: output.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert len(result.plan.context) == 3
        assert "First context item" in result.plan.context
        assert "Second context item" in result.plan.context
        assert "Third context item with details" in result.plan.context

    def test_parse_context_empty(self):
        """Test parsing plan with no CONTEXT section."""
        content = """
GOAL: Test without context

STEPS:
1. Do something
   DO: Execute the task
   OUT: output.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert result.plan.context == []

    def test_parse_steps_complete(self):
        """Test comprehensive step parsing with all fields."""
        content = """
GOAL: Test step parsing

STEPS:
1. Create the main module
   ACTION: create
   DO: Implement the core functionality
   IN: src/config.py, src/utils.py
   OUT: src/main.py
   DONE: File exists with main function
   NEEDS: none

2. Update the configuration
   ACTION: modify
   DO: Add new configuration options
   IN: src/main.py
   OUT: src/config.py
   DONE: Config has new options
   NEEDS: 1
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert len(result.plan.all_steps) == 2

        step1 = result.plan.all_steps[0]
        assert step1.id == "step-1"
        assert step1.action == StepAction.CREATE
        assert step1.description == "Implement the core functionality"
        assert "src/config.py" in step1.inputs
        assert "src/utils.py" in step1.inputs
        assert step1.target == "src/main.py"
        assert step1.done == "File exists with main function"
        assert step1.needs == []

        step2 = result.plan.all_steps[1]
        assert step2.id == "step-2"
        assert step2.action == StepAction.MODIFY
        assert step2.needs == ["step-1"]

    def test_parse_steps_action_inference(self):
        """Test action inference from title verbs."""
        content = """
GOAL: Test action inference

STEPS:
1. Create a new file
   DO: Create the file
   OUT: new_file.py

2. Modify existing config
   DO: Update config
   OUT: config.py

3. Delete old module
   DO: Remove deprecated code
   OUT: old_module.py

4. Run the tests
   DO: Execute test suite
   OUT: none
"""
        result = PlanParser().parse(content)

        assert result.success is True
        steps = result.plan.all_steps

        assert steps[0].action == StepAction.CREATE
        assert steps[1].action == StepAction.MODIFY
        assert steps[2].action == StepAction.DELETE
        assert steps[3].action == StepAction.RUN

    def test_parse_steps_explicit_action(self):
        """Test explicit ACTION field overrides inference."""
        content = """
GOAL: Test explicit actions

STEPS:
1. Create something but modify instead
   ACTION: modify
   DO: Actually modify
   OUT: file.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert result.plan.all_steps[0].action == StepAction.MODIFY

    def test_parse_verify_section(self):
        """Test VERIFY bullet extraction."""
        content = """
GOAL: Test verify parsing

STEPS:
1. Do something
   DO: Execute task
   OUT: file.py

VERIFY:
- Run pytest
- Check coverage > 80%
- Lint passes
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert len(result.plan.verify) == 3
        assert "Run pytest" in result.plan.verify
        assert "Check coverage > 80%" in result.plan.verify

    def test_parse_empty_content(self):
        """Test parsing empty content returns error."""
        result = PlanParser().parse("")

        assert result.success is False
        assert len(result.errors) > 0
        assert "empty" in result.error_summary().lower()

    def test_parse_missing_goal(self):
        """Test parsing plan without GOAL section."""
        content = """
STEPS:
1. Do something
   DO: Execute task
   OUT: file.py
"""
        result = PlanParser().parse(content)

        assert result.success is False
        assert any("GOAL" in str(e) for e in result.errors)

    def test_parse_missing_steps(self):
        """Test parsing plan without STEPS section."""
        content = """
GOAL: Test without steps

CONTEXT:
- Some context
"""
        result = PlanParser().parse(content)

        assert result.success is False
        assert any("step" in str(e).lower() for e in result.errors)

    def test_parse_step_missing_do(self):
        """Test step without DO instruction generates warning."""
        content = """
GOAL: Test missing DO

STEPS:
1. Just a title
   OUT: file.py
"""
        result = PlanParser().parse(content)

        # Should still succeed as title is used as description
        assert result.success is True

    def test_parse_step_invalid_dependency(self):
        """Test invalid step dependency raises error."""
        content = """
GOAL: Test invalid dependency

STEPS:
1. First step
   DO: Do first
   OUT: first.py
   NEEDS: 99
"""
        result = PlanParser().parse(content)

        assert result.success is False
        assert any("dependency" in str(e).lower() for e in result.errors)

    def test_parse_file_list_with_parenthetical(self):
        """Test parsing file list with parenthetical notes."""
        content = """
GOAL: Test file list parsing

STEPS:
1. Modify files
   DO: Update multiple files
   IN: src/main.py (modified), src/config.py, src/utils.py (new)
   OUT: src/output.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        step = result.plan.all_steps[0]
        assert "src/main.py" in step.inputs
        assert "src/config.py" in step.inputs
        assert "src/utils.py" in step.inputs
        # Parenthetical notes should be stripped
        assert "(modified)" not in " ".join(step.inputs)

    def test_parse_needs_various_formats(self):
        """Test parsing NEEDS field in various formats."""
        content = """
GOAL: Test needs parsing

STEPS:
1. First step
   DO: Do first
   OUT: first.py

2. Second step
   DO: Do second
   OUT: second.py
   NEEDS: 1

3. Third step
   DO: Do third
   OUT: third.py
   NEEDS: step-1, step-2

4. Fourth step
   DO: Do fourth
   OUT: fourth.py
   NEEDS: 1, 2, 3
"""
        result = PlanParser().parse(content)

        assert result.success is True
        steps = result.plan.all_steps

        assert steps[1].needs == ["step-1"]
        assert "step-1" in steps[2].needs
        assert "step-2" in steps[2].needs
        assert len(steps[3].needs) == 3

    def test_parse_plan_id_derived(self):
        """Test plan_id is derived from goal when not provided."""
        content = """
GOAL: Create user authentication module

STEPS:
1. Create module
   DO: Create it
   OUT: auth.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert result.plan.plan_id != ""
        # Should contain keywords from goal
        assert "user" in result.plan.plan_id or "auth" in result.plan.plan_id

    def test_parse_plan_id_explicit(self):
        """Test explicit plan_id is used when provided."""
        content = """
GOAL: Create something

STEPS:
1. Create module
   DO: Create it
   OUT: module.py
"""
        result = PlanParser().parse(content, plan_id="my-custom-id")

        assert result.success is True
        assert result.plan.plan_id == "my-custom-id"

    def test_parse_multiline_do_field(self):
        """Test parsing multiline DO instruction."""
        content = """
GOAL: Test multiline DO

STEPS:
1. Complex step
   ACTION: create
   DO: Implement feature that
includes multiple lines
of instruction
   OUT: feature.py
   DONE: Feature works
"""
        result = PlanParser().parse(content)

        assert result.success is True
        step = result.plan.all_steps[0]
        assert "Implement feature" in step.description

    def test_parsed_plan_total_steps_property(self):
        """Test ParsedPlan.total_steps property."""
        content = """
GOAL: Test properties

STEPS:
1. Step one
   DO: Do one
   OUT: one.py

2. Step two
   DO: Do two
   OUT: two.py

3. Step three
   DO: Do three
   OUT: three.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert result.plan.total_steps == 3

    def test_parsed_plan_all_steps_property(self):
        """Test ParsedPlan.all_steps property."""
        content = """
GOAL: Test all_steps

STEPS:
1. Step one
   DO: Do one
   OUT: one.py

2. Step two
   DO: Do two
   OUT: two.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert len(result.plan.all_steps) == 2
        assert result.plan.all_steps[0].id == "step-1"
        assert result.plan.all_steps[1].id == "step-2"

    def test_parse_result_error_summary(self):
        """Test ParseResult.error_summary method."""
        result = ParseResult(
            success=False,
            errors=[
                ParseError("First error", line=1),
                ParseError("Second error", field="GOAL"),
            ]
        )

        summary = result.error_summary()
        assert "First error" in summary
        assert "Second error" in summary

    def test_parse_whitespace_handling(self):
        """Test parser handles various whitespace correctly."""
        content = """

GOAL:   Lots of whitespace around

CONTEXT:
    -   Indented bullet
-Another bullet

STEPS:

   1.   Spaced step title
      ACTION:  create
      DO:   Spaced instruction
      OUT:   file.py

"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert result.plan.goal.strip() == "Lots of whitespace around"


class TestParsePlanFunction:
    """Tests for the parse_plan convenience function."""

    def test_parse_plan_basic(self):
        """Test parse_plan convenience function."""
        content = """
GOAL: Test convenience function

STEPS:
1. Do something
   DO: Execute task
   OUT: file.py
"""
        result = parse_plan(content)

        assert result.success is True
        assert result.plan is not None

    def test_parse_plan_with_id(self):
        """Test parse_plan with explicit plan_id."""
        content = """
GOAL: Test with ID

STEPS:
1. Do something
   DO: Execute task
   OUT: file.py
"""
        result = parse_plan(content, plan_id="explicit-id")

        assert result.success is True
        assert result.plan.plan_id == "explicit-id"


class TestValidatePlanCoverage:
    """Tests for validate_plan_coverage function."""

    def test_coverage_valid_numbered_requirements(self):
        """Test validation passes when steps match numbered requirements."""
        request = """
        Implement the following:
        1. Create user model
        2. Add API endpoint
        3. Write tests
        """
        plan = ParsedPlan(
            plan_id="test",
            goal="Test",
            phases=[PlanPhase(steps=[
                PlanStep(id="step-1", action=StepAction.CREATE, target="model.py", description="Create model"),
                PlanStep(id="step-2", action=StepAction.CREATE, target="api.py", description="Add endpoint"),
                PlanStep(id="step-3", action=StepAction.CREATE, target="test.py", description="Write tests"),
            ])]
        )

        is_valid, error = validate_plan_coverage(request, plan)
        assert is_valid is True
        assert error == ""

    def test_coverage_insufficient_steps(self):
        """Test validation fails when too few steps for requirements."""
        request = """
        Implement:
        1. Step one
        2. Step two
        3. Step three
        4. Step four
        5. Step five
        """
        plan = ParsedPlan(
            plan_id="test",
            goal="Test",
            phases=[PlanPhase(steps=[
                PlanStep(id="step-1", action=StepAction.CREATE, target="file.py", description="Only one step"),
            ])]
        )

        is_valid, error = validate_plan_coverage(request, plan)
        assert is_valid is False
        assert "requirement" in error.lower()

    def test_coverage_no_numbered_requirements(self):
        """Test validation passes when request has no numbered requirements."""
        request = "Just implement a simple feature without numbers"
        plan = ParsedPlan(
            plan_id="test",
            goal="Test",
            phases=[PlanPhase(steps=[
                PlanStep(id="step-1", action=StepAction.CREATE, target="file.py", description="Do it"),
            ])]
        )

        is_valid, error = validate_plan_coverage(request, plan)
        assert is_valid is True


class TestValidateIntegrationCompleteness:
    """Tests for validate_integration_completeness function."""

    def test_integration_not_new_feature(self):
        """Test validation passes for non-feature requests."""
        request = "Fix the bug in login"
        plan = ParsedPlan(
            plan_id="test",
            goal="Fix bug",
            phases=[PlanPhase(steps=[
                PlanStep(id="step-1", action=StepAction.MODIFY, target="login.py", description="Fix it"),
            ])]
        )

        is_valid, warning = validate_integration_completeness(request, plan)
        assert is_valid is True

    def test_integration_new_feature_complete(self):
        """Test validation passes for complete new feature plan."""
        request = "Implement a new user management module"
        plan = ParsedPlan(
            plan_id="test",
            goal="Implement user management",
            phases=[PlanPhase(steps=[
                PlanStep(id="step-1", action=StepAction.CREATE, target="db/repositories/user_repo.py", description="Create repository"),
                PlanStep(id="step-2", action=StepAction.CREATE, target="portal/services/user_service.py", description="Create service"),
                PlanStep(id="step-3", action=StepAction.CREATE, target="portal/routes/users.py", description="Create router"),
                PlanStep(id="step-4", action=StepAction.MODIFY, target="app.py", description="Include router"),
            ])]
        )

        is_valid, warning = validate_integration_completeness(request, plan)
        assert is_valid is True


class TestStepAction:
    """Tests for StepAction enum."""

    def test_step_action_values(self):
        """Test StepAction enum has expected values."""
        assert StepAction.CREATE.value == "create"
        assert StepAction.MODIFY.value == "modify"
        assert StepAction.DELETE.value == "delete"
        assert StepAction.RUN.value == "run"


class TestPlanStep:
    """Tests for PlanStep model."""

    def test_plan_step_creation(self):
        """Test PlanStep creation with valid data."""
        step = PlanStep(
            id="step-1",
            action=StepAction.CREATE,
            target="test.py",
            description="Create test file",
            done="File exists",
            inputs=["input.py"],
            needs=["step-0"]
        )

        assert step.id == "step-1"
        assert step.action == StepAction.CREATE
        assert step.target == "test.py"
        assert step.description == "Create test file"

    def test_plan_step_empty_description_fails(self):
        """Test PlanStep with empty description raises error."""
        with pytest.raises(ValueError, match="empty"):
            PlanStep(
                id="step-1",
                action=StepAction.CREATE,
                target="test.py",
                description="",
            )

    def test_plan_step_target_none_normalized(self):
        """Test PlanStep target 'none' is normalized to empty string."""
        step = PlanStep(
            id="step-1",
            action=StepAction.RUN,
            target="none",
            description="Run command",
        )

        assert step.target == ""


class TestParseError:
    """Tests for ParseError dataclass."""

    def test_parse_error_str(self):
        """Test ParseError string representation."""
        error = ParseError("Something went wrong", line=42, field="GOAL")
        str_repr = str(error)

        assert "Something went wrong" in str_repr
        assert "42" in str_repr
        assert "GOAL" in str_repr

    def test_parse_error_str_minimal(self):
        """Test ParseError string with only message."""
        error = ParseError("Simple error")
        str_repr = str(error)

        assert str_repr == "Simple error"


class TestEdgeCases:
    """Tests for edge cases and malformed plans."""

    def test_malformed_step_numbering(self):
        """Test handling of non-sequential step numbers."""
        content = """
GOAL: Test step numbers

STEPS:
1. First step
   DO: Do first
   OUT: first.py

5. Fifth step (skipped 2-4)
   DO: Do fifth
   OUT: fifth.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert len(result.plan.all_steps) == 2
        assert result.plan.all_steps[0].id == "step-1"
        assert result.plan.all_steps[1].id == "step-5"

    def test_unicode_content(self):
        """Test handling of unicode characters."""
        content = """
GOAL: Implementar módulo de autenticación

CONTEXT:
- Usar JWT con tokens
- Soporte para múltiples idiomas

STEPS:
1. Créer le service d'authentification
   DO: Implémenter le service
   OUT: auth.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert "autenticación" in result.plan.goal
        assert "múltiples" in result.plan.context[1]

    def test_special_characters_in_paths(self):
        """Test handling of special characters in file paths."""
        content = """
GOAL: Test special paths

STEPS:
1. Create file with special name
   DO: Create it
   OUT: src/components/user-profile/index.tsx
   IN: src/components/base-component/index.tsx
"""
        result = PlanParser().parse(content)

        assert result.success is True
        step = result.plan.all_steps[0]
        assert step.target == "src/components/user-profile/index.tsx"
        assert "src/components/base-component/index.tsx" in step.inputs

    def test_very_long_description(self):
        """Test handling of very long DO description."""
        long_description = "Do " + "something very detailed " * 50
        content = f"""
GOAL: Test long description

STEPS:
1. Long step
   DO: {long_description}
   OUT: file.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert len(result.plan.all_steps[0].description) > 100

    def test_mixed_case_keywords(self):
        """Test handling of mixed case keywords."""
        content = """
goal: Test mixed case

Context:
- Some context

steps:
1. Do something
   action: Create
   do: Create it
   out: file.py
   done: It exists
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert result.plan.goal == "Test mixed case"

    def test_extra_whitespace_in_file_lists(self):
        """Test handling of extra whitespace in file lists."""
        content = """
GOAL: Test whitespace

STEPS:
1. Process files
   DO: Do it
   IN:   file1.py  ,  file2.py  ,   file3.py
   OUT: output.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        step = result.plan.all_steps[0]
        assert len(step.inputs) == 3
        assert "file1.py" in step.inputs
        assert "file2.py" in step.inputs
        assert "file3.py" in step.inputs

    def test_asterisk_bullets(self):
        """Test handling of asterisk bullets in CONTEXT."""
        content = """
GOAL: Test asterisk bullets

CONTEXT:
* First bullet
* Second bullet
* Third bullet

STEPS:
1. Do something
   DO: Do it
   OUT: file.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert len(result.plan.context) == 3

    def test_raw_content_preserved(self):
        """Test that raw content is preserved in parsed plan."""
        content = """
GOAL: Test raw content

STEPS:
1. Do something
   DO: Do it
   OUT: file.py
"""
        result = PlanParser().parse(content)

        assert result.success is True
        assert content.strip() in result.plan.raw_content or "GOAL" in result.plan.raw_content
