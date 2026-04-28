# CI/CD Troubleshooting Guide

This document catalogs common errors encountered while setting up the CI/CD pipeline and explains exactly how to fix them.

## 1. Error: `workflow was not found`
**Symptom:**
```text
Invalid workflow file: .github/workflows/ci.yml
error parsing called workflow "..." -> ".../_trivy.yml@main" : workflow was not found.
```
**Cause & Fix:**
1. **Repository Access:** The templates repository (`quickhaul-templates`) is private. You must go to the templates repository settings -> **Actions** -> **General** -> scroll to **Access** -> enable "Accessible from repositories in the 'QuickHaulTransits' organization".
2. **File Naming/Branch:** Double-check that the reusable workflow actually exists on the branch you specified (e.g., `@main` vs `@feature/templates`) and the filename matches exactly.

## 2. Error: Docker Login or Brevo Email Fails with Empty Secrets
**Symptom:**
```text
Run echo "" | docker login -u "***" --password-stdin
Error: Cannot perform an interactive login from a non TTY device
```
*Or:*
```json
{"message":"Key not found","code":"unauthorized"}
```
**Cause & Fix:**
The secrets evaluated to empty strings. This almost always means a **Visibility Issue** in Organization Secrets.
1. Go to Organization Settings -> **Secrets and variables** -> **Actions**.
2. If the secret Visibility is set to "Public repositories", but your microservice is a "Private repository", GitHub blocks access.
3. Edit the secret and change Visibility to **"All repositories"** or explicitly add your private repository to the allowed list.
4. *Alternative Cause:* Check if you accidentally mapped the wrong secret name in the caller workflow (e.g., mapping `DOCKER_PASSWORD: ${{ secrets.DOCKER_PASSWORD }}` when the org secret is actually `DOCKER_TOKEN`).

## 3. Error: `setup-node` Fails on a Python App
**Symptom:**
```text
Run actions/setup-node@v4
Error: Some specified paths were not resolved, unable to cache dependencies.
```
**Cause & Fix:**
You passed `runtime: node` from your caller workflow to the SCA template, but the repository does not have a `package-lock.json`.
1. Open your `ci.yml` caller workflow.
2. In the `sca` job, change `runtime: node` to `runtime: python`. 
3. This tells the template to use `setup-python` and look for `requirements.txt` instead.

## 4. Error: `docker build` Cannot Find Files
**Symptom:**
```text
COPY requirements.txt .
ERROR: failed to calculate checksum of ref ... "/requirements.txt": not found
```
**Cause & Fix:**
When moving a microservice from a monorepo into a standalone repository, shared dependencies were left behind.
1. Copy the `shared/` folder from your old monorepo into the new standalone repository root.
2. Copy `requirements.txt` into the standalone repository root.
3. Update the `Dockerfile` to copy these files explicitly and ensure your Python paths still align (e.g., copying `.py` files into `/app/services/auth_service/` inside the container if the code expects that directory structure).

## 5. Error: SonarQube Execution Failure
**Symptom:**
```text
ERROR You must define the following mandatory properties for 'Unknown': sonar.projectKey
```
**Cause & Fix:**
SonarQube doesn't know which project this repository belongs to.
1. Create a `sonar-project.properties` file in the root of the repository.
2. Define `sonar.projectKey=your-service` and `sonar.sources=.`.
3. Ensure the project is created in the SonarQube Web UI with that exact Project Key.

## 6. Error: Git Push Fails with `src refspec does not match any`
**Symptom:**
```text
error: src refspec feature/ci-user does not match any
error: failed to push some refs to 'https://github.com/...'
```
**Cause & Fix:**
You made a typo in the branch name when pushing. Use `git branch` or `git status` to verify your current branch name, then ensure your push command perfectly matches it (e.g., `git push -u origin feature/ci-auth`).
