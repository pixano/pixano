-- =====================================
-- Copyright: CEA-LIST/DIASI/SIALV/LVA
-- Author : pixano@cea.fr
-- License: CECILL-C
-- =====================================

-- Schéma du sous-système de traitement : la file de jobs, l'état d'exécution et les
-- événements de progression. Voir docs/specs/backend-processing.md.
--
-- Ce fichier est idempotent et ne prend AUCUN paramètre. Les deux propriétés sont liées :
-- psycopg n'accepte plusieurs instructions dans un même execute() que sans paramètre (le
-- protocole étendu, utilisé dès qu'on passe une valeur, l'interdit). Le numéro de version
-- n'est donc pas écrit ici — il vit dans SCHEMA_VERSION, côté Python, et une seule source
-- ne peut pas diverger d'elle-même.

-- La file ne se mélange pas à `public`, où l'étape 6 posera comptes et droits d'accès.
CREATE SCHEMA IF NOT EXISTS pixano_jobs;

-- Marqueur de version. La clé primaire booléenne contrainte à `true` rend une seconde
-- ligne impossible : la lecture ne peut jamais être ambiguë.
CREATE TABLE IF NOT EXISTS pixano_jobs.schema_version (
    singleton  boolean     PRIMARY KEY DEFAULT true CHECK (singleton),
    version    integer     NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pixano_jobs.jobs (
    -- L'identifiant est produit par la base : ni l'application ni le worker n'ont besoin
    -- d'une bibliothèque d'identifiants pour créer un job.
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                text        NOT NULL CHECK (kind <> ''),
    dataset             text        NOT NULL CHECK (dataset <> ''),
    params              jsonb       NOT NULL DEFAULT '{}'::jsonb
                                    CHECK (jsonb_typeof(params) = 'object'),
    state               text        NOT NULL DEFAULT 'pending',
    -- L'annulation a sa propre colonne. L'instant est gratuit et répond en plus à
    -- « quand l'a-t-on demandée ? » ; `IS NOT NULL` tient lieu de booléen.
    cancel_requested_at timestamptz,
    total_tasks         integer     NOT NULL DEFAULT 0 CHECK (total_tasks >= 0),
    done_tasks          integer     NOT NULL DEFAULT 0 CHECK (done_tasks >= 0),
    error               jsonb       CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT jobs_state_valid
        CHECK (state IN ('pending', 'running', 'done', 'error', 'cancelled')),
    -- Une annulation ne peut structurellement pas s'écrire dans la charge d'erreur : le
    -- défaut du magasin SQLite est interdit par une contrainte, pas par une convention.
    CONSTRAINT jobs_error_only_when_failed
        CHECK (error IS NULL OR state = 'error')
);

CREATE TABLE IF NOT EXISTS pixano_jobs.job_chunks (
    -- Entier et non uuid : l'index de réclamation portera des millions d'entrées, et des
    -- identifiants croissants lui donnent en prime un ordre FIFO naturel.
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id      uuid        NOT NULL REFERENCES pixano_jobs.jobs (id) ON DELETE CASCADE,
    seq         integer     NOT NULL CHECK (seq >= 0),
    -- Ce que le type de job doit traiter, sous une forme que le moteur n'interprète pas.
    payload     jsonb       NOT NULL DEFAULT '{}'::jsonb
                                    CHECK (jsonb_typeof(payload) = 'object'),
    task_count  integer     NOT NULL CHECK (task_count > 0),
    state       text        NOT NULL DEFAULT 'pending',
    -- Sert deux usages : borner les reprises d'un chunk qui tue son worker, et servir de
    -- jeton de garde — une écriture porte l'`attempts` qu'elle a réclamé, donc un worker
    -- dont le bail a expiré ne peut pas écraser le résultat de son successeur.
    attempts    integer     NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    claimed_by  text,
    lease_until timestamptz,
    error       jsonb       CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    -- `cancelled` existe pour que la requête de réclamation n'ait jamais à joindre `jobs` :
    -- annuler un job bascule ses chunks en attente, ce qui les sort de l'index partiel.
    CONSTRAINT chunks_state_valid
        CHECK (state IN ('pending', 'running', 'done', 'error', 'cancelled')),
    -- Rend idempotente l'insertion des chunks d'un job : un POST rejoué ne double pas le
    -- travail.
    CONSTRAINT chunks_unique_seq UNIQUE (job_id, seq),
    -- Un bail existe exactement pendant l'exécution. Un `done` qui oublierait d'effacer le
    -- sien, ou un `running` sans bail — donc jamais récupérable — sont refusés à l'écriture.
    CONSTRAINT chunks_lease_matches_state
        CHECK ((state = 'running') = (lease_until IS NOT NULL))
);

-- Le journal que relit une interface qui se reconnecte. NOTIFY ne fait que sonner à la
-- porte : sa charge est plafonnée à 8 ko et n'est délivrée qu'aux clients connectés au
-- moment du commit.
CREATE TABLE IF NOT EXISTS pixano_jobs.job_events (
    id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id     uuid        NOT NULL REFERENCES pixano_jobs.jobs (id) ON DELETE CASCADE,
    type       text        NOT NULL CHECK (type IN ('state', 'progress')),
    payload    jsonb       NOT NULL DEFAULT '{}'::jsonb
                                   CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Réclamation : l'index ne porte que les chunks à faire, et fond à mesure que le travail
-- avance alors que la table, elle, conserve tout. La clé est `id`, exactement l'ORDER BY
-- de la requête, donc le parcours est ordonné et SKIP LOCKED avance sans retrier.
CREATE INDEX IF NOT EXISTS job_chunks_pending_idx
    ON pixano_jobs.job_chunks (id) WHERE state = 'pending';

-- Reprise des baux expirés. L'ensemble « en cours » est borné par le nombre de workers
-- multiplié par la taille de lot : l'index reste minuscule.
CREATE INDEX IF NOT EXISTS job_chunks_expired_lease_idx
    ON pixano_jobs.job_chunks (lease_until) WHERE state = 'running';

-- Liste des jobs dans l'interface.
CREATE INDEX IF NOT EXISTS jobs_created_at_idx
    ON pixano_jobs.jobs (created_at DESC);

-- Rattrapage d'un flux d'événements : WHERE job_id = ? AND id > ? ORDER BY id.
CREATE INDEX IF NOT EXISTS job_events_job_idx
    ON pixano_jobs.job_events (job_id, id);
