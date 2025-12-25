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
DOCKERHUB_IMAGE="naylence/agent-sdk-python"
PUSH=false
PLATFORM="linux/amd64"
BUILD_LATEST=false
SKIP_PACKAGE_CHECK=false
ADVANCED_SECURITY_VERSION="0.3.0"

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

Build Docker image locally for naylence-agent-sdk-python

OPTIONS:
    -p, --push                    Push image to Docker Hub after building
    -l, --latest                  Also tag as 'latest'
    -m, --multi-platform          Build for multiple platforms (linux/amd64,linux/arm64)
    -a, --advanced-security       Also build advanced security image
    -s, --skip-package-check      Skip PyPI package availability check
    -t, --tag TAG                 Additional custom tag to apply
    --platform PLATFORM           Specify platform (default: linux/amd64)
    -h, --help                    Show this help message

EXAMPLES:
    # Build locally for current platform
    $0

    # Build and push with version tag
    $0 --push

    # Build multi-platform and push with latest tag
    $0 --push --latest --multi-platform

    # Build both standard and advanced security images
    $0 --advanced-security

    # Build with custom tag
    $0 --tag my-custom-tag
EOF
    exit 0
}

# Parse command line arguments
CUSTOM_TAG=""
BUILD_ADVANCED=false
while [[ $# -gt 0 ]]; do
    case $1 in
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
        -a|--advanced-security)
            BUILD_ADVANCED=true
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

# Extract version from pyproject.toml
print_info "Extracting version from pyproject.toml..."
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")

if [ -z "$VERSION" ]; then
    print_error "Failed to extract version from pyproject.toml"
    exit 1
fi

print_success "Extracted version: $VERSION"

# Check if git tag matches
print_info "Checking git tag consistency..."
if git tag --list | grep -q "^v${VERSION}$"; then
    print_success "Found matching git tag: v$VERSION"
else
    print_warning "No matching git tag found for version $VERSION"
    print_info "Consider creating a git tag: git tag v$VERSION"
fi

# Function to check if package version is available on PyPI or TestPyPI
check_package_availability() {
    local package_name="naylence-agent-sdk"
    local version=$1
    
    print_info "Checking if $package_name version $version is available..."
    
    # Try to check if the package version exists using pip index
    # First try PyPI (default)
    if python3 -m pip index versions "$package_name" 2>/dev/null | grep -q "$version"; then
        print_success "Package $package_name version $version found on PyPI"
        return 0
    fi
    
    # If not found on PyPI, try TestPyPI
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
    check_package_availability "$VERSION" || true
else
    print_info "Skipping package availability check"
fi

# Build function
build_image() {
    local dockerfile=$1
    local image_name=$2
    local extra_build_args=$3
    
    # Build tags
    IMAGE="${DOCKERHUB_REGISTRY}/${image_name}"
    TAGS="${IMAGE}:${VERSION}"
    
    if [ "$BUILD_LATEST" = true ]; then
        TAGS="${TAGS} ${IMAGE}:latest"
    fi
    
    # Add semantic version tags if version follows semver pattern
    if [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f1-2)
        TAGS="${TAGS} ${IMAGE}:${MAJOR} ${IMAGE}:${MINOR}"
    fi
    
    # Add custom tag if provided
    if [ -n "$CUSTOM_TAG" ]; then
        TAGS="${TAGS} ${IMAGE}:${CUSTOM_TAG}"
    fi
    
    # Convert tags to docker build format
    TAG_ARGS=""
    for tag in $TAGS; do
        TAG_ARGS="${TAG_ARGS} -t ${tag}"
    done
    
    print_info "Building Docker image: ${image_name}"
    print_info "Platform: $PLATFORM"
    print_info "Tags: $TAGS"
    
    # Build command
    BUILD_CMD="docker buildx build \
        --platform ${PLATFORM} \
        --file ${dockerfile} \
        --build-arg SDK_VERSION=${VERSION} \
        ${extra_build_args} \
        ${TAG_ARGS} \
        --label org.opencontainers.image.title=naylence-agent-sdk \
        --label org.opencontainers.image.description=\"Naylence Agent SDK\" \
        --label org.opencontainers.image.version=${VERSION} \
        --label org.opencontainers.image.licenses=Apache-2.0 \
        --label org.opencontainers.image.source=https://github.com/naylence/naylence-agent-sdk-python \
        --label org.opencontainers.image.created=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    
    if [ "$PUSH" = true ]; then
        BUILD_CMD="${BUILD_CMD} --push"
    else
        BUILD_CMD="${BUILD_CMD} --load"
    fi
    
    BUILD_CMD="${BUILD_CMD} ."
    
    # Execute build
    print_info "Executing docker buildx build..."
    eval $BUILD_CMD
    
    if [ $? -eq 0 ]; then
        print_success "Docker image built successfully: ${image_name}"
        echo ""
        print_info "Built tags:"
        for tag in $TAGS; do
            echo "  - $tag"
        done
        echo ""
    else
        print_error "Docker build failed for ${image_name}!"
        return 1
    fi
}

# Build standard image
print_info "Building standard image..."
build_image "./docker/Dockerfile" "${DOCKERHUB_IMAGE}" ""

# Build advanced security image if requested
if [ "$BUILD_ADVANCED" = true ]; then
    print_info "Building advanced security image..."
    build_image "./docker/Dockerfile.advanced-security" "naylence/agent-sdk-adv-python" "--build-arg ADVANCED_SECURITY_VERSION=${ADVANCED_SECURITY_VERSION}"
fi

# Final summary
echo ""
print_success "All Docker images built successfully!"

if [ "$PUSH" = true ]; then
    print_success "Images pushed to registry!"
else
    echo ""
    print_info "To push the images, run with --push flag"
    print_info "To test the standard image locally, run:"
    echo "  docker run --rm ${DOCKERHUB_REGISTRY}/${DOCKERHUB_IMAGE}:${VERSION}"
fi
