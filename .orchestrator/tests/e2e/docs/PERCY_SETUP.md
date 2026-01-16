# Percy Visual Regression Testing Setup

This guide explains how to set up and use Percy.io for visual regression testing with our Playwright E2E tests.

## Overview

Percy captures screenshots of your application at multiple viewport widths and compares them against baseline images. When visual differences are detected, Percy highlights them for review, preventing unintended UI regressions.

## Prerequisites

- Node.js 18+ installed
- Playwright E2E tests configured
- Percy.io account (free tier available)

## 1. Obtaining Your Percy Token

### Create a Percy Account

1. Go to [percy.io](https://percy.io) and sign up (GitHub OAuth recommended)
2. Create a new project or select an existing one
3. Choose "Playwright" as your integration type

### Get Your Project Token

1. Navigate to your Percy project
2. Go to **Project Settings** → **Project token**
3. Copy the token (format: `PERCY_TOKEN=xxxxxxxxxxxxxxxx`)

> **Security Note:** Never commit your Percy token to version control. Always use environment variables or secrets management.

## 2. Local Environment Setup

### Option A: Environment Variable (Recommended)

**Windows (PowerShell):**
```powershell
$env:PERCY_TOKEN="your_token_here"
```

**Windows (Command Prompt):**
```cmd
set PERCY_TOKEN=your_token_here
```

**Linux/macOS:**
```bash
export PERCY_TOKEN="your_token_here"
```

### Option B: .env File

Create a `.env` file in the project root (ensure it's in `.gitignore`):

```env
PERCY_TOKEN=your_token_here
```

### Option C: Shell Profile (Persistent)

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, or PowerShell profile):

```bash
export PERCY_TOKEN="your_token_here"
```

## 3. GitHub Actions CI Setup

### Add the Percy Token as a Repository Secret

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `PERCY_TOKEN`
5. Value: Your Percy project token
6. Click **Add secret**

### Workflow Configuration

The Percy CI workflow is already configured in `.github/workflows/percy.yml`. It:

- Triggers on pull requests and pushes to main branches
- Installs dependencies and builds the application
- Runs Percy visual tests with `npm run test:visual`
- Uses the `PERCY_TOKEN` secret automatically

## 4. Running Visual Tests

### Run Locally

```bash
# Ensure PERCY_TOKEN is set, then run:
npm run test:visual
```

This command:
1. Starts the Percy agent
2. Launches Playwright with the visual test suite
3. Captures screenshots at configured viewport widths (1280px, 768px, 375px)
4. Uploads snapshots to Percy for comparison

### Run Specific Visual Tests

```bash
# Run only visual regression tests
npx percy exec -- npx playwright test --grep @visual

# Run a specific visual test file
npx percy exec -- npx playwright test visual/snapshots.spec.ts
```

### Run Without Percy (Dry Run)

To run visual tests locally without uploading to Percy:

```bash
# Runs tests but skips Percy snapshot capture
npx playwright test .orchestrator/tests/e2e/visual/
```

## 5. Understanding Percy Dashboard Results

### Accessing Results

1. After tests complete, Percy provides a dashboard URL in the console output
2. Alternatively, visit [percy.io](https://percy.io) and select your project

### Build States

| State | Description |
|-------|-------------|
| **Pending** | Screenshots are being processed |
| **Unreviewed** | Visual changes detected, awaiting review |
| **Approved** | All changes reviewed and approved |
| **Changes Requested** | Reviewer requested changes |
| **No Changes** | No visual differences from baseline |

### Reviewing Visual Diffs

1. Click on a build to see all snapshots
2. Snapshots with changes show a diff overlay:
   - **Red**: Removed pixels
   - **Green**: Added pixels
   - **Yellow**: Changed pixels
3. Toggle between views:
   - **Side by side**: Compare baseline and new
   - **Overlay**: See differences highlighted
   - **Slider**: Drag to compare

### Approving Changes

- **Approve All**: Accept all visual changes as new baseline
- **Approve Individual**: Accept specific snapshot changes
- **Request Changes**: Mark snapshots needing fixes

### Best Practices for Reviews

1. **Review carefully**: Small changes can indicate bugs
2. **Check all viewports**: Issues may only appear at specific widths
3. **Look for unintended changes**: Focus areas you didn't modify
4. **Update baselines intentionally**: Only approve expected changes

## 6. Configuration Reference

### percy.yml Settings

Located at project root, `percy.yml` controls snapshot behavior:

```yaml
version: 2
snapshot:
  widths:
    - 1280  # Desktop
    - 768   # Tablet
    - 375   # Mobile
  min-height: 1024
  percy-css: |
    /* Hide dynamic content */
    [data-percy-hide] { visibility: hidden !important; }
```

### Viewport Widths

| Width | Device Category | Use Case |
|-------|-----------------|----------|
| 1280px | Desktop | Standard desktop view |
| 768px | Tablet | iPad and tablet layouts |
| 375px | Mobile | iPhone and mobile layouts |

## 7. Troubleshooting

### Common Issues

**"PERCY_TOKEN not set"**
```
Error: PERCY_TOKEN was not provided.
```
Solution: Set the `PERCY_TOKEN` environment variable before running tests.

**"No snapshots captured"**
- Ensure tests include `percySnapshot()` calls
- Check that the application is running and accessible
- Verify selectors are finding elements before snapshot

**"Snapshots timing out"**
```typescript
// Increase wait time for dynamic content
await page.waitForLoadState('networkidle');
await percySnapshot(page, 'Page Name');
```

**"Flaky visual diffs"**
- Add CSS to hide dynamic content (timestamps, animations)
- Use `data-percy-hide` attribute on dynamic elements
- Ensure fonts are fully loaded before snapshot

### Debug Mode

Run with verbose logging:

```bash
# Enable Percy debug output
PERCY_LOGLEVEL=debug npm run test:visual
```

### Skipping Percy in Local Development

Set `PERCY_ENABLE=0` to disable Percy without removing code:

```bash
PERCY_ENABLE=0 npm run test:visual
```

## 8. Integration with Pull Requests

### GitHub Integration

Percy automatically:
1. Comments on PRs with visual diff summary
2. Adds status check requiring approval
3. Links directly to visual review dashboard

### Workflow

1. Developer creates PR with UI changes
2. CI runs visual tests automatically
3. Percy captures new screenshots
4. Percy compares against base branch baseline
5. Visual diffs appear in Percy dashboard
6. Reviewer approves visual changes
7. Percy status check passes
8. PR can be merged

### Branch Baselines

- `main`/`developmet`: Primary baseline branches
- Feature branches: Compare against base branch
- Auto-approve: Can configure for specific branches

## 9. Cost and Usage

### Free Tier Limits

- 5,000 screenshots/month
- Unlimited team members
- 1 concurrent build

### Optimizing Usage

1. Run visual tests only on PR and main branch pushes
2. Limit viewports to essential breakpoints
3. Snapshot only key pages, not every test
4. Use `@visual` tag to separate visual from functional tests

## Additional Resources

- [Percy Documentation](https://docs.percy.io/)
- [Percy Playwright SDK](https://docs.percy.io/docs/playwright)
- [Percy GitHub Integration](https://docs.percy.io/docs/github)
- [Percy Configuration Options](https://docs.percy.io/docs/configuration)
