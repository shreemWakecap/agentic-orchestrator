"""Async MCP-based planning workflow.

Provides streaming planning with real-time progress updates
via MCP protocol.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from core.mcp_client import MCPClient
from core.async_workflow import AsyncWorkflow
from core.workflow import WorkflowResult


class AsyncPlanningWorkflow(AsyncWorkflow):
    """Async MCP-based planning workflow."""

    def __init__(self, project_root: Path, mcp_client: MCPClient):
        """
        Initialize async planning workflow.

        Args:
            project_root: Project root directory
            mcp_client: MCP client for agent communication
        """
        super().__init__(
            name="Async Planning Workflow",
            project_root=project_root,
            output_dir=project_root / ".specs" / "pending",
            mcp_client=mcp_client
        )
        self._register_agents()

    def _register_agents(self):
        """Register planning agents with the pool."""
        planning_agents = [
            "analyzer", "scout", "architect", "planner", "validator",
            "decomposer", "synthesizer"
        ]

        for agent_name in planning_agents:
            self.register_agent(agent_name, timeout=300, max_tokens=4096)

    async def _execute_impl(self, request: str) -> WorkflowResult:
        """Execute async planning workflow."""
        self.print_header(f"Planning: {request[:50]}...")

        # Phase 1: Analyze complexity
        self.print_phase("Phase 1: Analyzing Complexity")
        self.print_agent("analyzer")

        context = self._get_codebase_context()
        analyzer_result = await self.run_agent("analyzer", request, context=context)

        if not analyzer_result.success:
            return WorkflowResult(
                success=False,
                output_file=None,
                steps_completed=["analyzer"],
                total_tokens=self.total_tokens,
                error=f"Analyzer failed: {analyzer_result.error}"
            )

        complexity = self._parse_complexity(analyzer_result.content)
        self.print_info(f"Complexity: {complexity.get('complexity', 'unknown')}")

        # Route based on complexity
        if complexity.get("complexity") in ["simple", "medium"]:
            return await self._simple_planning(request, context)
        else:
            return await self._complex_planning(request, context, complexity)

    async def _simple_planning(self, request: str, context: str) -> WorkflowResult:
        """Simple sequential planning for straightforward tasks."""

        # Phase 2: Scout codebase
        self.print_phase("Phase 2: Exploring Codebase")
        self.print_agent("scout")

        scout_result = await self.run_agent(
            "scout",
            f"Explore codebase for: {request}",
            context=context
        )

        if not scout_result.success:
            self.print_error(f"Scout failed: {scout_result.error}")
            # Continue with limited context
            scout_context = context[:2000]
        else:
            scout_context = scout_result.content[:4000]

        # Phase 3: Design architecture
        self.print_phase("Phase 3: Designing Architecture")
        self.print_agent("architect")

        architect_result = await self.run_agent(
            "architect",
            request,
            context=scout_context
        )

        if not architect_result.success:
            self.print_error(f"Architect failed: {architect_result.error}")
            architect_context = ""
        else:
            architect_context = architect_result.content

        # Phase 4: Create detailed plan
        self.print_phase("Phase 4: Creating Detailed Plan")
        self.print_agent("planner")

        combined_context = f"{scout_context[:2000]}\n\n{architect_context}"
        planner_result = await self.run_agent(
            "planner",
            request,
            context=combined_context
        )

        if not planner_result.success:
            return WorkflowResult(
                success=False,
                output_file=None,
                steps_completed=["analyzer", "scout", "architect", "planner"],
                total_tokens=self.total_tokens,
                error=f"Planner failed: {planner_result.error}"
            )

        # Phase 5: Validate plan
        self.print_phase("Phase 5: Validating Plan")
        self.print_agent("validator")

        validator_result = await self.run_agent(
            "validator",
            planner_result.content
        )

        # Save plan
        plan_content = planner_result.content
        if validator_result.success:
            # Append validation notes if any
            validation = self._parse_validation(validator_result.content)
            if validation.get("warnings"):
                plan_content += "\n\n## Validation Notes\n"
                for warning in validation.get("warnings", []):
                    plan_content += f"- {warning}\n"

        plan_file = self._save_plan(request, plan_content)
        self.print_success(f"Plan saved: {plan_file.name}")

        return WorkflowResult(
            success=True,
            output_file=plan_file,
            steps_completed=["analyzer", "scout", "architect", "planner", "validator"],
            total_tokens=self.total_tokens
        )

    async def _complex_planning(
        self,
        request: str,
        context: str,
        complexity: dict
    ) -> WorkflowResult:
        """Complex planning with decomposition and parallel sub-plans."""

        # Phase 2: Global scout
        self.print_phase("Phase 2: Deep Codebase Exploration")
        self.print_agent("scout")

        scout_result = await self.run_agent(
            "scout",
            f"Comprehensive exploration for: {request}",
            context=context
        )

        scout_context = scout_result.content[:4000] if scout_result.success else context[:2000]

        # Phase 3: Decompose into sub-features
        self.print_phase("Phase 3: Decomposing into Sub-features")
        self.print_agent("decomposer")

        decomposer_result = await self.run_agent(
            "decomposer",
            request,
            context=scout_context
        )

        if not decomposer_result.success:
            self.print_error("Decomposer failed, falling back to simple planning")
            return await self._simple_planning(request, context)

        sub_features = self._parse_sub_features(decomposer_result.content)
        if not sub_features:
            self.print_error("No sub-features parsed, falling back to simple planning")
            return await self._simple_planning(request, context)

        self.print_info(f"Decomposed into {len(sub_features)} sub-features")

        # Phase 4: Parallel sub-feature planning
        self.print_phase("Phase 4: Parallel Sub-feature Planning")

        # Limit parallel execution to 3 features
        sub_plan_tasks = []
        for sf in sub_features[:3]:
            sf_name = sf.get("name", "unknown")
            sf_desc = sf.get("description", "")
            sub_plan_tasks.append((
                "planner",
                f"Plan for sub-feature: {sf_name}\n\n{sf_desc}",
                scout_context[:2000]
            ))
            self.print_agent("planner", f"Planning {sf_name}")

        sub_plans = await self.run_agents_parallel(sub_plan_tasks)

        # Phase 5: Synthesize sub-plans
        self.print_phase("Phase 5: Synthesizing Plans")
        self.print_agent("synthesizer")

        combined = "\n\n---\n\n".join(
            p.content for p in sub_plans if p.success
        )

        synthesizer_result = await self.run_agent(
            "synthesizer",
            f"Original request: {request}\n\nSub-plans:\n{combined}"
        )

        if not synthesizer_result.success:
            return WorkflowResult(
                success=False,
                output_file=None,
                steps_completed=["analyzer", "scout", "decomposer", "planner", "synthesizer"],
                total_tokens=self.total_tokens,
                error=f"Synthesizer failed: {synthesizer_result.error}"
            )

        # Phase 6: Validate synthesized plan
        self.print_phase("Phase 6: Validating Synthesized Plan")
        self.print_agent("validator")

        validator_result = await self.run_agent(
            "validator",
            synthesizer_result.content
        )

        # Save plan
        plan_content = synthesizer_result.content
        plan_file = self._save_plan(request, plan_content)
        self.print_success(f"Plan saved: {plan_file.name}")

        return WorkflowResult(
            success=True,
            output_file=plan_file,
            steps_completed=["analyzer", "scout", "decomposer", "planner", "synthesizer", "validator"],
            total_tokens=self.total_tokens
        )

    def _get_codebase_context(self) -> str:
        """Gather codebase context for agents."""
        context_parts = []

        # Check for key files
        key_files = [
            "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
            "README.md", "src/main.py", "src/index.ts", "main.go"
        ]

        for filename in key_files:
            filepath = self.project_root / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8")[:2000]
                    context_parts.append(f"### {filename}\n```\n{content}\n```")
                except Exception:
                    pass

        # List key directories
        for dirname in ["src", "lib", "app", "pkg"]:
            dirpath = self.project_root / dirname
            if dirpath.exists() and dirpath.is_dir():
                try:
                    files = list(dirpath.glob("**/*"))[:20]
                    file_list = "\n".join(str(f.relative_to(self.project_root)) for f in files if f.is_file())
                    context_parts.append(f"### {dirname}/ structure\n{file_list}")
                except Exception:
                    pass

        return "\n\n".join(context_parts)[:8000]

    def _parse_complexity(self, content: str) -> dict:
        """Parse complexity analysis from agent response."""
        try:
            # Try to extract JSON
            json_match = re.search(r'\{[^{}]*"complexity"[^{}]*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Fallback: look for keywords
        content_lower = content.lower()
        if "complex" in content_lower or "high" in content_lower:
            return {"complexity": "complex"}
        elif "medium" in content_lower:
            return {"complexity": "medium"}
        return {"complexity": "simple"}

    def _parse_sub_features(self, content: str) -> List[dict]:
        """Parse sub-features from decomposer response."""
        try:
            # Try to extract JSON array
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # Try to extract from JSON object with sub_features key
            json_match = re.search(r'\{[^{}]*"sub_features"\s*:\s*\[.*?\][^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("sub_features", [])
        except json.JSONDecodeError:
            pass

        # Fallback: parse markdown-style list
        features = []
        for match in re.finditer(r'##?\s+(.+?)\n([\s\S]*?)(?=##|\Z)', content):
            name = match.group(1).strip()
            desc = match.group(2).strip()[:500]
            if name and not name.lower().startswith(("overview", "summary", "note")):
                features.append({"name": name, "description": desc})

        return features[:5]  # Limit to 5 features

    def _parse_validation(self, content: str) -> dict:
        """Parse validation results."""
        try:
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {}

    def _save_plan(self, request: str, content: str) -> Path:
        """Save plan to output directory."""
        # Generate filename from request
        slug = re.sub(r'[^\w\s-]', '', request.lower())
        slug = re.sub(r'[\s_]+', '-', slug)[:40]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"plan-{slug}-{timestamp}.md"

        plan_file = self.output_dir / filename

        # Add header
        full_content = f"# Plan: {request[:80]}\n\n"
        full_content += f"*Generated: {datetime.now().isoformat()}*\n\n"
        full_content += f"*Tokens used: {self.total_tokens}*\n\n"
        full_content += "---\n\n"
        full_content += content

        plan_file.write_text(full_content, encoding="utf-8")
        return plan_file
