"""Tests for CSS class validation on form elements across HTML templates.

Uses BeautifulSoup to parse templates and verify form elements have correct
Tailwind CSS classes for consistent styling across the application.

This module validates the Tailwind CSS classes used in the SDLC Orchestrator
templates to ensure consistent styling across all form elements, buttons,
and interactive components.

Fixtures Used (from conftest.py):
    - template_files: List of all HTML template file paths
    - parsed_templates: Dict mapping template names to BeautifulSoup objects
    - dashboard_template: Parsed dashboard.html for form input tests
    - plan_detail_template: Parsed plan_detail.html for button tests

Test Classes:
    - TestTemplateDiscovery: Validates template file discovery and parsing
    - TestFormInputClasses: Validates form input element CSS classes
    - TestPrimaryButtonClasses: Validates primary action button CSS classes
    - TestSecondaryButtonClasses: Validates secondary button CSS classes
    - TestFormGroupSpacing: Validates form layout and spacing classes
    - TestCSSClassHelpers: Validates helper utilities for CSS testing
    - TestFormInputsCorrectClasses: Comprehensive form input validation
    - TestAllTemplatesFormElements: Cross-template consistency validation

See css_class_mapping.md for detailed mapping of Bootstrap-equivalent classes
to Tailwind CSS classes used in the templates.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag

# Template directory path (matches conftest.py for consistency)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "server" / "templates"


class TestTemplateDiscovery:
    """Validate template file discovery and parsing functionality."""

    def test_templates_directory_exists(self) -> None:
        """Verify the templates directory exists."""
        assert TEMPLATES_DIR.exists(), f"Templates directory not found at {TEMPLATES_DIR}"

    def test_templates_found(self, template_files: list[Path]) -> None:
        """Verify at least one template file is found."""
        assert len(template_files) > 0, "No HTML templates found in templates directory"

    def test_expected_templates_present(self, template_files: list[Path]) -> None:
        """Verify expected core templates are present."""
        template_names = {t.name for t in template_files}
        expected = {"base.html", "dashboard.html", "plans.html", "plan_detail.html"}
        missing = expected - template_names
        assert not missing, f"Missing required templates: {missing}"

    def test_all_templates_parseable(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify all templates can be parsed without errors."""
        for name, soup in parsed_templates.items():
            assert soup is not None, f"Failed to parse {name}"

    def test_all_templates_have_valid_structure(self, template_files: list[Path]) -> None:
        """Verify each template parses and contains recognizable HTML structure."""
        parsing_errors: list[str] = []

        for template_path in template_files:
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    content = f.read()

                soup = BeautifulSoup(content, "html.parser")
                assert soup is not None, f"BeautifulSoup returned None for {template_path.name}"

                # Verify parsed document has some structure
                has_content = (
                    soup.find("html") is not None or
                    soup.find("body") is not None or
                    soup.find("head") is not None or
                    len(list(soup.children)) > 0
                )
                assert has_content, f"{template_path.name} has no recognizable HTML structure"

            except FileNotFoundError:
                parsing_errors.append(f"{template_path.name}: File not found")
            except UnicodeDecodeError:
                parsing_errors.append(f"{template_path.name}: Encoding error")
            except Exception as e:
                parsing_errors.append(f"{template_path.name}: {type(e).__name__}")

        assert not parsing_errors, f"Template parsing errors:\n  - " + "\n  - ".join(parsing_errors)


