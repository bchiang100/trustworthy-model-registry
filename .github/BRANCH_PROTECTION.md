# Branch Protection Setup Guide

## Setting Up Branch Protection Rules

### Protecting the Main Branch
1. Go to your repository's **Settings** tab, then click **Branches**
2. Click **Add rule** to create a new protection rule
3. In the branch name pattern field, type: `main`
4. Now enable these important settings:
   - **Require a pull request before merging**
     - Set required approving reviews to: `1`
     - Check "Dismiss stale PR reviews when new commits are pushed"
     - Check "Require review from code owners" (if you have a CODEOWNERS file)
   - **Require status checks to pass before merging**
     - Check "Require branches to be up to date before merging"
     - Add these required status checks:
       - `test (3.10)`
       - `test (3.11)`
       - `lint`
       - `build`
       - `security`
   - **Require conversation resolution before merging**
   - **Include administrators** (this makes sure even admins follow the rules)
   - **Allow force pushes** - UNCHECK this (prevents dangerous force pushes)
   - **Allow deletions** - UNCHECK this (prevents accidental branch deletion)

### Protecting the Dev Branch
1. Create another rule with branch name pattern: `dev`
2. Enable these settings:
   - **Require a pull request before merging** with 1 required review
   - **Require status checks to pass before merging** (same checks as main)
   - **Include administrators**

### Working on New Features
1. Start from the dev branch: `git checkout dev && git checkout -b feature/your-feature`
2. Write your code and make commits as you go
3. Push your branch: `git push -u origin feature/your-feature`
4. Open a pull request targeting the `dev` branch
5. Wait for all the automated tests to pass
6. Ask a teammate to review your code
7. Once approved, merge into `dev`

### Releasing to Production
1. When we're ready for a release, create a PR from `dev` to `main`
2. All automated checks must pass (no exceptions!)
3. The team lead needs to approve the release
4. Merging to main automatically deploys to our staging environment
5. Production deployment requires manual approval for safety

## CI/CD Pipeline Status Checks

Wrkflows will create these status checks that must pass:

### CI Pipeline (`ci.yml`)
- **test (3.10)** - Tests on Python 3.10
- **test (3.11)** - Tests on Python 3.11
- **lint** - Code style and formatting checks
- **build** - Package build verification
- **security** - Security vulnerability scanning

### CD Pipeline (`cd.yml`)
- **deploy-staging** - Staging environment deployment
- **deploy-production** - Production deployment (manual trigger)

## What Everyone Should Do

### When Reviewing Code
Every PR needs at least one teammate to review it. When you're reviewing someone's code, check these things:
- Does the code actually work and make sense?
- Are there tests for any new features?
- Did they update documentation if needed?
- No passwords or API keys hardcoded anywhere
- Code follows our team's style guidelines

### Before Submitting PR
Run these commands locally to make sure everything looks good:
- `python -m pytest` - All tests should pass
- `black src/ tests/` - Format your code properly
- `isort src/ tests/` - Sort your imports
- `flake8 src/ tests/` - Check for any linting issues
- `bandit -r src/` - Make sure there are no security problems
- Write a clear PR description explaining what you changed and why
- Link to any related issues if you're fixing something specific