import { runWorkflow } from "./orchistrator.js";

const goal = process.argv.slice(2).join(" ").trim();
if (!goal) {
  console.error('Usage: node dist/index.js "<goal>"');
  process.exit(1);
}

runWorkflow({ goal }).catch((err) => {
  console.error(err instanceof Error ? err.stack : err);
  process.exit(1);
});
