# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NC Foreclosures Project - A data analysis and foreclosure tracking system for North Carolina.

**Repository:** https://github.com/nash1515/nc_foreclosures

**Note:** This is a new project in early setup phase. Project specifications are documented in "NC Foreclosures Project_StartUp Doc.docx".

## Context Window Management Strategy

**CRITICAL:** To maximize context window efficiency, always use GitHub for collaboration and tracking:

### Git Workflow for Context Management
1. **Commit frequently** - Small, focused commits preserve context and enable rollback
2. **Push immediately after commits** - Keep GitHub as the source of truth
3. **Use descriptive commit messages** - Future Claude instances need clear history
4. **Create branches for features** - Isolate work to reduce cognitive load
5. **Use GitHub Issues** - Track bugs, features, and tasks outside of code context
6. **Leverage pull requests** - Document major changes with descriptions and reviews
7. **Tag important milestones** - Mark stable versions for easy reference

### When Working with Claude Code
- Always commit and push before starting major refactoring
- Use `git status` and `git diff` to understand current state efficiently
- Prefer reading recent commits over re-reading entire files
- Use GitHub CLI (`gh`) to manage issues, PRs, and releases
- Reference commit SHAs and file paths with line numbers in discussions

### Essential Git Commands
```bash
# Quick status check
git status

# Stage and commit changes
git add <file>
git commit -m "descriptive message"

# Push to GitHub
git push

# View recent changes
git log --oneline -10
git diff

# Create feature branch
git checkout -b feature/name

# View file history
git log -p <file>
```

### GitHub CLI Commands
```bash
# Create issue
gh issue create --title "title" --body "description"

# List issues
gh issue list

# Create PR
gh pr create --title "title" --body "description"

# View PR status
gh pr status
```

## Project Status

This repository is currently in initial setup. Once the codebase is developed, this file should be updated with:
- Build and test commands
- Project architecture overview
- Data pipeline structure
- Database schema information
- API endpoints (if applicable)
- Development workflow

## Getting Started

Since this is a new project, refer to the startup document for requirements and initial specifications.

## Notes for Future Development

When the project structure is established, update this file with:
1. How to set up the development environment
2. How to run the application
3. How to run tests
4. Database connection and migration procedures
5. Key architectural decisions and patterns
6. Data source information and processing workflows
