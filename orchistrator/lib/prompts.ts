/**
 * Prompt Loader
 * Reads prompts from .claude/ files and strips YAML frontmatter
 */

import { join } from 'path';

/**
 * Load a prompt from a .claude/ file
 * @param relativePath - Path relative to repo root (e.g., '.claude/skills/atomic-planning/SKILL.md')
 */
export async function loadPrompt(relativePath: string): Promise<string> {
  const fullPath = join(process.cwd(), relativePath);
  const file = Bun.file(fullPath);

  if (!(await file.exists())) {
    throw new Error(`Prompt file not found: ${fullPath}`);
  }

  const content = await file.text();
  return stripFrontmatter(content);
}

/**
 * Strip YAML frontmatter from markdown content
 */
function stripFrontmatter(content: string): string {
  // Match YAML frontmatter: starts with ---, ends with ---
  const frontmatterRegex = /^---\r?\n[\s\S]*?\r?\n---\r?\n/;
  return content.replace(frontmatterRegex, '').trim();
}

/**
 * Load a skill prompt
 */
export async function loadSkill(skillName: string): Promise<string> {
  return loadPrompt(`.claude/skills/${skillName}/SKILL.md`);
}

/**
 * Load an agent prompt
 */
export async function loadAgent(agentName: string): Promise<string> {
  return loadPrompt(`.claude/agents/${agentName}.md`);
}
