# Global CI/CD Setup Guide for QuickHaul Microservices

This guide provides a sequential, step-by-step process for setting up the standardized CI/CD pipeline for any new microservice repository in the QuickHaulTransits organization.

## 1. Configure Organization Secrets (Prerequisite)
Before any pipeline can run, the repository must have access to organization-level secrets. 

**Important:** Microservices are typically Private repositories. You must ensure that Organization Secrets have their Visibility set to **"All repositories"** or **"Selected repositories"** (including the new microservice). If set to "Public repositories", private services will receive empty strings!

Required Secrets:
* `ALERT_EMAIL`
* `BREVO_API_KEY`
* `DOCKER_TOKEN`
* `DOCKER_USERNAME`
* `SNYK_TOKEN`
* `SONAR_HOST_URL`
* `SONAR_TOKEN`
* `HELM_REPO_PAT` (For CD)

## 2. SonarQube (SAST) Setup
1. Log into your SonarQube Web UI.
2. Navigate to **Projects** -> **Add Project** -> **Manually**.
3. Set the **Project Key** and **Display Name** to exactly match your service name (e.g., `auth-service`).
4. In your repository root, create a `sonar-project.properties` file:
   ```ini
   sonar.projectKey=auth-service
   sonar.projectName=Auth Service
   sonar.sources=.
   sonar.exclusions=**/*.md,**/*.yml,**/*.yaml,Dockerfile,requirements.txt,**/.github/**
   # Add this if it's a python service:
   sonar.python.version=3.12
   ```

## 3. Docker Build Context & Dependencies
If you are extracting a service from an old monorepo into a standalone repository:
1. Ensure you copy the `shared/` folder from the old backend root into the new repository root.
2. Ensure you copy the `requirements.txt` (or `package.json`) into the new repository root.
3. Update the `Dockerfile` so that it copies the files into the correct expected paths inside the container (e.g., `/app/services/auth_service/`) so relative Python imports don't break.

## 4. Snyk (SCA) & Trivy Configuration
The pipeline handles Snyk and Trivy automatically using reusable templates. 
* **For Node.js apps:** The pipeline will look for `package-lock.json`. 
* **For Python apps:** The pipeline will look for `requirements.txt`. 
* You just need to ensure you pass the correct `runtime` variable in your caller workflow (see step 5).

## 5. Write the Caller Workflow
Create `.github/workflows/ci.yml` (or `ci-<service>.yml`). We use a modular approach calling templates from `QuickHaulTransits/quickhaul-templates`.

```yaml
name: CI/CD — Your Service

on:
  push:
    branches: [ develop, main ]
  pull_request:
    branches: [ develop, main ]
permissions:
  contents: write

jobs:
  sast:
    if: github.event_name == 'pull_request'
    uses: QuickHaulTransits/quickhaul-templates/.github/workflows/_sast.yml@main
    with:
      service-path: .
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      SONAR_URL: ${{ secrets.SONAR_HOST_URL }}

  sca:
    needs: [sast]
    if: github.event_name == 'pull_request'
    uses: QuickHaulTransits/quickhaul-templates/.github/workflows/_sca.yml@main
    with:
      service-name: your-service
      service-path: .
      runtime: python # CHANGE TO 'node' IF NODE.JS
    secrets:
      SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

  notify-snyk:
    needs: [sca]
    if: needs.sca.outputs.critical-found == 'true'
    uses: QuickHaulTransits/quickhaul-templates/.github/workflows/_notify.yml@main
    with:
      service-name: your-service
    secrets:
      BREVO_API_KEY: ${{ secrets.BREVO_API_KEY }}
      ALERT_EMAIL: ${{ secrets.ALERT_EMAIL }}

  build:
    needs: [sast, sca]
    if: github.event_name == 'pull_request'
    uses: QuickHaulTransits/quickhaul-templates/.github/workflows/_docker-build.yml@main
    with:
      service-name: your-service
      service-path: .

  notify-trivy:
    needs: [build]
    if: needs.build.outputs.trivy-critical == 'true'
    uses: QuickHaulTransits/quickhaul-templates/.github/workflows/_notify.yml@main
    with:
      service-name: your-service
    secrets:
      BREVO_API_KEY: ${{ secrets.BREVO_API_KEY }}
      ALERT_EMAIL: ${{ secrets.ALERT_EMAIL }}

  publish:
    if: github.event_name == 'push'
    uses: QuickHaulTransits/quickhaul-templates/.github/workflows/_docker-publish.yml@main
    with:
      service-name: your-service
      environment: ${{ github.ref_name }}
    secrets:
      DOCKER_USERNAME: ${{ secrets.DOCKER_USERNAME }}
      DOCKER_PASSWORD: ${{ secrets.DOCKER_TOKEN }}
```

## 6. Code Ownership
Create `.github/CODEOWNERS` to ensure automatic PR review assignment:
```text
* @YourGitHubUsername
```

## 7. GitHub Branch Protection Setup
To enforce the pipeline and code ownership, you must configure separate Branch Protection Rules for `main` and `develop`. Go to your repository on GitHub -> **Settings** -> **Branches** -> **Add branch protection rule**.

### For the `develop` Branch:
1. **Branch name pattern:** Enter `develop`.
2. Check **Require a pull request before merging**.
   * Require at least **1 approval**.
   * Check **Require review from Code Owners** (activates `.github/CODEOWNERS`).
   * Check **Dismiss stale pull request approvals when new commits are pushed**.
3. Check **Require status checks to pass before merging**.
   * Search for and select your CI jobs (`sast`, `sca`, `build`) to ensure broken code cannot be merged.
4. Check **Require conversation resolution before merging**.
5. Click **Create**.

### For the `main` Branch (Production):
1. Click **Add branch protection rule** again.
2. **Branch name pattern:** Enter `main`.
3. Check **Require a pull request before merging**.
   * Require at least **1 or 2 approvals** (depending on your org standard).
   * Check **Require review from Code Owners**.
   * Check **Dismiss stale pull request approvals when new commits are pushed**.
4. Check **Require status checks to pass before merging**.
   * Select your CI jobs (`sast`, `sca`, `build`).
5. Check **Require conversation resolution before merging**.
6. Check **Do not allow bypassing the above settings** (Enforce for administrators) to ensure strict production security.
7. (Optional) Check **Restrict who can push to matching branches** to limit `main` merges to specific release managers.
8. Click **Create**.

## 8. Git Workflow
When developing a new feature:
1. `git checkout -b feature/your-feature`
2. Make changes, `git add .`, `git commit -m "feat: your feature"`
3. `git push -u origin feature/your-feature`
4. Open a Pull Request on GitHub. The PR will trigger SAST, SCA, and Build (Trivy) checks.
5. Once merged to `main`, the `publish` job will build and push the Docker image to Docker Hub.
