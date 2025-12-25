#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DOCKERHUB_REGISTRY="docker.io"
DOCKERHUB_IMAGE="naylence/agent-sdk-adv-python"
PUSH=false
PLATFORM="linux/amd64"
BUILD_LATEST=false
SKIP_PACKAGE_CHECK=false
ADVANCED_SECURITY_VERSION=""

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build Advanced Security Docker image locally for naylence-agent-sdk-python

This script builds the advanced security variant which includes naylence-advanced-security.
If no version is specified, the latest version will be automatically fetched from PyPI/TestPyPI.

OPTIONS:
    -a, --adv-version VERSION     Specify naylence-advanced-security version (optional)
                                  If not provided, latest version is auto-detected from PyPI
    -p, --push                    Push image to Docker Hub after building
    -l, --latest                  Also tag as 'latest'
    -m, --multi-platform          Build for multiple platforms (linux/amd64,linux/arm64)
    -s, --skip-package-check      Skip PyPI package availability check
    -t, --tag TAG                 Additional custom tag to apply
    --platform PLATFORM           Specify platform (default: linux/amd64)
    -h, --help                    Show this help message

EXAMPLES:
    # Build with auto-detected latest version
    $0

    # Build with specific advanced security version
    $0 --adv-version 0.3.0

    # Build and push with latest tag (auto-detect version)
    $0 --push --latest

    # Build multi-platform and push
    $0 --adv-version 0.3.0 --push --multi-platform

NOTES:
    - The SDK version is automatically extracted from pyproject.toml
    - Advanced security version is auto-detected from PyPI/TestPyPI if not specified
    - Advanced security package must be available on PyPI or TestPyPI
EOF
    exit 0
}

# Parse command line arguments
CUSTOM_TAG=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--adv-version)
            ADVANCED_SECURITY_VERSION="$2"
            shift 2
            ;;
        -p|--push)
            PUSH=true
            shift
            ;;
        -l|--latest)
            BUILD_LATEST=true
            shift
            ;;
        -m|--multi-platform)
            PLATFORM="linux/amd64,linux/arm64"
            shift
            ;;
        -s|--skip-package-check)
            SKIP_PACKAGE_CHECK=true
            shift
            ;;
        -t|--tag)
            CUSTOM_TAG="$2"
            shift 2
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Extract SDK version from pyproject.toml
print_info "Extracting SDK version from pyproject.toml..."
SDK_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")

if [ -z "$SDK_VERSION" ]; then
    print_error "Failed to extract SDK version from pyproject.toml"
    exit 1
fi

print_success "Extracted SDK version: $SDK_VERSION"

