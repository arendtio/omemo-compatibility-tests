# Tigase XMPP Server for OMEMO interoperability smoke tests

Tigase requires a one-time web installer at http://localhost:8080 when using the
default Docker image without a pre-baked `etc/` tree.

## Automated CI

Server-matrix Tigase tests are skipped unless `OMEMO_TIGASE_READY=1` is set after
you complete the web installer and register `alice` / `bob` on `localhost`.

## Manual setup

```bash
docker compose -f docker/tigase/docker-compose.yml up -d
# Open http://localhost:8080 — complete installer (admin/tigase)
# Register users alice and bob with passwords alicepass / bobpass
export OMEMO_TIGASE_READY=1
python3 scripts/run-server-matrix.py --profile tigase
```

For open PEP access on `eu.siacs.conversations.axolotl.*` nodes, configure pubsub
access_model to `open` in the Tigase pubsub module settings during setup.
