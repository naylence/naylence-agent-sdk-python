#!/bin/bash
set -e

# Get current version from pyproject.toml
CURRENT_VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
echo "Current version: $CURRENT_VERSION"

# Check if tag already exists
if git tag --list | grep -q "^v${CURRENT_VERSION}$"; then
    echo "❌ Tag v$CURRENT_VERSION already exists!"
    echo "Please update the version in pyproject.toml first"
    exit 1
fi

# Check if there are uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    echo "❌ You have uncommitted changes. Please commit them first."
    exit 1
fi

echo "Creating release for version $CURRENT_VERSION..."

# Create and push tag
git tag "v$CURRENT_VERSION"
git push origin main --tags

echo "✅ Created and pushed tag v$CURRENT_VERSION"

# Create GitHub release (if gh CLI is installed)
if command -v gh &> /dev/null; then
    echo "Creating GitHub release..."
    gh release create "v$CURRENT_VERSION" --generate-notes
    echo "✅ Created GitHub release"
else
    echo "⚠️  GitHub CLI not found. Please create the release manually at:"
    echo "https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\([^/]*\/[^/]*\).*/\1/' | sed 's/\.git$//')/releases/new?tag=v$CURRENT_VERSION"
fi

echo "🎉 Release process complete!"
