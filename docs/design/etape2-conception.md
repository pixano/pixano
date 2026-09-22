# Étape 2 — Conception avant le premier kind

**Statut :** tranché le 2026-09-22, sauf la question 2 (chunks), en suspens avec le suivi vidéo.
Chaque section garde son cadrage et sa recommandation ; la décision est en tête de section.
Les décisions sont aussi dans [`docs/specs/backend-processing.md`](../specs/backend-processing.md),
et les lots dans [`todo-etape2.md`](./todo-etape2.md).
**Pourquoi maintenant :** l'étape 1 a livré un moteur et un kind d'embeddings ; les kinds de
l'étape 2 — embeddings finalisés, détection, segmentation, NER, statistiques, indexation,
clustering, suivi vidéo — vont chacun buter sur une des six questions ci-dessous. Les trancher
d'abord évite de les trancher kind par kind, en incohérence.
**Ordre :** les questions sont indépendantes, sauf la 1 qui conditionne la 3 (règle de vue) et
la 2 qui conditionne le suivi vidéo. Elles peuvent se prendre dans l'ordre du document.

Ce que chaque section contient : ce qu'il y a aujourd'hui, ce qui en dépend, les options avec
leur coût, et ma recommandation.

---

## 1. Le grain des embeddings — par enregistrement ou par vue

> **Décision :** un embedding par **média** composant l'enregistrement, pas par enregistrement (option B). La recherche retrouve un média par son embedding et rend l'enregistrement complet ; rendre des médias (C) reste possible plus tard. Le chemin en processus de l'API est **gardé pour l'instant**, à nettoyer plus tard.

### Aujourd'hui

- La table `embeddings` porte **une ligne par enregistrement** : `record_id`, `vector`, plus
  `view_id` et `frame_id` que le worker laisse vides (le chemin en processus de l'application,
  `src/pixano/api/embeddings.py`, remplit `view_id`).
- La recherche (`Dataset.search_records`) est **par enregistrement** : elle cherche dans les
  vecteurs, groupe par `record_id` en gardant la meilleure distance, et rend des
  enregistrements. Le code dit lui-même « one vector per record, but group defensively ».
- Le kind d'embeddings embarque **la première vue image** que LanceDB rend pour un
  enregistrement (`_images_of`, `setdefault`). Sur nuScenes, un enregistrement a six caméras :
  une seule est embarquée, sans que rien ne dise laquelle.
- Le modèle vit dans le **sidecar** du dataset (`record_embedding_space`), une table = un
  modèle ; un job avec un autre modèle est refusé.

### Ce qui en dépend

- **La règle de choix de vue** (revue, C7) : un paramètre `view` n'a de sens que si le grain
  reste l'enregistrement. Si le grain passe à la vue, il n'y a rien à choisir.
- **La recherche** : par vue, la recherche « images qui ressemblent à celle-ci » devient
  possible sur un enregistrement multi-vues ; par enregistrement, elle répond « enregistrements
  qui ressemblent ».
- **La vidéo** : une vidéo est un enregistrement avec des milliers de frames. Un vecteur par
  enregistrement demande d'en choisir une (ou de moyenner) ; un vecteur par vue demande
  d'échantillonner.
- **Le chemin en processus de l'application** : il fait la même chose que le worker, avec
  `view_id`, un index vectoriel et un `force` qui supprime la table. Deux chemins pour une
  table, c'est un de trop (question 1bis).
- **La détection d'erreurs de labels** (hors périmètre, mais prévue) : la curation par
  voisinage se fait sur ce que l'annotateur regarde — l'image — donc la vue.

### Options