# Determine advanced security version
if [ -z "$ADVANCED_SECURITY_VERSION" ] || [ "$ADVANCED_SECURITY_VERSION" = "auto" ]; then
    print_info "Auto-detecting latest naylence-advanced-security version from PyPI..."
    
    # Try PyPI first
    ADVANCED_SECURITY_VERSION=$(python3 -m pip index versions naylence-advanced-security 2>/dev/null | head -1 | grep -o '([^)]*' | sed 's/(//' || echo "")
    
    if [ -z "$ADVANCED_SECURITY_VERSION" ]; then
        print_info "Not found on PyPI, checking TestPyPI..."
        ADVANCED_SECURITY_VERSION=$(python3 -m pip index versions naylence-advanced-security --index-url https://test.pypi.org/simple/ 2>/dev/null | head -1 | grep -o '([^)]*' | sed 's/(//' || echo "")
    fi
    
    if [ -z "$ADVANCED_SECURITY_VERSION" ]; then
        print_error "Could not auto-detect naylence-advanced-security version"
        echo ""
        print_info "Options to fix this:"
        echo "  1. Specify version manually: --adv-version 0.3.0"
        echo "  2. Ensure naylence-advanced-security is published to PyPI/TestPyPI"
        exit 1
    fi
    
    print_success "Auto-detected advanced security version: $ADVANCED_SECURITY_VERSION"
else
    print_success "Using specified advanced security version: $ADVANCED_SECURITY_VERSION"
fi

# Check if git tag matches SDK version
print_info "Checking git tag consistency..."
if git tag --list | grep -q "^v${SDK_VERSION}$"; then
    print_success "Found matching git tag: v$SDK_VERSION"
else
    print_warning "No matching git tag found for SDK version $SDK_VERSION"
    print_info "Consider creating a git tag: git tag v$SDK_VERSION"
fi

# Function to check if package version is available on PyPI or TestPyPI
check_package_availability() {
    local package_name=$1
    local version=$2
    
    print_info "Checking if $package_name version $version is available..."
    
    # Try PyPI first
    if python3 -m pip index versions "$package_name" 2>/dev/null | grep -q "$version"; then
        print_success "Package $package_name version $version found on PyPI"
        return 0
    fi
    
    # Try TestPyPI
    if python3 -m pip index versions "$package_name" --index-url https://test.pypi.org/simple/ 2>/dev/null | grep -q "$version"; then
        print_success "Package $package_name version $version found on TestPyPI"
        return 0
    fi
    
    print_warning "Package $package_name version $version not found on PyPI or TestPyPI"
    print_warning "Docker build may fail if package is not available"
    return 1
}

# Check package availability unless skipped
if [ "$SKIP_PACKAGE_CHECK" = false ]; then
    print_info "Checking package availability on PyPI/TestPyPI..."
    check_package_availability "naylence-agent-sdk" "$SDK_VERSION" || true
    check_package_availability "naylence-advanced-security" "$ADVANCED_SECURITY_VERSION" || true
else
    print_info "Skipping package availability check"
fi

# Build tags
IMAGE="${DOCKERHUB_REGISTRY}/${DOCKERHUB_IMAGE}"
TAGS="${IMAGE}:${SDK_VERSION}"

if [ "$BUILD_LATEST" = true ]; then
    TAGS="${TAGS} ${IMAGE}:latest"
    print_info "Will also tag as 'latest'"
fi

# Add semantic version tags if SDK version follows semver pattern
if [[ "$SDK_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    MAJOR=$(echo $SDK_VERSION | cut -d. -f1)
    MINOR=$(echo $SDK_VERSION | cut -d. -f1-2)
    TAGS="${TAGS} ${IMAGE}:${MAJOR} ${IMAGE}:${MINOR}"
    print_info "Adding semantic version tags: ${MAJOR}, ${MINOR}"
fi

# Add custom tag if provided
if [ -n "$CUSTOM_TAG" ]; then
    TAGS="${TAGS} ${IMAGE}:${CUSTOM_TAG}"
    print_info "Adding custom tag: ${CUSTOM_TAG}"
fi

# Convert tags to docker build format
TAG_ARGS=""
for tag in $TAGS; do
    TAG_ARGS="${TAG_ARGS} -t ${tag}"
done

print_info "Building Advanced Security Docker image..."
print_info "Platform: $PLATFORM"
print_info "SDK Version: $SDK_VERSION"
print_info "Advanced Security Version: $ADVANCED_SECURITY_VERSION"
print_info "Tags: $TAGS"

# Build command
BUILD_CMD="docker buildx build \
    --platform ${PLATFORM} \
    --file ./docker/Dockerfile.advanced-security \
    --build-arg SDK_VERSION=${SDK_VERSION} \
    --build-arg ADVANCED_SECURITY_VERSION=${ADVANCED_SECURITY_VERSION} \
    ${TAG_ARGS} \
    --label org.opencontainers.image.title=naylence-agent-sdk-adv-python \
    --label org.opencontainers.image.description=\"Naylence Agent SDK (advanced security build). Includes naylence-advanced-security.\" \
    --label org.opencontainers.image.version=${SDK_VERSION} \
    --label \"org.opencontainers.image.licenses=Apache-2.0 AND BSL-1.1\" \
    --label org.opencontainers.image.source=https://github.com/naylence/naylence-agent-sdk-python \
    --label org.opencontainers.image.created=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

if [ "$PUSH" = true ]; then
    BUILD_CMD="${BUILD_CMD} --push"
    print_info "Will push to registry after build"
else
    BUILD_CMD="${BUILD_CMD} --load"
fi

BUILD_CMD="${BUILD_CMD} ."

# Execute build
print_info "Executing docker buildx build..."
eval $BUILD_CMD

if [ $? -eq 0 ]; then
    echo ""
    print_success "Advanced Security Docker image built successfully!"
    echo ""
    print_info "Built tags:"
    for tag in $TAGS; do
        echo "  - $tag"
    done
    echo ""
    print_info "Image details:"
    echo "  - SDK version: $SDK_VERSION"
    echo "  - Advanced Security version: $ADVANCED_SECURITY_VERSION"
    echo "  - Licenses: Apache-2.0 AND BSL-1.1"
    
    if [ "$PUSH" = true ]; then
        print_success "Images pushed to registry!"
    else
        echo ""
        print_info "To push the images, run with --push flag"
        print_info "To test the image locally, run:"
        echo "  docker run --rm ${IMAGE}:${SDK_VERSION}"
    fi
else
    print_error "Docker build failed!"
    exit 1
fi
