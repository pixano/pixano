**Background processing jobs.** Processing over a whole dataset runs as a
job, outside the application and apart from the import and export jobs:
`POST /jobs` queues it in PostgreSQL, and `pixano-worker`, a process of its
own, runs it in chunks, with live progress, cancellation, retry, and a
quarantine of the items that fail. The chunks of a worker that stops are
claimed again once their lease expires. The embeddings job computes a
dataset's embeddings with the inference server. In the new UI
(`ACTIVATE_UI_V1_0`), a Jobs panel starts and follows jobs. The queue is off
unless `PIXANO_DATABASE_URL` is set. `pixano-worker` has no published package
or image yet: jobs need the repository's compose stack (`docker compose up`;
`docker-compose.inference.yml` adds an inference on CPU serving
MobileCLIP2-S2), or a worker installed from a checkout
(`docs/running-by-hand.md`).
