# Kubernetes manifests (local dev learning)

This directory contains **learning-grade** Kubernetes manifests to run the stack on a local cluster (kind/minikube).

- Base resources live under `base/`
- A dev overlay lives under `overlays/dev/`

Apply:

- `kubectl apply -k manifests/overlays/dev`

## Migrations (recommended flow)

To avoid migration races, the `backend` Deployment is configured **not** to run migrations on Pod startup.

- **dev**: the migrate Job is included automatically in `manifests/overlays/dev`.
- **stage/prod**: run migrations **explicitly** either:
	- **manually** (apply a Job when you need it), or
	- via a GitOps tool hook (e.g., Argo CD sync hook) so it runs once per deploy.

Manual run (recommended for learning):

- Apply: `kubectl apply -f manifests/extras/backend-migrate-job.yaml`
- Re-run: `kubectl -n lecture delete job backend-migrate --ignore-not-found` then apply again
- Check: `kubectl -n lecture logs -l app=backend-migrate`

Notes:

- These manifests are intentionally minimal.
- For production, you should introduce Ingress, TLS, secret management, run migrations in a Job, and tighten security settings.