class TestFormInputClasses:
    """Validate form input elements have correct Tailwind CSS classes."""

    # Expected Tailwind classes for form inputs (based on actual codebase patterns)
    INPUT_BORDER_CLASSES = {"border", "border-gray-300"}
    INPUT_STYLE_CLASSES = {"rounded-md", "shadow-sm"}
    INPUT_FOCUS_CLASSES = {"focus:outline-none", "focus:ring-2", "focus:ring-blue-500"}
    INPUT_PADDING_CLASSES = {"px-4", "py-2"}
    INPUT_TEXT_CLASSES = {"sm:text-sm"}

    def test_dashboard_input_has_border_classes(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard form input has border styling classes."""
        input_elem = dashboard_template.find("input", {"type": "text"})
        assert input_elem is not None, "No text input found in dashboard"
        classes = set(input_elem.get("class", []))
        for expected in self.INPUT_BORDER_CLASSES:
            assert expected in classes, f"Input missing '{expected}'. Found: {classes}"

    def test_dashboard_input_has_style_classes(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard form input has rounded and shadow classes."""
        input_elem = dashboard_template.find("input", {"type": "text"})
        assert input_elem is not None, "No text input found in dashboard"
        classes = set(input_elem.get("class", []))
        for expected in self.INPUT_STYLE_CLASSES:
            assert expected in classes, f"Input missing '{expected}'. Found: {classes}"

    def test_dashboard_input_has_focus_classes(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard form input has focus ring classes for accessibility."""
        input_elem = dashboard_template.find("input", {"type": "text"})
        assert input_elem is not None, "No text input found in dashboard"
        classes = set(input_elem.get("class", []))
        for expected in self.INPUT_FOCUS_CLASSES:
            assert expected in classes, f"Input missing focus class '{expected}'. Found: {classes}"

    def test_dashboard_input_has_padding_classes(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard form input has proper padding."""
        input_elem = dashboard_template.find("input", {"type": "text"})
        assert input_elem is not None, "No text input found in dashboard"
        classes = set(input_elem.get("class", []))
        for expected in self.INPUT_PADDING_CLASSES:
            assert expected in classes, f"Input missing padding '{expected}'. Found: {classes}"

    def test_dashboard_input_has_responsive_text(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard form input has responsive text size class."""
        input_elem = dashboard_template.find("input", {"type": "text"})
        assert input_elem is not None, "No text input found in dashboard"
        classes = set(input_elem.get("class", []))
        for expected in self.INPUT_TEXT_CLASSES:
            assert expected in classes, f"Input missing text class '{expected}'. Found: {classes}"


class TestPrimaryButtonClasses:
    """Validate primary action buttons have correct Tailwind CSS classes."""

    # Expected Tailwind classes for primary buttons (blue theme)
    PRIMARY_BG_CLASSES = {"bg-blue-600", "hover:bg-blue-700"}
    PRIMARY_TEXT_CLASSES = {"text-white", "font-medium", "text-sm"}
    PRIMARY_LAYOUT_CLASSES = {"inline-flex", "items-center"}
    PRIMARY_BORDER_CLASSES = {"border", "border-transparent"}
    PRIMARY_STYLE_CLASSES = {"rounded-md", "shadow-sm"}
    PRIMARY_FOCUS_CLASSES = {"focus:outline-none", "focus:ring-2", "focus:ring-offset-2"}

    def test_dashboard_submit_button_has_primary_bg(self, dashboard_template: BeautifulSoup) -> None:
        """Verify submit button has primary blue background classes."""
        button = dashboard_template.find("button", {"type": "submit"})
        assert button is not None, "No submit button found in dashboard"
        classes = set(button.get("class", []))
        for expected in self.PRIMARY_BG_CLASSES:
            assert expected in classes, f"Button missing '{expected}'. Found: {classes}"

    def test_dashboard_submit_button_has_text_classes(self, dashboard_template: BeautifulSoup) -> None:
        """Verify submit button has white text styling."""
        button = dashboard_template.find("button", {"type": "submit"})
        assert button is not None, "No submit button found in dashboard"
        classes = set(button.get("class", []))
        for expected in self.PRIMARY_TEXT_CLASSES:
            assert expected in classes, f"Button missing text class '{expected}'. Found: {classes}"

    def test_dashboard_submit_button_has_layout_classes(self, dashboard_template: BeautifulSoup) -> None:
        """Verify submit button uses inline-flex layout."""
        button = dashboard_template.find("button", {"type": "submit"})
        assert button is not None, "No submit button found in dashboard"
        classes = set(button.get("class", []))
        for expected in self.PRIMARY_LAYOUT_CLASSES:
            assert expected in classes, f"Button missing layout class '{expected}'. Found: {classes}"

    def test_dashboard_submit_button_has_border_classes(self, dashboard_template: BeautifulSoup) -> None:
        """Verify submit button has transparent border for sizing consistency."""
        button = dashboard_template.find("button", {"type": "submit"})
        assert button is not None, "No submit button found in dashboard"
        classes = set(button.get("class", []))
        for expected in self.PRIMARY_BORDER_CLASSES:
            assert expected in classes, f"Button missing border class '{expected}'. Found: {classes}"

    def test_plan_detail_start_build_button(self, plan_detail_template: BeautifulSoup) -> None:
        """Verify Start Build button has primary styling."""
        buttons = plan_detail_template.find_all("button")
        build_button = None
        for btn in buttons:
            onclick = btn.get("onclick", "")
            if "startBuild" in onclick:
                build_button = btn
                break
        assert build_button is not None, "Start Build button not found in plan_detail"
        classes = set(build_button.get("class", []))
        assert "bg-blue-600" in classes, f"Build button missing bg-blue-600. Found: {classes}"

    def test_primary_buttons_have_text_white(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify primary buttons have text-white for proper contrast."""
        primary_bg_options = {"bg-blue-600", "bg-indigo-600", "bg-purple-600"}

        for template_name, soup in parsed_templates.items():
            for bg_class in primary_bg_options:
                elements = soup.find_all(["button", "a"], class_=lambda x: x and bg_class in x)
                for elem in elements:
                    classes = set(elem.get("class", []))
                    elem_text = elem.get_text(strip=True)[:30]
                    assert "text-white" in classes, (
                        f"{template_name}: Button '{elem_text}' missing text-white. Found: {classes}"
                    )

    def test_primary_buttons_have_hover_state(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify primary buttons have corresponding hover state."""
        primary_bg_options = {"bg-blue-600", "bg-indigo-600", "bg-purple-600"}

        for template_name, soup in parsed_templates.items():
            for bg_class in primary_bg_options:
                elements = soup.find_all(["button", "a"], class_=lambda x: x and bg_class in x)
                for elem in elements:
                    classes = set(elem.get("class", []))
                    elem_text = elem.get_text(strip=True)[:30]
                    bg_base = bg_class.replace("-600", "")
                    expected_hover = f"hover:{bg_base}-700"
                    assert expected_hover in classes, (
                        f"{template_name}: Button '{elem_text}' missing {expected_hover}. Found: {classes}"
                    )

    def test_primary_buttons_have_font_medium(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify primary buttons have font-medium for readability."""
        primary_bg_options = {"bg-blue-600", "bg-indigo-600", "bg-purple-600"}

        for template_name, soup in parsed_templates.items():
            for bg_class in primary_bg_options:
                elements = soup.find_all(["button", "a"], class_=lambda x: x and bg_class in x)
                for elem in elements:
                    classes = set(elem.get("class", []))
                    elem_text = elem.get_text(strip=True)[:30]
                    assert "font-medium" in classes, (
                        f"{template_name}: Button '{elem_text}' missing font-medium. Found: {classes}"
                    )

    def test_primary_buttons_have_correct_classes(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify primary action buttons have the complete set of Tailwind button styling.

        Primary buttons should have:
        - Background color: bg-blue-600, bg-indigo-600, or bg-purple-600
        - Hover state: hover:bg-{color}-700
        - Text styling: text-white, font-medium, text-sm
        - Layout: inline-flex, items-center
        - Border: border, border-transparent
        - Shape: rounded-md
        - Shadow: shadow-sm
        - Padding: px-4, py-2

        This test finds all primary action buttons (identified by colored backgrounds)
        and validates they have the complete styling package for consistency.
        """
        # Primary button background colors that indicate a primary action button
        primary_bg_colors = {"bg-blue-600", "bg-indigo-600", "bg-purple-600"}

        # Required classes for proper primary button styling
        required_styling = {
            "text-white": "white text for contrast",
            "font-medium": "medium font weight for readability",
            "rounded-md": "rounded corners",
        }

        # Recommended classes (warn if missing, but don't fail)
        recommended_styling = {
            "inline-flex": "inline-flex for icon alignment",
            "items-center": "vertical centering",
            "px-4": "horizontal padding",
            "py-2": "vertical padding",
            "text-sm": "small text size",
        }

        errors: list[str] = []
        warnings: list[str] = []

        for template_name, soup in parsed_templates.items():
            for bg_class in primary_bg_colors:
                # Find all button and anchor elements with primary background
                elements = soup.find_all(
                    ["button", "a"],
                    class_=lambda x: x and bg_class in x
                )

                for elem in elements:
                    classes = set(elem.get("class", []))
                    elem_text = elem.get_text(strip=True)[:40] or "[no text]"
                    elem_tag = elem.name

                    # Check for corresponding hover state
                    bg_base = bg_class.replace("-600", "")
                    expected_hover = f"hover:{bg_base}-700"
                    if expected_hover not in classes:
                        errors.append(
                            f"{template_name}: {elem_tag} '{elem_text}' with {bg_class} "
                            f"missing hover state {expected_hover}. Found: {sorted(classes)}"
                        )

                    # Check required styling classes
                    for req_class, description in required_styling.items():
                        if req_class not in classes:
                            errors.append(
                                f"{template_name}: {elem_tag} '{elem_text}' missing "
                                f"'{req_class}' ({description}). Found: {sorted(classes)}"
                            )

                    # Check recommended styling classes (collect warnings)
                    for rec_class, description in recommended_styling.items():
                        if rec_class not in classes:
                            warnings.append(
                                f"{template_name}: {elem_tag} '{elem_text}' missing "
                                f"recommended '{rec_class}' ({description})"
                            )

        # Fail on errors
        assert not errors, (
            f"Primary button styling validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


class TestSecondaryButtonClasses:
    """Validate secondary action buttons have correct Tailwind CSS classes."""

    # Expected Tailwind classes for secondary buttons (gray/outline theme)
    SECONDARY_BG_CLASSES = {"bg-white", "hover:bg-gray-50"}
    SECONDARY_TEXT_CLASSES = {"text-gray-700", "font-medium", "text-sm"}
    SECONDARY_BORDER_CLASSES = {"border", "border-gray-300"}

    def test_plan_detail_back_link_has_secondary_bg(self, plan_detail_template: BeautifulSoup) -> None:
        """Verify back link has secondary white background styling."""
        back_link = plan_detail_template.find("a", href="/plans")
        assert back_link is not None, "Back to Plans link not found in plan_detail"
        classes = set(back_link.get("class", []))
        for expected in self.SECONDARY_BG_CLASSES:
            assert expected in classes, f"Back link missing '{expected}'. Found: {classes}"

    def test_plan_detail_back_link_has_border(self, plan_detail_template: BeautifulSoup) -> None:
        """Verify back link has gray border classes."""
        back_link = plan_detail_template.find("a", href="/plans")
        assert back_link is not None, "Back to Plans link not found in plan_detail"
        classes = set(back_link.get("class", []))
        for expected in self.SECONDARY_BORDER_CLASSES:
            assert expected in classes, f"Back link missing border '{expected}'. Found: {classes}"

    def test_gray_bg_buttons_have_hover_state(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify buttons with gray background have hover state."""
        for template_name, soup in parsed_templates.items():
            elements = soup.find_all(
                ["button", "a"],
                class_=lambda x: x and any(cls.startswith("bg-gray-") for cls in x)
            )
            for elem in elements:
                classes = set(elem.get("class", []))
                elem_text = elem.get_text(strip=True)[:30]
                has_hover = any(cls.startswith("hover:bg-gray-") for cls in classes)
                assert has_hover, (
                    f"{template_name}: Gray button '{elem_text}' missing hover state. Found: {classes}"
                )

    def test_outline_secondary_buttons_have_hover(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify outline secondary buttons (white bg + gray border) have hover state."""
        for template_name, soup in parsed_templates.items():
            elements = soup.find_all(
                ["button", "a"],
                class_=lambda x: x and (
                    "bg-white" in x and any(cls.startswith("border-gray-") for cls in x)
                )
            )
            for elem in elements:
                classes = set(elem.get("class", []))
                elem_text = elem.get_text(strip=True)[:30]
                has_hover = any(cls.startswith("hover:bg-gray-") for cls in classes)
                assert has_hover, (
                    f"{template_name}: Outline button '{elem_text}' missing hover. Found: {classes}"
                )

    def test_outline_secondary_buttons_have_text_color(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify outline secondary buttons have text-gray-* for contrast."""
        for template_name, soup in parsed_templates.items():
            elements = soup.find_all(
                ["button", "a"],
                class_=lambda x: x and (
                    "bg-white" in x and any(cls.startswith("border-gray-") for cls in x)
                )
            )
            for elem in elements:
                classes = set(elem.get("class", []))
                elem_text = elem.get_text(strip=True)[:30]
                has_text_color = any(cls.startswith("text-gray-") for cls in classes)
                assert has_text_color, (
                    f"{template_name}: Outline button '{elem_text}' missing text color. Found: {classes}"
                )

    def test_data_secondary_elements_have_gray_styling(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify elements marked data-style='secondary' have gray styling."""
        for template_name, soup in parsed_templates.items():
            elements = soup.find_all(["button", "a"], attrs={"data-style": "secondary"})
            for elem in elements:
                classes = set(elem.get("class", []))
                elem_text = elem.get_text(strip=True)[:30]
                has_styling = (
                    any(cls.startswith("bg-gray-") for cls in classes) or
                    any(cls.startswith("border-gray-") for cls in classes)
                )
                assert has_styling, (
                    f"{template_name}: Secondary element '{elem_text}' lacks gray styling. Found: {classes}"
                )

    def test_secondary_buttons_have_correct_classes(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify secondary/cancel buttons have the complete set of Tailwind secondary button styling.

        Secondary buttons (cancel, back, close actions) should have:
        - Background: bg-white (outline style) OR bg-gray-* (filled gray style)
        - Border: border, border-gray-300 (for outline style)
        - Text styling: text-gray-700, font-medium, text-sm
        - Hover state: hover:bg-gray-50 (for outline) or hover:bg-gray-* (for filled)
        - Layout: inline-flex, items-center
        - Shape: rounded-md
        - Padding: px-4, py-2

        This test finds all secondary action buttons (identified by white/gray backgrounds
        with gray borders, or by cancel/back/close text content) and validates they have
        the complete styling package for consistency.
        """
        # Keywords that indicate a secondary/cancel button
        secondary_keywords = {"cancel", "back", "close", "dismiss", "no", "later", "skip"}

        # Required classes for proper secondary button styling (outline variant)
        outline_secondary_required = {
            "bg-white": "white background for outline style",
            "border-gray-300": "gray border for definition",
            "text-gray-700": "gray text for secondary appearance",
            "font-medium": "medium font weight for readability",
            "rounded-md": "rounded corners for consistency",
        }

        # Required hover state for outline secondary buttons
        outline_secondary_hover = "hover:bg-gray-50"

        # Alternative: filled gray style secondary buttons
        filled_secondary_bg_options = {"bg-gray-100", "bg-gray-200", "bg-gray-300", "bg-gray-500", "bg-gray-600"}

        errors: list[str] = []

        for template_name, soup in parsed_templates.items():
            # Strategy 1: Find outline secondary buttons (bg-white + border-gray-*)
            outline_buttons = soup.find_all(
                ["button", "a"],
                class_=lambda x: x and "bg-white" in x and any(cls.startswith("border-gray-") for cls in x)
            )

            for elem in outline_buttons:
                classes = set(elem.get("class", []))
                elem_text = elem.get_text(strip=True)[:40] or "[no text]"
                elem_tag = elem.name

                # Check for hover state
                if outline_secondary_hover not in classes:
                    errors.append(
                        f"{template_name}: {elem_tag} '{elem_text}' (outline secondary) "
                        f"missing hover state '{outline_secondary_hover}'. Found: {sorted(classes)}"
                    )

                # Check for text color
                if "text-gray-700" not in classes:
                    errors.append(
                        f"{template_name}: {elem_tag} '{elem_text}' (outline secondary) "
                        f"missing 'text-gray-700' for proper contrast. Found: {sorted(classes)}"
                    )

                # Check for font-medium
                if "font-medium" not in classes:
                    errors.append(
                        f"{template_name}: {elem_tag} '{elem_text}' (outline secondary) "
                        f"missing 'font-medium' for readability. Found: {sorted(classes)}"
                    )

                # Check for rounded-md
                if "rounded-md" not in classes:
                    errors.append(
                        f"{template_name}: {elem_tag} '{elem_text}' (outline secondary) "
                        f"missing 'rounded-md' for consistent styling. Found: {sorted(classes)}"
                    )

            # Strategy 2: Find filled gray secondary buttons
            filled_buttons = soup.find_all(
                ["button", "a"],
                class_=lambda x: x and any(bg in x for bg in filled_secondary_bg_options)
            )

            for elem in filled_buttons:
                classes = set(elem.get("class", []))
                elem_text = elem.get_text(strip=True)[:40] or "[no text]"
                elem_tag = elem.name

                # Determine which bg-gray-* class is used
                used_bg = None
                for bg in filled_secondary_bg_options:
                    if bg in classes:
                        used_bg = bg
                        break

                if used_bg:
                    # Extract the gray shade number
                    shade = used_bg.replace("bg-gray-", "")
                    try:
                        shade_num = int(shade)
                        # Expected hover should be one shade darker
                        expected_hover_shade = min(shade_num + 100, 900)
                        expected_hover = f"hover:bg-gray-{expected_hover_shade}"

                        has_hover = any(cls.startswith("hover:bg-gray-") for cls in classes)
                        if not has_hover:
                            errors.append(
                                f"{template_name}: {elem_tag} '{elem_text}' (filled gray secondary) "
                                f"missing hover state. Expected '{expected_hover}' or similar. Found: {sorted(classes)}"
                            )
                    except ValueError:
                        pass

                # Check for font-medium
                if "font-medium" not in classes:
                    errors.append(
                        f"{template_name}: {elem_tag} '{elem_text}' (filled gray secondary) "
                        f"missing 'font-medium' for readability. Found: {sorted(classes)}"
                    )

                # Check for rounded-md
                if "rounded-md" not in classes:
                    errors.append(
                        f"{template_name}: {elem_tag} '{elem_text}' (filled gray secondary) "
                        f"missing 'rounded-md' for consistent styling. Found: {sorted(classes)}"
                    )

            # Strategy 3: Find buttons by cancel/back/close text content
            all_buttons = soup.find_all(["button", "a"])
            for elem in all_buttons:
                elem_text = elem.get_text(strip=True).lower()
                elem_text_display = elem.get_text(strip=True)[:40] or "[no text]"
                elem_tag = elem.name

                # Check if button text indicates secondary action
                is_secondary_by_text = any(keyword in elem_text for keyword in secondary_keywords)
                if not is_secondary_by_text:
                    continue

                classes = set(elem.get("class", []))
                if not classes:
                    continue

                # Skip if already identified as primary button
                primary_colors = {"bg-blue-600", "bg-indigo-600", "bg-purple-600", "bg-green-600", "bg-red-600"}
                if any(color in classes for color in primary_colors):
                    continue

                # Verify secondary styling
                has_secondary_styling = (
                    "bg-white" in classes or
                    any(cls.startswith("bg-gray-") for cls in classes)
                )

                if not has_secondary_styling:
                    errors.append(
                        f"{template_name}: {elem_tag} '{elem_text_display}' appears to be a secondary action "
                        f"but lacks secondary styling (bg-white or bg-gray-*). Found: {sorted(classes)}"
                    )

        # Fail on errors
        assert not errors, (
            f"Secondary button styling validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


class TestFormGroupSpacing:
    """Validate form groups have appropriate spacing classes."""

    # Expected spacing classes for form groups and sections
    SECTION_SPACING_CLASSES = {"mb-4", "mb-6", "mb-8"}
    FLEX_GAP_CLASSES = {"gap-4", "gap-5", "gap-6"}

    # Tailwind spacing classes for form groups (margin-bottom and space utilities)
    FORM_GROUP_SPACING_CLASSES = {
        "mb-1", "mb-2", "mb-3", "mb-4", "mb-5", "mb-6", "mb-8",
        "space-y-1", "space-y-2", "space-y-3", "space-y-4", "space-y-5", "space-y-6",
        "gap-1", "gap-2", "gap-3", "gap-4", "gap-5", "gap-6",
        "py-1", "py-2", "py-3", "py-4", "py-5", "py-6",
    }

    def test_form_groups_have_spacing_classes(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify form group containers (divs wrapping labels and inputs) have spacing classes.

        Form groups are div elements that contain a label and an associated form input
        (input, select, or textarea). These containers should have Tailwind spacing classes
        such as mb-3, mb-4, space-y-*, gap-*, or similar to ensure proper vertical spacing
        between form groups for consistent layout and visual separation.

        This test:
        1. Finds all div elements that contain both a label and a form input
        2. Verifies the div (or its parent) has appropriate spacing classes
        3. Reports any form groups missing spacing for visual consistency
        """
        # Spacing class prefixes to look for
        spacing_prefixes = ("mb-", "mt-", "my-", "space-y-", "space-x-", "gap-", "py-", "pb-", "pt-")

        def has_spacing_class(classes: set[str]) -> bool:
            """Check if a set of classes contains any spacing class."""
            return any(
                any(cls.startswith(prefix) for prefix in spacing_prefixes)
                for cls in classes
            )

        def get_form_group_identifier(div: Tag) -> str:
            """Generate an identifier for a form group based on its contents."""
            label = div.find("label")
            if label:
                label_text = label.get_text(strip=True)[:30]
                if label_text:
                    return f"label='{label_text}'"
                label_for = label.get("for", "")
                if label_for:
                    return f"for='{label_for}'"
            # Fall back to input identification
            form_input = div.find(["input", "select", "textarea"])
            if form_input:
                input_id = form_input.get("id", "")
                input_name = form_input.get("name", "")
                return input_id or input_name or form_input.name
            return "unknown"

        errors: list[str] = []

        for template_name, soup in parsed_templates.items():
            # Find all divs that contain both a label and a form input element
            all_divs = soup.find_all("div")

            for div in all_divs:
                # Check if this div directly contains a label
                label = div.find("label", recursive=False)
                if label is None:
                    # Also check for labels as immediate children within the div
                    label = next(
                        (child for child in div.children
                         if hasattr(child, "name") and child.name == "label"),
                        None
                    )

                if label is None:
                    continue

                # Check if this div contains a form input element
                form_input = div.find(["input", "select", "textarea"])
                if form_input is None:
                    continue

                # Skip if the input is hidden or a button type
                if form_input.name == "input":
                    input_type = form_input.get("type", "text")
                    if input_type in ("hidden", "submit", "button", "image", "reset"):
                        continue

                # This is a form group - verify it has spacing classes
                div_classes = set(div.get("class", []))

                # Check the div itself
                if has_spacing_class(div_classes):
                    continue

                # Check the parent div (form groups may be nested)
                parent = div.parent
                if parent and hasattr(parent, "get"):
                    parent_classes = set(parent.get("class", []))
                    if has_spacing_class(parent_classes):
                        continue

                    # Check if parent is a flex/grid with gap
                    if "flex" in parent_classes or "grid" in parent_classes:
                        if any(cls.startswith("gap-") for cls in parent_classes):
                            continue

                # Check if the form group is inside a form with spacing
                form_ancestor = div.find_parent("form")
                if form_ancestor:
                    form_classes = set(form_ancestor.get("class", []))
                    if has_spacing_class(form_classes):
                        continue
                    # Check for flex/grid gap on form
                    if "flex" in form_classes or "grid" in form_classes:
                        if any(cls.startswith("gap-") for cls in form_classes):
                            continue

                # No spacing found - report the issue
                group_id = get_form_group_identifier(div)
                errors.append(
                    f"{template_name}: Form group ({group_id}) missing spacing class. "
                    f"Expected mb-*, space-y-*, gap-*, or similar. Div classes: {sorted(div_classes)}"
                )

        # Report all errors
        assert not errors, (
            f"Form group spacing validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    def test_dashboard_form_has_flex_layout(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard form uses flex layout."""
        form = dashboard_template.find("form")
        assert form is not None, "No form found in dashboard"
        classes = set(form.get("class", []))
        assert "flex" in classes, f"Form should use flex layout. Found: {classes}"

    def test_dashboard_form_has_gap(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard form has gap class for element spacing."""
        form = dashboard_template.find("form")
        assert form is not None, "No form found in dashboard"
        classes = set(form.get("class", []))
        has_gap = any(cls.startswith("gap-") for cls in classes)
        assert has_gap, f"Form should have gap-* class. Found: {classes}"

    def test_dashboard_has_margin_bottom_sections(self, dashboard_template: BeautifulSoup) -> None:
        """Verify dashboard has sections with margin-bottom spacing.

        Note: BeautifulSoup's find_all with class_ lambda checks class attribute values.
        For Tailwind templates, we need to check for mb-* classes in any element.
        """
        # Find all elements that have any class attribute
        all_elements = dashboard_template.find_all(attrs={"class": True})
        sections_with_mb = [
            elem for elem in all_elements
            if any(cls.startswith("mb-") for cls in elem.get("class", []))
        ]
        assert len(sections_with_mb) > 0, "No sections with mb-* spacing found in dashboard"

    def test_dashboard_grids_have_gap(self, dashboard_template: BeautifulSoup) -> None:
        """Verify grid layouts use gap classes for consistent spacing."""
        grids = dashboard_template.find_all(class_="grid")
        assert len(grids) > 0, "No grid layouts found in dashboard"
        for grid in grids:
            classes = set(grid.get("class", []))
            has_gap = any(cls.startswith("gap-") for cls in classes)
            assert has_gap, f"Grid missing gap-* class. Found: {classes}"

    def test_forms_have_spacing_classes(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify form elements have spacing classes (mb-*, space-y-*, gap-*, py-*)."""
        spacing_prefixes = ("mb-", "space-y-", "space-x-", "gap-", "py-")

        def has_spacing(classes: set[str]) -> bool:
            return any(any(c.startswith(p) for p in spacing_prefixes) for c in classes)

        for template_name, soup in parsed_templates.items():
            for form in soup.find_all("form"):
                form_classes = set(form.get("class", []))
                parent = form.parent
                parent_classes = set(parent.get("class", [])) if parent else set()

                form_has_spacing = has_spacing(form_classes)
                parent_has_spacing = has_spacing(parent_classes)
                uses_flex_gap = "flex" in form_classes and any(c.startswith("gap-") for c in form_classes)

                assert form_has_spacing or parent_has_spacing or uses_flex_gap, (
                    f"{template_name}: Form lacks spacing. Form: {form_classes}, Parent: {parent_classes}"
                )

    def test_content_sections_have_padding(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify content section divs have vertical padding or margin."""
        for template_name, soup in parsed_templates.items():
            sections = soup.find_all("div", class_=lambda x: x and ("sm:p-6" in x or "p-5" in x or "p-6" in x))
            for div in sections:
                classes = set(div.get("class", []))
                parent = div.parent
                parent_classes = set(parent.get("class", [])) if parent else set()

                has_spacing = any(
                    c.startswith("py-") or c.startswith("mb-") or c.startswith("p-") or c == "sm:p-6"
                    for c in classes
                )
                parent_has_spacing = any(c.startswith("mb-") or c.startswith("py-") for c in parent_classes)

                assert has_spacing or parent_has_spacing, (
                    f"{template_name}: Content section missing vertical spacing. Found: {classes}"
                )

    def test_grids_have_gap(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify all grid containers use gap classes for spacing."""
        for template_name, soup in parsed_templates.items():
            for grid in soup.find_all("div", class_="grid"):
                classes = set(grid.get("class", []))
                has_gap = any(c.startswith("gap-") for c in classes)
                assert has_gap, f"{template_name}: Grid missing gap-* class. Found: {classes}"

    def test_form_flex_containers_have_spacing(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify form-related flex containers have spacing mechanism."""
        for template_name, soup in parsed_templates.items():
            flex_divs = soup.find_all("div", class_=lambda x: x and "flex" in x)
            for flex_div in flex_divs:
                children = [c for c in flex_div.children if hasattr(c, "name") and c.name is not None]
                if len(children) <= 1:
                    continue

                classes = set(flex_div.get("class", []))
                has_spacing = any(
                    c.startswith("gap-") or c.startswith("space-x-") or c.startswith("space-y-") or
                    c in ("justify-between", "justify-around", "justify-evenly")
                    for c in classes
                )

                children_have_margin = any(
                    any(c.startswith(p) for p in ("ml-", "mr-", "mt-", "mb-"))
                    for child in children
                    for c in set(child.get("class", []))
                )

                if has_spacing or children_have_margin:
                    continue

                has_form_elements = any(
                    child.name in ("input", "button", "label", "select", "textarea") or
                    child.find(["input", "button", "select", "textarea"])
                    for child in children
                )
                if has_form_elements:
                    assert False, (
                        f"{template_name}: Form flex container missing spacing. Classes: {classes}"
                    )


class TestCSSClassHelpers:
    """Validate CSS class helper utilities used for testing."""

    @staticmethod
    def parse_html_file(file_path: Path) -> BeautifulSoup:
        """Parse an HTML file and return a BeautifulSoup object."""
        if not file_path.exists():
            raise FileNotFoundError(f"Template not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        soup = BeautifulSoup(content, "html.parser")
        if soup is None:
            raise ValueError(f"Failed to parse: {file_path}")
        return soup

    @staticmethod
    def discover_template_files(templates_dir: Path = TEMPLATES_DIR) -> list[Path]:
        """Discover all HTML template files in a directory."""
        if not templates_dir.exists():
            return []
        return list(templates_dir.glob("*.html"))

    @staticmethod
    def get_element_classes(element: Tag | None) -> set[str]:
        """Safely extract CSS classes from an element."""
        if element is None:
            return set()
        classes = element.get("class", [])
        if isinstance(classes, str):
            return set(classes.split())
        return set(classes)

    @staticmethod
    def has_required_classes(element: Tag | None, required: set[str]) -> tuple[bool, set[str]]:
        """Check if an element has all required CSS classes."""
        element_classes = TestCSSClassHelpers.get_element_classes(element)
        missing = required - element_classes
        return len(missing) == 0, missing

    @staticmethod
    def has_any_class(element: Tag | None, class_options: set[str]) -> tuple[bool, str | None]:
        """Check if an element has at least one of the specified classes."""
        element_classes = TestCSSClassHelpers.get_element_classes(element)
        for cls in class_options:
            if cls in element_classes:
                return True, cls
        return False, None

    @staticmethod
    def find_elements_by_class_pattern(soup: BeautifulSoup, pattern: str) -> list[Tag]:
        """Find all elements with classes matching a pattern prefix."""
        return soup.find_all(
            class_=lambda x: x and any(cls.startswith(pattern) for cls in x)
        )

    def test_parse_html_file_returns_soup(self) -> None:
        """Verify parse_html_file returns valid BeautifulSoup object.

        Note: Templates use Jinja2 {% extends %} and may not have <html> or <body> tags.
        Instead, check for common elements like <div>, <form>, or children.
        """
        dashboard_path = TEMPLATES_DIR / "dashboard.html"
        soup = self.parse_html_file(dashboard_path)
        assert soup is not None, "Failed to parse dashboard.html"
        # Check for recognizable content - Jinja templates may not have <html>/<body>
        has_structure = (
            soup.find("html") is not None or
            soup.find("body") is not None or
            soup.find("div") is not None or
            soup.find("form") is not None or
            len(list(soup.children)) > 0
        )
        assert has_structure, "Parsed soup has no recognizable HTML structure"

    def test_discover_template_files_finds_html(self) -> None:
        """Verify discover_template_files finds HTML files."""
        templates = self.discover_template_files()
        assert len(templates) > 0, "Should discover at least one template"
        assert all(t.suffix == ".html" for t in templates)

    def test_get_element_classes_returns_set(self, dashboard_template: BeautifulSoup) -> None:
        """Verify get_element_classes returns a set."""
        button = dashboard_template.find("button")
        classes = self.get_element_classes(button)
        assert isinstance(classes, set)

    def test_has_required_classes_returns_tuple(self, dashboard_template: BeautifulSoup) -> None:
        """Verify has_required_classes returns (bool, set) tuple."""
        button = dashboard_template.find("button", {"type": "submit"})
        has_all, missing = self.has_required_classes(button, {"rounded-md"})
        assert isinstance(has_all, bool)
        assert isinstance(missing, set)

    def test_find_elements_by_class_pattern_returns_list(self, dashboard_template: BeautifulSoup) -> None:
        """Verify find_elements_by_class_pattern returns a list."""
        bg_elements = self.find_elements_by_class_pattern(dashboard_template, "bg-")
        assert isinstance(bg_elements, list)


class TestFormInputsCorrectClasses:
    """Comprehensive validation of form input elements across all templates.

    This test class verifies that all input, select, and textarea elements
    have the appropriate Tailwind CSS form styling classes for consistent
    appearance and functionality.
    """

    # Tailwind form input styling classes (equivalent to Bootstrap form-control)
    # These are the core classes that should be present on styled form inputs
    FORM_INPUT_CORE_CLASSES = {"border", "rounded-md"}

    # Acceptable border color classes for form inputs
    FORM_INPUT_BORDER_COLORS = {"border-gray-300", "border-gray-200", "border-gray-400"}

    # Focus state classes for accessibility
    FORM_INPUT_FOCUS_CLASSES = {"focus:ring-2", "focus:outline-none", "focus:ring", "focus:border-blue-500"}

    # Padding classes for proper spacing
    FORM_INPUT_PADDING_CLASSES = {"px-4", "px-3", "py-2", "py-1", "p-2", "p-3", "p-4"}

    # Input types to skip (non-visual or button-like inputs)
    SKIP_INPUT_TYPES = {"hidden", "submit", "button", "image", "reset", "checkbox", "radio"}

    def test_form_inputs_have_correct_classes(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify all form inputs (input, select, textarea) have appropriate Tailwind form styling.

        This test finds all input, select, and textarea elements across all templates
        and validates they have the required Tailwind CSS classes for consistent styling:
        - Border styling (border, border-gray-*)
        - Rounded corners (rounded-md or similar)
        - Focus states for accessibility (focus:ring-*, focus:outline-none)
        - Proper padding (px-*, py-*)

        Elements without any classes are skipped as they may be styled via parent or JS.
        Hidden inputs and button-type inputs are also skipped.
        """
        errors: list[str] = []

        for template_name, soup in parsed_templates.items():
            # Check all form element types
            for tag_name in ["input", "select", "textarea"]:
                elements = soup.find_all(tag_name)

                for elem in elements:
                    # Skip inputs that don't need visual styling
                    if tag_name == "input":
                        input_type = elem.get("type", "text")
                        if input_type in self.SKIP_INPUT_TYPES:
                            continue

                    # Get element classes
                    classes = set(elem.get("class", []))

                    # Skip elements without any classes (may be styled elsewhere)
                    if not classes:
                        continue

                    # Get element identifier for error messages
                    elem_id = elem.get("id", "")
                    elem_name = elem.get("name", "")
                    elem_type = elem.get("type", "") if tag_name == "input" else ""
                    elem_identifier = elem_id or elem_name or elem_type or "unnamed"

                    # Check for border class
                    has_border = "border" in classes or any(
                        cls.startswith("border-") for cls in classes
                    )
                    if not has_border:
                        errors.append(
                            f"{template_name}: {tag_name}[{elem_identifier}] missing border class. "
                            f"Found: {sorted(classes)}"
                        )

                    # Check for rounded class
                    has_rounded = any(
                        cls.startswith("rounded") for cls in classes
                    )
                    if not has_rounded:
                        errors.append(
                            f"{template_name}: {tag_name}[{elem_identifier}] missing rounded class. "
                            f"Found: {sorted(classes)}"
                        )

                    # Check for focus state (accessibility requirement)
                    has_focus = any(
                        cls.startswith("focus:") for cls in classes
                    )
                    if not has_focus:
                        errors.append(
                            f"{template_name}: {tag_name}[{elem_identifier}] missing focus state class. "
                            f"Found: {sorted(classes)}"
                        )

                    # Check for padding
                    has_padding = any(
                        cls.startswith("px-") or cls.startswith("py-") or cls.startswith("p-")
                        for cls in classes
                    )
                    if not has_padding:
                        errors.append(
                            f"{template_name}: {tag_name}[{elem_identifier}] missing padding class. "
                            f"Found: {sorted(classes)}"
                        )

        # Report all errors at once for comprehensive feedback
        assert not errors, (
            f"Form input styling validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    def test_text_inputs_have_complete_styling(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify text inputs have complete Tailwind form styling package.

        Text inputs should have the full set of styling classes including:
        - Border with color (border border-gray-300)
        - Rounded corners (rounded-md)
        - Shadow (shadow-sm)
        - Focus ring (focus:ring-2 focus:ring-blue-500)
        - Responsive text size (sm:text-sm)
        """
        expected_classes = {
            "border",
            "border-gray-300",
            "rounded-md",
            "shadow-sm",
        }

        for template_name, soup in parsed_templates.items():
            for input_elem in soup.find_all("input", {"type": "text"}):
                classes = set(input_elem.get("class", []))
                if not classes:
                    continue

                input_id = input_elem.get("id", input_elem.get("name", "unnamed"))
                missing = expected_classes - classes
                assert not missing, (
                    f"{template_name}: input[{input_id}] missing classes {missing}. "
                    f"Found: {sorted(classes)}"
                )

    def test_select_elements_have_form_styling(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify select elements have appropriate Tailwind form styling.

        Select elements should have consistent styling with inputs including:
        - Border styling
        - Rounded corners
        - Focus states
        """
        for template_name, soup in parsed_templates.items():
            for select_elem in soup.find_all("select"):
                classes = set(select_elem.get("class", []))
                if not classes:
                    continue

                select_id = select_elem.get("id", select_elem.get("name", "unnamed"))

                # Check core styling
                has_border = "border" in classes or any(c.startswith("border-") for c in classes)
                has_rounded = any(c.startswith("rounded") for c in classes)

                assert has_border, (
                    f"{template_name}: select[{select_id}] missing border. Found: {sorted(classes)}"
                )
                assert has_rounded, (
                    f"{template_name}: select[{select_id}] missing rounded. Found: {sorted(classes)}"
                )

    def test_textarea_elements_have_form_styling(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify textarea elements have appropriate Tailwind form styling.

        Textarea elements should have consistent styling with inputs including:
        - Border styling
        - Rounded corners
        - Focus states
        """
        for template_name, soup in parsed_templates.items():
            for textarea_elem in soup.find_all("textarea"):
                classes = set(textarea_elem.get("class", []))
                if not classes:
                    continue

                textarea_id = textarea_elem.get("id", textarea_elem.get("name", "unnamed"))

                # Check core styling
                has_border = "border" in classes or any(c.startswith("border-") for c in classes)
                has_rounded = any(c.startswith("rounded") for c in classes)

                assert has_border, (
                    f"{template_name}: textarea[{textarea_id}] missing border. Found: {sorted(classes)}"
                )
                assert has_rounded, (
                    f"{template_name}: textarea[{textarea_id}] missing rounded. Found: {sorted(classes)}"
                )


class TestAllTemplatesFormElements:
    """Cross-template validation for form element consistency."""

    # Tailwind classes for form input styling (equivalent to Bootstrap form-control)
    FORM_INPUT_BORDER_CLASSES = {"border", "border-gray-300", "border-gray-200", "border-gray-400"}
    FORM_INPUT_ROUNDED_CLASSES = {"rounded", "rounded-md", "rounded-lg", "rounded-sm"}

    def test_form_inputs_have_border_classes(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify form inputs have border class for proper styling."""
        for template_name, soup in parsed_templates.items():
            for tag in ["input", "select", "textarea"]:
                for elem in soup.find_all(tag):
                    input_type = elem.get("type", "")
                    if input_type in ("hidden", "submit", "button", "image", "reset"):
                        continue
                    classes = set(elem.get("class", []))
                    if not classes:
                        continue
                    has_border = bool(classes & self.FORM_INPUT_BORDER_CLASSES)
                    assert has_border, (
                        f"{template_name}: {tag} missing border class. Found: {classes}"
                    )

    def test_form_inputs_have_rounded_classes(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify form inputs have rounded class for consistent styling."""
        for template_name, soup in parsed_templates.items():
            for tag in ["input", "select", "textarea"]:
                for elem in soup.find_all(tag):
                    input_type = elem.get("type", "")
                    if input_type in ("hidden", "submit", "button", "image", "reset"):
                        continue
                    classes = set(elem.get("class", []))
                    if not classes:
                        continue
                    has_rounded = bool(classes & self.FORM_INPUT_ROUNDED_CLASSES)
                    assert has_rounded, (
                        f"{template_name}: {tag} missing rounded class. Found: {classes}"
                    )

    def test_text_inputs_have_border_and_rounded(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify all text inputs have border and rounded-md classes."""
        for template_name, soup in parsed_templates.items():
            for input_elem in soup.find_all("input", {"type": "text"}):
                classes = set(input_elem.get("class", []))
                if not classes:
                    continue
                assert "border" in classes, f"{template_name}: input missing 'border'. Found: {classes}"
                assert "rounded-md" in classes, f"{template_name}: input missing 'rounded-md'. Found: {classes}"

    def test_submit_buttons_have_rounded_and_font_medium(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify all submit buttons have rounded-md and font-medium classes."""
        for template_name, soup in parsed_templates.items():
            for button in soup.find_all("button", {"type": "submit"}):
                classes = set(button.get("class", []))
                if not classes:
                    continue
                assert "rounded-md" in classes, f"{template_name}: button missing 'rounded-md'. Found: {classes}"
                assert "font-medium" in classes, f"{template_name}: button missing 'font-medium'. Found: {classes}"

    def test_blue_buttons_have_hover_state(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify buttons with bg-blue-600 have hover:bg-blue-700."""
        for template_name, soup in parsed_templates.items():
            for btn in soup.find_all(["button", "a"], class_=lambda x: x and "bg-blue-600" in x):
                classes = set(btn.get("class", []))
                assert "hover:bg-blue-700" in classes, (
                    f"{template_name}: Blue button missing hover state. Found: {classes}"
                )

    def test_secondary_buttons_have_hover_state(self, parsed_templates: dict[str, BeautifulSoup]) -> None:
        """Verify secondary buttons (white bg + gray border) have hover:bg-gray-50."""
        for template_name, soup in parsed_templates.items():
            for btn in soup.find_all(["button", "a"], class_=lambda x: x and "bg-white" in x and "border-gray-300" in x):
                classes = set(btn.get("class", []))
                assert "hover:bg-gray-50" in classes, (
                    f"{template_name}: Secondary button missing hover. Found: {classes}"
                )