|              | A — par enregistrement (statu quo) | B — par vue, rendu par enregistrement                        | C — par vue, rendu par vue           |
| ------------ | ---------------------------------- | ------------------------------------------------------------ | ------------------------------------ |
| Table        | 1 ligne / enregistrement           | 1 ligne / vue image, `view_id` rempli                        | idem                                 |
| Recherche    | inchangée                          | inchangée en surface : groupe par `record_id`, meilleure vue | nouvelle : rend des vues             |
| Multi-vues   | une vue choisie par une règle      | toutes les vues                                              | toutes                               |
| Vidéo        | une frame choisie                  | frames échantillonnées, `frame_id` rempli                    | idem                                 |
| Coût étape 2 | règle de vue à écrire              | kind : boucle sur les vues ; recherche : rien                | recherche, explorateur, API à revoir |
| Volume       | N                                  | N × vues (× frames échantillonnées)                          | idem                                 |

### Recommandation : **B**

Stocker par vue, rendre par enregistrement. La table porte déjà `view_id` et `frame_id` — le
schéma a été dessiné pour ça — et la recherche groupe déjà par `record_id`. B ne change ni
l'API ni l'explorateur, supprime la règle de choix de vue (plus rien à choisir), et laisse C
ouvert pour plus tard sans rien jeter. Ce que B décide en creux : **la vidéo est échantillonnée**
à la planification (une frame sur N, N paramètre du kind), et c'est le kind qui le fait, pas
le moteur.

Deux points à trancher avec B :

- **Le volume** sur nuScenes : 26 766 enregistrements × 6 caméras = 160 k vecteurs de 512
  flottants, 330 Mo. Acceptable ; un dataset vidéo se règle par l'échantillonnage.
- **La clé de remplacement** devient (kind, enregistrement, vue) — voir question 3.

### 1bis. Le sort du chemin en processus

`src/pixano/api/embeddings.py` calcule les embeddings dans le processus de l'API. Il
préexiste à l'étape 1. Trois choix : le garder (deux chemins à maintenir, et il viole
l'invariant « un job de 50 000 images ne dégrade pas l'interface »), le faire déléguer au
worker (l'endpoint soumet un job et rend son identifiant — un client existant y perd la
synchronie), ou le retirer. **Recommandation : déléguer**, en gardant l'endpoint comme façade,
et retirer le calcul en processus. L'index vectoriel qu'il construisait devient le kind
d'indexation de l'étape 2 (item 4 du plan), qui a sa place dans un job.

---

## 2. Les chunks — dépendances, progression interne, limite par poids

> **En suspens** avec le suivi vidéo. Option A retenue en principe (un chunk = une vidéo, progression interne, poids par chunk) ; rien n'est construit tant que la vidéo n'arrive pas.

### Aujourd'hui

- Un chunk est **indépendant** : réclamé en FIFO par identifiant, quatre à la fois, sans
  ordre entre chunks d'un même job.
- La **progression** avance à la fin d'un chunk, par `task_count` ; rien n'avance pendant.
- La **limite de durée** est un réglage de déploiement (`PIXANO_WORKER_CHUNK_TIMEOUT_S`,
  30 min), le même pour tous les kinds.

### Ce qui en dépend

Le **suivi vidéo par tronçons** (plan, étape 2, item 5) : la propagation passe par l'endpoint
synchrone de l'inférence, découpée en tronçons tenant chacun sous son délai ; le tronçon N+1
part de l'état du tronçon N ; une vidéo interrompue repart de son début ; la progression est en
frames. Quatre exigences que le moteur ne sait pas tenir :

1. **Ordre** : deux tronçons d'une même vidéo peuvent aujourd'hui tourner en parallèle.
2. **Atomicité par vidéo** : si le tronçon 3 échoue, les tronçons 1 et 2 ne sont pas remis en
   file.
3. **Progression en frames** : un chunk d'une vidéo entière n'avancerait qu'à la fin.
4. **Durée** : une vidéo n'a pas le pire cas d'un lot d'images.

Aucun autre kind de l'étape 2 n'en a besoin : détection, segmentation, NER, statistiques,
clustering sont des lots indépendants. La question ne bloque donc que le dernier kind, mais
elle touche le schéma, donc mieux vaut la prendre avant.

### Options

