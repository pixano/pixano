# Running the stack by hand

The compose files are the convenient way to run the local stack; they are not the only one.
Every component is a plain process that reads its configuration from the environment, and
this page runs the four of them by hand — PostgreSQL, the inference server, `pixano-worker`
and the application — the way a deployment without Docker would. Nothing in the code assumes
a container: the same variables, the same behaviour.

The one idea to keep in mind is the **media root**. The worker hands the inference server
_paths_ to images, never bytes, so both must see the same storage, each under the root it
declares: `PIXANO_MEDIA_ROOT` for the worker, `PIXANO_INFERENCE_MEDIA_ROOTS` for the
inference. On one machine the two are simply the same directory.

All paths below are absolute; replace `/srv/pixano` with yours.

## 1. PostgreSQL

Any PostgreSQL 14 or later, with a database and a role that may create a schema in it. The
worker installs the queue schema itself on its first start, so nothing else is needed.

```sh
createdb pixano
export PIXANO_DATABASE_URL=postgresql://pixano:changeme@127.0.0.1:5432/pixano
```

## 2. The inference server

A checkout of [pixano-inference](https://github.com/pixano/pixano-inference), its CLIP
embedding plugin, and a model list. The list the demo uses on CPU is in this repository:

```sh
git clone https://github.com/pixano/pixano-inference.git ../pixano-inference
cd ../pixano-inference
uv sync
uv pip install ./packages/pixano-inference-clip
cd -

PIXANO_INFERENCE_MEDIA_ROOTS=/srv/pixano/data/media \
  uv run --directory ../pixano-inference pixano-inference \
  --host 127.0.0.1 --port 7463 --config "$PWD/docker/inference/models.cpu.py"
```

`PIXANO_INFERENCE_MEDIA_ROOTS` is the directory under which the server accepts image paths.
Wait for `http://127.0.0.1:7463/health` to answer; the first start downloads the model.

## 3. The worker

```sh
export PIXANO_DATABASE_URL=postgresql://pixano:changeme@127.0.0.1:5432/pixano
export PIXANO_INFERENCE_URL=http://127.0.0.1:7463
export PIXANO_LIBRARY_DIR=/srv/pixano/data/library
export PIXANO_MEDIA_ROOT=/srv/pixano/data/media
export PIXANO_INFERENCE_MEDIA_ROOT=/srv/pixano/data/media
# Stable across restarts, unique among live workers: it is how a restarted worker takes its
# own chunks back at once instead of waiting for their lease to expire.
export PIXANO_WORKER_ID=worker-1

uv run --directory packages/pixano-worker pixano-worker
```

Optional: `PIXANO_WORKER_CONCURRENCY` (chunks in flight, default 4),
`PIXANO_WORKER_CHUNK_TIMEOUT_S` (default 1800), `PIXANO_WORKER_DEMO_KINDS=true` for the
`fake` and `label` kinds, `PIXANO_WORKER_HEARTBEAT` (the file the worker touches to say it is
alive, `/tmp/pixano-worker.heartbeat` by default).

The worker refuses to start against a queue schema of another version and says what to do;
there is no migration on purpose (see `docs/specs/backend-processing.md`, §5).

## 4. The application

```sh
export PIXANO_DATABASE_URL=postgresql://pixano:changeme@127.0.0.1:5432/pixano
export PIXANO_MEDIA_ROOT=/srv/pixano/data/media
# The Jobs panel lives in the new UI, which the app serves only when this is true.
export ACTIVATE_UI_V1_0=true

uv run pixano init /srv/pixano/data   # once
uv run pixano server run /srv/pixano/data --port 7492 --pixano-inference-url http://127.0.0.1:7463
```

Open <http://localhost:7492> and switch to the new UI with the button in the header. Its Jobs
panel shows the worker's kinds; a job submitted there is picked up by the worker started in
step 3.

## The demo, by hand

`docs/demo-etape1.md` prepares its datasets with a script that references the damaged images
by path. That path must be the worker's media root:

```sh
uv run --directory packages/pixano-worker python scripts/prepare_demo.py \
  --data-dir /srv/pixano/data --media-dir /srv/pixano/data/media --media-root /srv/pixano/data/media
```

Then the demo runs as written, with `kill -9` on the worker's process where it says
`docker compose kill`, and a restart of the worker where it says `docker compose start`.

## Stopping

`SIGTERM` (or Ctrl-C) stops the worker cleanly: it stops claiming, gives the chunks in flight
30 s to finish, hands back what still runs, and exits. A worker killed outright leaves its
chunks to their lease, two minutes, unless the next worker carries the same
`PIXANO_WORKER_ID`, in which case it takes them back at once.
