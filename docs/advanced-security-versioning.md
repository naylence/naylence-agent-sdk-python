# Advanced Security Docker Image Versioning

The `naylence/agent-sdk-adv-python` Docker image includes two independently versioned packages:
- `naylence-agent-sdk` (follows this repository's version)  
- `naylence-advanced-security` (has its own versioning)

## Version Selection Strategy

The workflow automatically determines the appropriate `naylence-advanced-security` version using the following priority:

### 1. Manual Workflow Dispatch
When manually triggering the workflow:
- **Required**: Specify the `adv_version` parameter
- Use case: Specific version testing, custom builds

```bash
# GitHub Actions UI: Manual workflow dispatch
# Input: adv_version = "0.1.15"
```

### 2. Repository Variable (Recommended for CI/CD)
For automatic builds (tags, releases, post-PyPI):
- Set repository variable: `ADVANCED_SECURITY_VERSION`
- Location: `Settings → Actions → Variables → Repository variables`
- Use case: Controlled releases with known compatible versions

### 3. Latest from PyPI (Fallback)
If no repository variable is set:
- Automatically fetches latest published version
- Tries PyPI first, then TestPyPI
- Use case: Development builds, latest features

## Setting Up Repository Variable

1. Go to repository `Settings → Actions → Variables`
2. Click "New repository variable"
3. Name: `ADVANCED_SECURITY_VERSION`
4. Value: `0.1.12` (or desired version)
5. Save

## Workflow Examples

### Automatic Release (with repo var)
```bash
git tag v0.1.21
git push origin v0.1.21
# Uses ADVANCED_SECURITY_VERSION repo variable
```

### Manual Build
```bash
# Via GitHub Actions UI
# Select "Build and Push Advanced Security Docker Image"
# Input adv_version: "0.1.15"
```

### Local Testing
```bash
docker build -f docker/Dockerfile.advanced-security \
  --build-arg SDK_VERSION=0.1.21 \
  --build-arg ADVANCED_SECURITY_VERSION=0.1.15 \
  -t test:local .
```

## Troubleshooting

**Error: "Could not determine naylence-advanced-security version"**

Solutions:
1. Set repository variable `ADVANCED_SECURITY_VERSION`
2. Use manual workflow dispatch with specific version
3. Ensure `naylence-advanced-security` is published to PyPI/TestPyPI

**Build fails with package not found:**
- Wait for package to be available on PyPI after publishing
- Check version exists: `pip index versions naylence-advanced-security`
