# P1-W3 runtime decision

Date: 2026-09-12

## Decision

User-authored Python strategies execute only through an `ExecutionProvider`. The production provider uses one non-root, one-shot Docker container for each request. The container has no network, a read-only root filesystem, no inherited application environment, no host mounts or socket, no Linux capabilities, `no-new-privileges`, a bounded temporary filesystem, and explicit CPU, memory, process, wall-time, source-size, signal-count, and response-size limits.

The API process performs syntax and policy validation but never evaluates user source. If Docker, the runner image, or the daemon is unavailable, execution returns `EXECUTION_UNAVAILABLE` with HTTP 503. There is deliberately no unsafe local fallback.

## Runtime status

Docker CLI is installed on the reference machine, but the daemon is not running. At the user's direction, no further Docker startup or live container work is required in this package. Unit tests verify the command boundary and fail-closed behavior; live runner-image verification remains unavailable.

## Build command for a deployment environment

`docker build -f backend/docker/studio-runner.Dockerfile -t quant360-studio-runner:1.0 backend`
