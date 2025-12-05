#!/bin/bash
# Development Worktree Management Script
#
# Creates isolated worktrees for feature development without
# affecting the stable main branch.
#
# Usage:
#   ./scripts/dev_worktree.sh create <feature-name>
#   ./scripts/dev_worktree.sh delete <feature-name>
#   ./scripts/dev_worktree.sh list

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKTREE_DIR="$PROJECT_ROOT/.worktrees"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Development Worktree Management"
    echo ""
    echo "Usage:"
    echo "  $0 create <feature-name>   Create a new worktree for feature development"
    echo "  $0 delete <feature-name>   Delete a worktree and its branch"
    echo "  $0 list                    List all worktrees"
    echo ""
    echo "Examples:"
    echo "  $0 create dashboard-improvements"
    echo "  $0 delete dashboard-improvements"
}

create_worktree() {
    local feature_name=$1
    local branch_name="feature/$feature_name"
    local worktree_path="$WORKTREE_DIR/$feature_name"

    if [ -z "$feature_name" ]; then
        echo "Error: Feature name required"
        usage
        exit 1
    fi

    # Check if worktree already exists
    if [ -d "$worktree_path" ]; then
        echo "Error: Worktree '$feature_name' already exists at $worktree_path"
        exit 1
    fi

    echo -e "${BLUE}Creating worktree for feature: $feature_name${NC}"
    echo ""

    # Create worktrees directory if needed
    mkdir -p "$WORKTREE_DIR"

    # Create branch and worktree
    cd "$PROJECT_ROOT"

    # Check if branch exists
    if git show-ref --verify --quiet "refs/heads/$branch_name"; then
        echo "Branch '$branch_name' already exists, using it..."
        git worktree add "$worktree_path" "$branch_name"
    else
        echo "Creating new branch '$branch_name'..."
        git worktree add -b "$branch_name" "$worktree_path" main
    fi

    echo ""
    echo -e "${GREEN}Worktree created successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo ""
    echo "1. Navigate to the worktree frontend:"
    echo -e "   ${BLUE}cd $worktree_path/frontend${NC}"
    echo ""
    echo "2. Install dependencies (first time only):"
    echo -e "   ${BLUE}npm install${NC}"
    echo ""
    echo "3. Start the dev server on port 5174:"
    echo -e "   ${BLUE}npm run dev -- --port 5174${NC}"
    echo ""
    echo "4. Open http://localhost:5174 in your browser"
    echo ""
    echo "5. Make changes - they appear instantly (Hot Module Reload)"
    echo ""
    echo -e "${YELLOW}When you're done:${NC}"
    echo "   git add . && git commit -m 'Your changes'"
    echo "   git push origin $branch_name"
    echo "   $0 delete $feature_name"
}

delete_worktree() {
    local feature_name=$1
    local branch_name="feature/$feature_name"
    local worktree_path="$WORKTREE_DIR/$feature_name"

    if [ -z "$feature_name" ]; then
        echo "Error: Feature name required"
        usage
        exit 1
    fi

    if [ ! -d "$worktree_path" ]; then
        echo "Error: Worktree '$feature_name' does not exist"
        exit 1
    fi

    echo -e "${YELLOW}Removing worktree: $feature_name${NC}"

    cd "$PROJECT_ROOT"

    # Remove the worktree
    git worktree remove "$worktree_path" --force

    # Optionally delete the branch (ask user)
    echo ""
    read -p "Delete branch '$branch_name'? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git branch -D "$branch_name" 2>/dev/null || echo "Branch already deleted or merged"
    fi

    echo ""
    echo -e "${GREEN}Worktree removed successfully!${NC}"
}

list_worktrees() {
    echo -e "${BLUE}Current worktrees:${NC}"
    echo ""
    cd "$PROJECT_ROOT"
    git worktree list
}

# Main
case "$1" in
    create)
        create_worktree "$2"
        ;;
    delete)
        delete_worktree "$2"
        ;;
    list)
        list_worktrees
        ;;
    *)
        usage
        exit 1
        ;;
esac
