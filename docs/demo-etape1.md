# Step 1 demo — background jobs

**What it shows:** a processing job submitted from the interface, running outside the API
process with live progress; cancelled halfway; its worker killed mid-job and resuming where it
stopped; a real embeddings job going to the end; and, as an appendix, a job that meets broken
images and an inference outage without losing anything.

**Duration:** about 6 minutes for steps 1 to 4 and 4 more for the appendix, once the preparation below
is done. Rehearsed on the local stack: the commands and clicks alone take 3 min 30 s and 3 min 20 s;
the rest is talking.

**Machine:** Docker with at least 8 GB of memory and 8 CPUs allocated. No GPU — the inference
runs a small CLIP model on CPU, at about three images per second.

---

## 0. Preparation — once, before the audience arrives

About 20 minutes the first time, mostly image builds and a model download.

```sh
# The inference server is a sibling repository, used as is: the compose builds its image and
# adds the CLIP embedding plugin on top (see docker-compose.inference.yml).
git clone https://github.com/pixano/pixano-inference.git ../pixano-inference

cp .env.example .env

# Build the four services.
docker compose -f docker-compose.yml -f docker-compose.inference.yml build

# Generate and import the two demo datasets into ./data.
uv run --directory packages/pixano-worker python scripts/prepare_demo.py

# Start everything, then wait until the four services report healthy.
docker compose -f docker-compose.yml -f docker-compose.inference.yml up -d
docker compose ps
```

`prepare_demo.py` needs no sample data: it draws its images and imports them through the Pixano
CLI. It creates:

| Dataset               | Content                                                                     | Used for                          |
| --------------------- | --------------------------------------------------------------------------- | --------------------------------- |
| `Demo shapes`         | 400 images stored inside the dataset (`embed`, the default import mode)     | the demo itself — about 2 minutes |
| `Demo damaged images` | 60 images referenced by path (`uri`), two of them corrupted and one deleted | the appendix — quarantine         |

**Before each run**, start from an empty queue and a worker that has not cached the datasets:

```sh
uv run --directory packages/pixano-worker python scripts/prepare_demo.py
docker compose exec -T postgres psql -U pixano -d pixano -c "TRUNCATE pixano_jobs.jobs CASCADE"
docker compose restart pixano-worker
```

Open <http://localhost:7492> and, in a second window, a terminal at the repository root.

---

## 1. Submit a job from the interface — 1 min

1. In the **Explorer** on the left, click **Demo shapes**. Its 400 records are listed.
2. In the activity bar, click the **Jobs** icon (the last one, a checklist).
3. **Processing** is `embeddings`, **Chunk Size** `8`. Click **Run**.

> The form opens with the **Dataset** it will run on: the one last opened in the Explorer. Check the
> name before clicking Run.

**What to point out:**

- The job appears at once, before any work is done: the application only _records_ the request.
  Splitting it into chunks and running them is the worker's business, in another container.
- The bar moves without the page being refreshed — events are pushed by the database through a
  single server-sent stream.
- The state switches to `running` within a second or two, and the counter climbs by eight — one chunk
  at a time, several in flight.

While it runs, click the **Explorer** icon and scroll through the records of **Demo shapes**: their
thumbnails load and the interface stays responsive. The job runs in `pixano-worker`, never in the
process serving the pages. Click **Jobs** again to come back to the bar.

## 2. Cancel it halfway — 1 min

When the bar is around a third, click **Cancel**.

**What to see:** the job reads `cancelling` at once and the button disappears. A few seconds later —
the time for the chunks in flight to finish — it ends `cancelled`, with a line under the bar such as
`176 produced`.

**What to point out:** nothing is interrupted mid-chunk. The chunks already running finish and
are kept; the ones still waiting leave the queue. The work done is not undone — its vectors are
already in the dataset.

## 3. Kill the worker mid-job — 3 min

Click **Run** again, and when the bar is around a third, in the terminal:

```sh
docker compose kill -s SIGKILL pixano-worker
```

**What to see:** the bar stops. The worker is gone without any chance to clean up — this is a
power cut, not a shutdown.

Wait a few seconds, then:

```sh
docker compose start pixano-worker
docker compose logs --since 1m pixano-worker | grep -E "repris|démarré"
```

**What to see:** the log says `4 chunk(s) repris d'une exécution précédente`, the bar moves
again from where it stopped, and the job ends `done`.

**What to point out:**

- No state was lost: the queue, the progress and the ownership of each chunk live in PostgreSQL,
  not in the worker.
- Only the chunks that were in flight are redone — four, the worker's concurrency. The chunks
  already finished are not.
- Redoing them does not duplicate anything: results are written under an identifier derived from
  the work, so a replay replaces instead of adding.

## 4. The real embeddings job, checked — 1 min

The job of step 3 _is_ the real one: CLIP through `pixano-inference`. Its line reads
`400 produced`.

To show what landed in the dataset — from the repository root, `$PWD` matters because
`uv run --directory` moves the working directory:

```sh
uv run --directory packages/pixano-worker python -c "
import lancedb, numpy as np
t = lancedb.connect('$PWD/data/library/demo_shapes/db').open_table('embeddings').to_arrow().to_pylist()
v = np.array([r['vector'] for r in t])
distinct = len({r['record_id'] for r in t})
print(len(t), 'vectors,', distinct, 'distinct records, dimension', str(v.shape[1]) + ',',
      'norm', round(float(np.linalg.norm(v[0])), 1))
"
```

**What to see:** `400 vectors, 400 distinct records, dimension 512, norm 1.0` — two runs on the
same dataset, one of them cut in the middle, and still exactly one vector per image.

---

## Appendix — failures that are not the end of the job, 4 min

### A. Broken images go to quarantine

1. Click the **Explorer** icon, go back to the dataset list with the arrow next to the dataset
   name, and click **Demo damaged images**. Then **Jobs**, then **Run**.
2. It ends within twenty seconds, reading `57 produced · 3 quarantined`. Click **Show quarantine**.

**What to point out:** three images out of sixty cannot be read — two are corrupted, one was
deleted from disk. Before, one bad image failed its whole chunk of eight. Now the job isolates
the culprits, keeps the fifty-seven others, and says which ones failed and why.

### B. The inference goes down in the middle of a job

Open **Demo shapes** again the same way, run the job, and as soon as the bar has started:

```sh
docker compose -f docker-compose.yml -f docker-compose.inference.yml stop pixano-inference
```

Wait about 30 seconds — the bar stalls — then:

```sh
docker compose -f docker-compose.yml -f docker-compose.inference.yml start pixano-inference
```

**What to see:** the job resumes by itself once the inference is back — reloading its model takes
it about half a minute — and ends `400 produced`, with nothing in quarantine. Allow three minutes
for the whole appendix step.

**What to point out:** an outage is not blamed on the images. The chunks that met it go back to
the queue with a growing delay — 15 s, 30 s, 1 min — which leaves an inference close to four
minutes to restart before a chunk is given up.

---

## If something does not match

| Symptom                                                      | Cause and fix                                                                                                                          |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| "No worker is running" in the Jobs panel                     | `pixano-worker` is not up, or started before PostgreSQL. `docker compose logs pixano-worker`                                           |
| The worker exits at start with "schéma de base incompatible" | the database holds an older queue schema. There is no migration on purpose: drop the queue schema, then restart the worker — see below |
| A job fails at once with "Table 'embeddings' was not found"  | the worker cached a dataset that was recreated underneath it. `docker compose restart pixano-worker`                                   |
| Every job ends `error`, the chunks mention the inference     | `pixano-inference` is not healthy yet — its first start downloads the model. `docker compose ps`, and wait for `healthy`               |
| The bar is much slower than two minutes for 400 images       | Docker has fewer CPUs than expected. The demo still works; allow for it in the cancel and kill steps                                   |

Dropping the queue schema, which recreates it empty at the worker's next start. Prefer it to
`docker compose down -v`, which would also delete the inference's downloaded model weights:

```sh
docker compose exec -T postgres psql -U pixano -d pixano -c "DROP SCHEMA pixano_jobs CASCADE"
docker compose restart pixano-worker
```