**A — un chunk = une vidéo.** Le kind fait la boucle sur les tronçons lui-même, dans un seul
chunk. Ordre et atomicité viennent gratuitement (c'est un seul chunk, rejoué du début). Reste
à ajouter : une progression interne (le chunk publie « frame 1 200 / 9 000 ») et une limite
de durée que le kind déclare. Le moteur ne connaît toujours pas les dépendances.

- Coût : un `progress(done)` que le kind appelle, relayé par le moteur en événement
  (`done_tasks` reste absolu : le chunk publie un compte partiel de ses tâches) ; un poids par
  chunk déclaré à la planification (`Chunk.weight`), et une limite = poids × durée unitaire.
- Limite : un chunk de trois heures est exposé trois heures à un arrêt du worker — et le bail
  est rafraîchi, donc c'est tenable — mais un `SIGKILL` à la 2 h 59 refait tout. C'est ce que le
  plan accepte explicitement (« une vidéo interrompue repart de son début »).

**B — chunks chaînés.** Une colonne `after` (le chunk dont celui-ci dépend) et un `group`
(la vidéo) ; `available_at` posé par la fin du précédent ; un échec remet le groupe entier en
file ; `SETTLE` comprend les groupes. Chaque tronçon est un chunk ordinaire, court, rejouable.

- Coût : trois colonnes, la réclamation filtre `after IS NULL OR after done` (l'index partiel
  change), la remise en file d'un groupe, la progression par tronçon vient seule.
- Gain : la reprise ne refait qu'un tronçon, pas la vidéo. Mais **l'état entre tronçons** (le
  contexte de suivi que N+1 reçoit de N) doit vivre quelque part entre deux chunks : dans le
  payload du suivant, écrit par le précédent — c'est un chunk qui modifie un chunk, une
  mécanique nouvelle.

### Recommandation : **A**, avec la progression interne et le poids

Le plan a déjà tranché l'atomicité (« repart de son début ») ; A la donne sans nouvelle
colonne ni état inter-chunks. Le moteur gagne deux choses génériques et petites — une
progression publiée par le kind, et un poids par chunk qui remplace la limite unique — utiles
à tout kind long. B est la bonne réponse si un jour la reprise d'une vidéo de plusieurs heures
devient un problème mesuré ; rien dans A ne l'empêche d'arriver ensuite.

À écrire dans le contrat : `Chunk.weight` (défaut 1 = un lot d'images), et
`reader.progress(done_tasks)` ou équivalent, avec la règle « absolu, jamais un incrément ».

---

## 3. `replace` exact par clé

> **Décision :** un autre modèle **s'ajoute** : la clé de remplacement est (kind, modèle, enregistrement, vue), et relancer le même modèle remplace ses propres lignes. Remplacer à la demande : un paramètre `replace_previous` qui, via `prepare`, efface d'abord les lignes `pending` du kind, tous modèles. Un nettoyage des doublons pourra être un workflow plus tard. Mécanisme : A (delete par filtre), B si Lance le permet.

### Aujourd'hui

`JobWriter.replace` dérive les identifiants des lignes de (kind, clé, rang), écrit, puis
sonde **32 rangs** au-delà pour effacer les restes d'une exécution précédente plus longue. Une
détection qui passe de 100 à 20 boîtes sur une image laisse 48 boîtes fantômes (revue, C6).
La portée demandée par le lot 6 était (job, item) ; la revue a tranché (écart I) : la bonne
portée est **(kind, enregistrement)**, parce qu'un second job doit remplacer les lignes du
premier, pas s'y ajouter.

### Ce qui en dépend

Le premier kind de détection ; et la question 1 : avec un grain par vue, la clé devient
(kind, enregistrement, vue).

### Options

**A — delete par filtre.** `DELETE WHERE source_name = kind AND record_id = X [AND view_id = V]`
puis insertion. Exact, borné, deux opérations Lance par enregistrement (comme aujourd'hui :
`merge_insert` + `delete`).

**B — merge_insert avec `when_not_matched_by_source_delete`.** Une seule opération Lance,
exacte, à condition que le filtre de source soit exprimable (`source_name = kind AND
record_id IN (...)`). À vérifier sur la version de Lance embarquée.

**C — garder la sonde, l'élargir.** Non : la borne reste une borne.

### Recommandation : **A maintenant, B si Lance le permet**

A est sûr et lisible ; B économise une version Lance par chunk (la compaction, question 6, y
gagne). Vérifier B coûte une heure ; si ça passe, prendre B. Dans les deux cas la clé est
celle de la question 1, et `source_name` doit être le **kind**, pas le modèle — le modèle est
dans la provenance (question 4).

Un point à trancher en même temps : **une ré-exécution avec un autre modèle** remplace-t-elle
(même kind, même clé) ou s'ajoute-t-elle ? Avec `source_name = kind`, elle remplace. C'est le
comportement des embeddings (une table, un modèle) ; le garder pour les annotations est
cohérent, et « garder les deux » demanderait une clé qui inclut le modèle, donc une
provenance dans la clé.

---

## 4. La provenance autoportante

> **Décision :** option A — `source_metadata` porte `job_id`, `kind`, `model`, `model_version`, `params`, posés par le writer. Colonnes dédiées quand un filtre par modèle sera un besoin réel.

### Aujourd'hui

Les lignes écrites par un job portent `source_type` (déclaré par le kind), `source_name` (le
kind) et `source_metadata = {"job_id": …}`. Le `job_id` est une **étiquette opaque** (revue,
Q3) : les jobs sont nettoyés par troncature, donc il ne référence rien de durable. Les
embeddings ne portent rien ; le modèle est dans le sidecar.

Le plan demande « la traçabilité de ce que chaque modèle a produit » ; un relecteur doit
savoir quel modèle, quelle version, avec quels paramètres, a produit une boîte.

### Ce qui en dépend

La file de relecture (`review_status`, question 5) : filtrer « les boîtes du modèle X à
relire » suppose le modèle dans la ligne. Et l'étape 6, qui voudra « qui a lancé le job ».

### Options

**A — tout dans `source_metadata`.** `{"job_id", "model", "model_version", "params", "kind_version"}`
en JSON. Aucun changement de schéma, filtrable par LanceDB sur JSON (à vérifier : filtre sur
une chaîne JSON = `LIKE`, pas un vrai filtre).

**B — colonnes dédiées.** `source_model`, `source_model_version` en colonnes, le reste en
`source_metadata`. Filtrable proprement, indexable ; demande une évolution des schémas
d'annotation et de la table d'embeddings.

### Recommandation : **A pour l'étape 2, B quand la relecture le demande**

A suffit pour tracer ; B est nécessaire pour filtrer. La file de relecture de l'étape 2
filtrera d'abord sur `review_status`, pas sur le modèle — B peut attendre qu'un besoin de
filtre par modèle soit réel. Ce que A doit fixer dès maintenant : **le contenu**, écrit par
le writer et non par chaque kind — `job_id` (étiquette), `kind`, `model` (nom tel que
l'inférence le déclare), `model_version` (ce que l'inférence rend ; sinon absent), `params`
(les paramètres validés du job, sans ceux du moteur comme `chunk_size`).

Pour les embeddings : le sidecar garde le modèle (c'est ce que la recherche lit), et la ligne
n'a pas besoin de plus tant qu'une table = un modèle.

---

## 5. `review_status`

> **Décision :** quatre valeurs — `pending`, `accepted`, `corrected`, `rejected`. Corriger garde `source_type = model` et la trace du modèle ; on pourra compter les corrections. Rejeter ne supprime pas. Une ré-exécution ne remplace que les lignes `pending` ; les lignes relues sont figées pour ce kind.

### Aujourd'hui

Absent des schémas. Le plan : « toutes les sorties de pré-annotation arrivent en statut « à
relire », et une file de relecture permet d'accepter, corriger ou rejeter ».

### Ce qui en dépend

Le premier kind de pré-annotation (détection), le panneau de relecture, et l'export (une
boîte rejetée s'exporte-t-elle ?).

### Ce qu'il faut décider

1. **Les valeurs** : `pending` / `accepted` / `rejected`, et une valeur pour ce qu'un humain a
   corrigé (`corrected`, ou `accepted` + `source_type` passé à `human` ?). Ma proposition :
   trois valeurs, et **corriger = accepter** : la ligne corrigée garde sa provenance modèle
   dans `source_metadata` et gagne `source_type = human` — la trace du modèle reste, la
   responsabilité passe à l'humain.
2. **La valeur par défaut** : vide pour une annotation humaine (rien à relire), `pending` pour
   une sortie de modèle. C'est le writer qui pose `pending`, jamais le kind.
3. **Où** : une colonne sur chaque schéma d'annotation (bbox, RLE, keypoints, classification,
   …). Pas sur les embeddings ni les statistiques : on ne relit pas un vecteur.
4. **Rejeter = supprimer ?** Non : une boîte rejetée reste, marquée, pour que la ré-exécution
   du modèle ne la recrée pas comme neuve — et c'est là que ça se croise avec la question 3 :
   un `replace` exact **doit-il écraser une ligne relue** ? Ma proposition : non — le writer
   ne remplace que les lignes en `pending` ; une ligne acceptée, corrigée ou rejetée est
   figée pour ce kind, et une nouvelle exécution la laisse.

Ce dernier point est le vrai choix de produit de cette section : il dit ce qu'une ré-exécution
d'un modèle a le droit de défaire.

---

## 6. La politique de compaction

> **Décision :** statu quo (A) ; bascule hors du verrou (C) si une compaction dépasse la durée d'un chunk ; mesurer à 500 k lignes dès qu'un kind produit ce volume.

### Aujourd'hui

Toutes les 64 écritures d'une table, sous le verrou d'écriture du dataset, dans le chunk qui
déclenche ; versions de plus d'une heure effacées. Mesuré : 0,12 s à 10 k lignes, 0,30 s à
30 k, max 0,9 s, croissant avec la table. Un dataset de 50 000 images × 10 boîtes = 500 k
lignes : de l'ordre de 5 à 15 s par compaction, extrapolé, toutes les 64 écritures — pendant
lesquelles aucun chunk du dataset n'écrit, et l'annotation humaine passe par l'API, qui
n'est pas sous ce verrou mais rencontrera un conflit de commit Lance.

### Options

**A — statu quo** (tous les N chunks). Simple ; le coût est payé par un chunk au hasard.

**B — en fin de job.** Une seule compaction, dans `settle` ou dans un `finalize` du kind (que
la question 4 du contrat a refusé « tant qu'aucun type n'en a besoin » — ce serait le besoin).
Coût payé une fois, mais 6 250 versions accumulées pendant le job, et un job annulé ne
compacte pas.

**C — hors du verrou.** Compacter dans une tâche de fond du worker, en dehors du verrou
d'écriture, en acceptant le conflit de commit Lance (journalisé, rejoué). La compaction Lance
est conçue pour tourner à côté des écritures.

**D — un rôle d'écrivain** (étape 4) : le worker qui possède le dataset compacte quand il veut.

### Recommandation : **A jusqu'à mesure contraire, puis C**

A tient à l'échelle mesurée. Le seuil qui fait basculer : une compaction qui dépasse la durée
d'un chunk. Le passage à C est local au writer (une tâche, un verrou en moins) et ne touche
aucun kind. B est refusé pour la même raison que `finalize` ; D est l'étape 4.

À faire à l'étape 2 : **mesurer à 500 k lignes** une fois qu'un kind de détection produit ce
volume, et fixer le seuil dans la spec.

---

## Ce que l'étape 2 ne tranche pas ici

- **Les écritures partielles** (statistiques en colonnes sur `records`) : le writer écrit des
  lignes entières. Une opération `update_columns(table, key, {col: value})` s'ajoutera avec
  le kind de statistiques ; elle ne dépend d'aucune des six questions.
- **La colonne de groupe versionnée** du clustering : même famille, à concevoir avec ce kind.
- **`chunk_size` / `batch_size`** : à séparer quand un kind sur GPU le demandera.

## Ordre de travail

Voir [`todo-etape2.md`](./todo-etape2.md) : lots 0 à 6, pré-annotation seulement.
