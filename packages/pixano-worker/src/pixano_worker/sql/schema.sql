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

-- Ce que les workers savent exécuter. Chacun y déclare son registre au démarrage : c'est la
-- source de vérité pour l'application, qui n'a aucun autre moyen de savoir si un type de job
-- existe — elle ne partage aucun code avec le worker. La question posée à la soumission est
-- « existe-t-il un worker capable de faire ça », pas « cette chaîne est-elle connue ».
CREATE TABLE IF NOT EXISTS pixano_jobs.job_kinds (
    name          text        PRIMARY KEY CHECK (name <> ''),
    -- Le schéma JSON des paramètres du type, publié depuis son modèle pydantic. Il permet à
    -- l'application de refuser des paramètres invalides à la soumission plutôt que de mettre
    -- en file un job qui échouera à l'exécution.
    params_schema jsonb       NOT NULL DEFAULT '{}'::jsonb
                              CHECK (jsonb_typeof(params_schema) = 'object'),
    declared_by   text        NOT NULL,
    declared_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pixano_jobs.jobs (
    -- L'identifiant est produit par la base : ni l'application ni le worker n'ont besoin
    -- d'une bibliothèque d'identifiants pour créer un job.
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                text        NOT NULL CHECK (kind <> ''),
    dataset             text        NOT NULL CHECK (dataset <> ''),
    params              jsonb       NOT NULL DEFAULT '{}'::jsonb
                                    CHECK (jsonb_typeof(params) = 'object'),
    state               text        NOT NULL DEFAULT 'planning',
    -- L'annulation a sa propre colonne. L'instant est gratuit et répond en plus à
    -- « quand l'a-t-on demandée ? » ; `IS NOT NULL` tient lieu de booléen.
    cancel_requested_at timestamptz,
    -- Le bail de la planification. Un job reste en `planning` pendant qu'un worker le découpe ;
    -- si ce worker meurt, le bail expire et un autre reprend la découpe. Sans lui, un job dont
    -- le planificateur tombait restait « en cours » pour toujours, sans un seul chunk.
    planning_until      timestamptz,
    total_tasks         integer     NOT NULL DEFAULT 0 CHECK (total_tasks >= 0),
    done_tasks          integer     NOT NULL DEFAULT 0 CHECK (done_tasks >= 0),
    error               jsonb       CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    -- `planning` précède `pending` : l'application enregistre la demande, le worker exécute le
    -- planificateur du type et insère les chunks. Découper par vidéo ou par image est une
    -- logique du type de job, qui ne s'exécute que côté worker.
    CONSTRAINT jobs_state_valid
        CHECK (state IN ('planning', 'pending', 'running', 'done', 'error', 'cancelled')),
    -- Une annulation ne peut structurellement pas s'écrire dans la charge d'erreur : le
    -- défaut du magasin SQLite est interdit par une contrainte, pas par une convention.
    CONSTRAINT jobs_error_only_when_failed
        CHECK (error IS NULL OR state = 'error'),
    -- Un bail de planification n'a de sens que pendant la planification.
    CONSTRAINT jobs_planning_lease_only_when_planning
        CHECK (planning_until IS NULL OR state = 'planning')
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
    -- Un job relancé (POST /jobs/{id}/retry) rouvre ses chunks en échec sans toucher à
    -- `attempts`, qui doit rester monotone pour servir de jeton de garde : le plancher
    -- marque d'où repart le compte, et les plafonds comparent `attempts - attempts_floor`.
    attempts_floor integer  NOT NULL DEFAULT 0 CHECK (attempts_floor >= 0 AND attempts_floor <= attempts),
    claimed_by  text,
    lease_until timestamptz,
    -- Une panne passagère rend le chunk à la file, mais pas tout de suite : rejoué dans la
    -- seconde contre une inférence qui redémarre, il épuiserait ses tentatives avant qu'elle
    -- soit revenue. Réclamable seulement une fois cet instant passé.
    available_at timestamptz NOT NULL DEFAULT now(),
    -- La dernière erreur, y compris celle d'une tentative qui sera rejouée : c'est ce qu'on
    -- veut lire quand un chunk revient en file pour la troisième fois.
    error       jsonb       CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    -- Le bilan d'un chunk terminé. Une tâche est soit produite, soit écartée parce qu'elle
    -- est sans objet (un enregistrement sans image pour un calcul sur les images), soit en
    -- quarantaine dans `job_items`. Sans ces comptes, un job ne sait dire que ce qu'il a
    -- tenté, jamais ce qu'il a produit.
    produced    integer     CHECK (produced IS NULL OR produced >= 0),
    skipped     integer     CHECK (skipped IS NULL OR skipped >= 0),
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
        CHECK ((state = 'running') = (lease_until IS NOT NULL)),
    -- Le bilan n'existe que pour un chunk terminé : un chunk rejoué ne garde pas celui d'une
    -- tentative précédente.
    CONSTRAINT chunks_outcome_only_when_done
        CHECK ((state = 'done') = (produced IS NOT NULL AND skipped IS NOT NULL))
);

-- La quarantaine : les items qu'un type de job n'a pas su traiter, un par ligne. Seuls les
-- échecs y entrent — un item sans objet est compté dans `skipped`, pas stocké ici, sans quoi
-- un dataset lidar remplirait la quarantaine de relevés qui ne sont pas des erreurs.
-- Une table plutôt qu'un champ du chunk, parce qu'une quarantaine doit pouvoir se relire :
-- « quels items de ce job ont échoué, et pourquoi », pour les corriger ou les rejouer.
CREATE TABLE IF NOT EXISTS pixano_jobs.job_items (
    job_id     uuid        NOT NULL REFERENCES pixano_jobs.jobs (id) ON DELETE CASCADE,
    chunk_id   bigint      NOT NULL REFERENCES pixano_jobs.job_chunks (id) ON DELETE CASCADE,
    -- L'identifiant de l'item dans le dataset, tel que le type de job le désigne.
    item_id    text        NOT NULL CHECK (item_id <> ''),
    reason     text        NOT NULL CHECK (reason <> ''),
    detail     jsonb       CHECK (detail IS NULL OR jsonb_typeof(detail) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    -- Un item n'est en quarantaine qu'une fois par job : un chunk rejoué après la mort de
    -- son worker remplace la ligne au lieu de la doubler.
    PRIMARY KEY (job_id, item_id)
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

-- Les jobs que le worker doit encore découper. L'ensemble est minuscule et se vide seul.
CREATE INDEX IF NOT EXISTS jobs_to_plan_idx
    ON pixano_jobs.jobs (created_at) WHERE state = 'planning';

-- Liste des jobs dans l'interface.
CREATE INDEX IF NOT EXISTS jobs_created_at_idx
    ON pixano_jobs.jobs (created_at DESC);

-- Rattrapage d'un flux d'événements : WHERE job_id = ? AND id > ? ORDER BY id.
CREATE INDEX IF NOT EXISTS job_events_job_idx
    ON pixano_jobs.job_events (job_id, id);
