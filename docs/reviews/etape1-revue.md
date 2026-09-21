# Étape 1 — Revue du sous-système de traitement

**Objet :** la branche `feat/pixano-worker` au-dessus de `releases/v1.0-alpha` : le worker, la file PostgreSQL, le flux d'événements, le panneau Jobs, le kind `embeddings`, les compose et la CI.
**Référentiel :** `pixano-plan-developpement-backend` (étape 1), `todo-etape1.md` (13 lots), [`docs/specs/backend-processing.md`](../specs/backend-processing.md), [`docs/specs/writing-a-job-kind.md`](../specs/writing-a-job-kind.md).
**Ce document** consolide trois passes : une revue indépendante de l'état à `c607d4db` (lecture intégrale, trois suites de tests, scénarios sur la pile locale, requêtes sur une base jetable de 256 250 chunks), sa seconde passe sur les correctifs (`87c2b9e7`), puis la revue d'architecture menée avec l'architecte, qui a tranché les choix pris seul et les questions ouvertes. Il remplace les deux rapports intermédiaires. Les décisions qu'il rapporte sont consignées, avec leurs raisons, dans le spec ; ici, on garde le constat, ce qui en a été fait, et ce qui reste.

Chaque constat porte son statut d'origine : **vérifié** (exécuté, ou lu dans le code à la ligne près) ou **déduit** (raisonnement non exécuté).

---

## 1. Verdict

Le socle demandé est livré et tient ses treize définitions de fini, avec une exception — la « provenance complète » des embeddings (lot 9) — et des écarts de mécanisme, tous validés par l'architecte (§4). Les propriétés de la file — aucun doublon, aucune perte, reprise sans processus vivant — sont portées par le schéma et par un jeton de garde, testées, et revérifiées par le relecteur à 1 000 chunks sur trois workers et sur le job réel tué en plein vol.

La revue indépendante a trouvé quatre défauts à corriger avant l'étape 2 (D1 à D4) ; ils le sont, chacun avec un test et une vérification sur la pile, ainsi que tous les résidus de la seconde passe. Ce qui reste n'est pas un défaut de l'étape 1 mais de la conception à faire avant l'étape 2 (§6) et des questions que l'étape 4 ouvrira (§7). Un lot de suites de revue, décidé avec l'architecte, est planifié après la fusion (§5).

À la clôture : worker 270 tests, API 60, web 459, `pre-commit run --all-files` sans réécriture.

---

## 2. Les lots

| Lot                         | DoD tenue                   | Manque, écart, ou livré en plus                                                                                                                                                                                                    |
| --------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0 — Compose                 | oui                         | En plus : `.env.example` commenté, politique de redémarrage, `stop_grace_period`. L'inférence de la démo est un fork (Q2)                                                                                                          |
| 1 — Schéma                  | oui, par un autre mécanisme | Pas de migrations versionnées : fichier idempotent, `SCHEMA_VERSION`, refus au démarrage (écart B)                                                                                                                                 |
| 2 — Enqueue + `SKIP LOCKED` | oui, par un autre mécanisme | L'application enregistre une demande, le worker planifie et insère les chunks en une transaction (écart C). Le test partage 200 chunks et non 1 000 (écart D) ; revérifié à 1 000 sur trois workers : 344/320/336, 1 000 distincts |
| 3 — Runner + job factice    | oui                         | En plus : `planning` sous bail, taxonomie des pannes, quarantaine                                                                                                                                                                  |
| 4 — `LISTEN/NOTIFY` → SSE   | oui, après correctifs       | D2, D3, D6                                                                                                                                                                                                                         |
| 5 — UI minimale             | oui, après correctifs       | D4, C2                                                                                                                                                                                                                             |
| 6 — Écritures idempotentes  | oui                         | Nettoyage des restes borné à 32 rangs (Q6) ; suppression par identifiants dérivés et non « scopée (job, item) » (écart I)                                                                                                          |
| 7 — Contrats + registre     | oui                         | `review_status` non livré : les schémas n'ont pas le champ (écart F)                                                                                                                                                               |
| 8 — Résolveur de médias     | oui                         | En plus : repli sur les octets pour les datasets `embed` (écart A)                                                                                                                                                                 |
| 9 — Kind embeddings         | partiellement               | « Provenance complète » non tenue : ni modèle ni job par ligne (écart E). Le « sémaphore » est la concurrence du moteur (écart G)                                                                                                  |
| 10 — Mesure de débit        | oui                         | Le mécanisme de « plus gros = plus lent » n'est pas établi ; le spec le dit                                                                                                                                                        |
| 11 — Durcissement           | oui, après correctifs       | D1, D9                                                                                                                                                                                                                             |
| 12 — Démo scriptée          | oui                         | Rejouable par un tiers à condition d'avoir le fork de l'inférence (Q2)                                                                                                                                                             |

---

## 3. Constats et ce qui en a été fait

### 3.1 Défauts

|        | Constat                                                                                                                                                             | Statut d'origine             | Suite                                                                                                                                                                          |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **D1** | Une exception hors base pendant la planification tuait le worker, qui ne revenait pas : `record_plan` hors du `try`, la boucle ne rattrapait que les pannes de base | important, vérifié           | **Corrigé.** Un plan refusé échoue le job ; une exception dans un tour de boucle est journalisée et survécue                                                                   |
| **D2** | Le flux jetait un événement commité après un identifiant plus grand : les identifiants sont attribués avant le commit                                               | important, mécanisme vérifié | **Corrigé.** Les événements d'état sont écrits par la transaction qui change l'état ; le flux dédoublonne par identifiant vu, le rattrapage relit cent identifiants en arrière |
| **D3** | Une annulation faite par l'API n'émettait aucun événement                                                                                                           | important, vérifié           | **Corrigé.** L'annulation écrit son événement d'état dans sa transaction                                                                                                       |
| **D4** | La raison d'un échec n'était exposée nulle part                                                                                                                     | important, vérifié           | **Corrigé.** L'API expose l'erreur du job ou de son premier chunk en échec, le panneau l'affiche, les raisons du worker sont en anglais                                        |
| **D5** | Un identifiant de job qui n'est pas un uuid répondait 500                                                                                                           | mineur, vérifié              | **Corrigé**, flux d'événements compris (R1) : 404                                                                                                                              |
| **D6** | L'événement terminal était écrit hors de la transaction qui conclut le job                                                                                          | mineur, vérifié              | **Corrigé** avec D2                                                                                                                                                            |
| **D7** | Un worker plein ne reprenait pas les baux expirés                                                                                                                   | mineur, déduit               | **Corrigé.** La reprise tourne sur son intervalle, worker plein ou non                                                                                                         |
| **D8** | `job_kinds` dit « un worker a déclaré », la doc disait « un worker vivant déclare »                                                                                 | mineur, vérifié              | **Doc et message corrigés** (R6). La vivacité des déclarations est pour l'étape 4 (§7)                                                                                         |
| **D9** | La durée maximale d'un chunk ne couvre pas le pire cas légitime de la bissection                                                                                    | mineur, déduit               | Commentaire corrigé. Sur le fond, arbitrage 2 : la limite doit suivre le travail (§6)                                                                                          |

### 3.2 Résidus de la seconde passe

|        | Constat                                                                     | Suite                                                                                                                   |
| ------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **R1** | `GET /jobs/{id}/events` avec un non-uuid répondait 200 puis cassait le flux | **Corrigé** : 404 avant d'ouvrir le flux                                                                                |
| **R2** | L'API exposait la trace de pile du chunk en échec                           | **Corrigé** : la projection retire `trace`                                                                              |
| **R3** | Le compose activait les kinds de démo par défaut                            | **Corrigé** : `false` par défaut, `true` dans `.env.example`                                                            |
| **R4** | La compaction tourne sous le verrou d'écriture du dataset                   | **Ouvert**, consigné au spec ; à mesurer (arbitrage 11)                                                                 |
| **R5** | Un bug persistant dans la boucle devenait une trace par seconde             | **Corrigé** : compté, journalisé toutes les 60 occurrences. Arbitrage 7 : arrêt propre après 60 échecs consécutifs (§5) |
| **R6** | La doc promettait plus que le code sur les workers vivants                  | **Corrigé**                                                                                                             |

### 3.3 Choix relevés

|         | Constat                                                                                          | Suite                                                                                                |
| ------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| **C1**  | `fake` et `label` dans le registre de production                                                 | **Corrigé** : `PIXANO_WORKER_DEMO_KINDS`                                                             |
| **C2**  | Le formulaire ne rendait pas un paramètre `array`                                                | **Corrigé** : liste de scalaires                                                                     |
| **C3**  | Lister les jobs : trois sous-requêtes corrélées par ligne, 168–281 ms à 256 250 chunks           | **Ouvert**, consigné au spec avec ses deux leviers                                                   |
| **C4**  | Une connexion PostgreSQL neuve par requête HTTP                                                  | **Ouvert** ; hors du lot de suites, à mesurer                                                        |
| **C5**  | Une version Lance par écriture, sans compaction                                                  | **Corrigé** : compaction toutes les 64 écritures, anciennes versions purgées après une heure         |
| **C6**  | Restes au-delà de 32 rangs non nettoyés                                                          | **Décidé** (Q6) : remplacement exact par clé, avec le premier kind de détection                      |
| **C7**  | Une seule vue image par enregistrement, choisie par l'ordre de LanceDB                           | Documenté dans le kind. **Reporté** : dépend du grain des embeddings (§6)                            |
| **C8**  | Le bail dérive de la sonde docker                                                                | **Ouvert**, étape 4                                                                                  |
| **C9**  | Identité du worker `hostname:pid`                                                                | Validé. `PIXANO_WORKER_ID` arrive avec le mode manuel (§5)                                           |
| **C10** | Le flux d'un job rejoue tout son historique                                                      | **Ouvert**, consigné au spec                                                                         |
| **C11** | Langues mêlées dans `src/pixano/api/jobs/`                                                       | **Corrigé** : le paquet est en anglais                                                               |
| **C12** | `MAX_LISTED_JOBS` en double                                                                      | **Corrigé**                                                                                          |
| **C13** | `done_tasks` dénormalisé, identifiants `uuid`                                                    | Validés (arbitrages 18 et 19) ; le test réclamé existe                                               |
| —       | Deux workers : un dataset en cache écrasait la table d'embeddings de l'autre (déduit, important) | **Corrigé** : relecture hors cache avant création. Deux créations simultanées restent pour l'étape 4 |

### 3.4 Trouvé pendant la revue d'architecture

| Constat                                                                                                                                                                       | Suite                                                                                                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Une image refusée seule dans son lot — dernier chunk d'une image, ou `chunk_size: 1` — faisait échouer tout le job : le kind prenait « rien n'a été embarqué » pour une panne | **Corrigé en intérim** : la présomption de panne demande au moins deux images. Vérifié sur la pile : 60 chunks d'une image, 57 produites, 3 en quarantaine. Remplacé par la requête témoin (arbitrage 3, §5) |
| Le cache de datasets de l'API n'est pas invalidé à la fin d'un job du worker (déduit)                                                                                         | À vérifier puis corriger (§5)                                                                                                                                                                                |
| Le worker n'écrit pas `view_id` et ne construit pas d'index, contrairement au chemin en processus de l'application                                                            | Conception avant l'étape 2 (§6)                                                                                                                                                                              |

---

## 4. Arbitrages de l'architecte

### 4.1 Sur les choix pris seul pendant l'étape

| #      | Choix                                                        | Décision                                                                                                                                                                             |
| ------ | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1      | Cinq tentatives, délai de 15 s doublé jusqu'à 5 min          | Validé. S'y ajoute un `POST /jobs/{id}/retry` générique ; le bouton viendra plus tard                                                                                                |
| 2      | Durée maximale de chunk, réglage de déploiement              | À remplacer : le kind déclare un poids par chunk à la planification. Mesurer d'abord ; traité avec Q6                                                                                |
| 3      | Panne présumée quand aucun lot ne passe                      | Remplacé par une requête témoin ; si le témoin passe et que les images refusées étaient envoyées par chemin, en renvoyer une en octets pour détecter un montage cassé côté inférence |
| 4      | Panne sans réponse = transitoire, même en pleine bissection  | Validé                                                                                                                                                                               |
| 5      | `restart: on-failure:3`                                      | `unless-stopped`. La décision du lot 1 était « refuser de démarrer avec un message clair », pas « rester arrêté pour de bon » ; la boucle de redémarrage est acceptée                |
| 6      | Pool de threads renouvelé sur place                          | Validé                                                                                                                                                                               |
| 7      | Exception dans la boucle : journal et pause d'une seconde    | Validé, complété : 60 échecs consécutifs → arrêt propre en erreur, et le redémarrage fait le reste                                                                                   |
| 8      | Une table d'embeddings, un modèle                            | Validé. `replace_existing_embeddings` viendra à l'étape 2, sous conditions ; il demande un crochet `prepare` dans le contrat, qui entre dans le lot de suites                        |
| 9      | Ignoré n'est pas en quarantaine                              | Validé. Planifier depuis les images et traiter les vues : reporté, dépend du grain                                                                                                   |
| 10     | Bissection d'un lot refusé                                   | Provisoire. Tickets amont à rédiger ; rien n'est publié sans l'architecte                                                                                                            |
| 11     | Compaction toutes les 64 écritures                           | Commenter la rétention, mesurer sur une table d'annotations, décider de la politique avant les kinds de l'étape 2                                                                    |
| 12     | `chunk_size` 8                                               | Validé. `chunk_size` et taille du lot d'inférence sont deux réglages que ce kind confond ; chronométrage par phase, puis re-mesure                                                   |
| 13     | Concurrence 4                                                | Gardée. Écrire son couplage avec la limite du serveur d'inférence et les délais                                                                                                      |
| 14, 15 | Transaction des événements d'état ; fenêtre de dédoublonnage | Validés                                                                                                                                                                              |
| 16     | Aucun rattrapage sur le flux de tous les jobs                | Validé                                                                                                                                                                               |
| 17     | `running` au premier chunk terminé                           | À changer : `running` juste après la réclamation, dans la même transaction que son événement, sous le verrou de la ligne du job                                                      |
| 18, 19 | `done_tasks` dénormalisé ; identifiants `uuid`               | Validés                                                                                                                                                                              |

### 4.2 Sur les questions de la revue indépendante

|        | Question                    | Décision                                                                                                                                                                                                                |
| ------ | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Q1** | Octets ou chemins           | Rien à changer à l'étape 1                                                                                                                                                                                              |
| **Q2** | Le fork de pixano-inference | Rien n'est poussé en amont pour l'instant. Le fork ne change que l'image (Dockerfile et configuration CPU), aucun code d'inférence. **Docker ne doit pas être le seul mode de déploiement** : item « mode manuel » (§5) |
| **Q3** | Rétention contre provenance | `job_id` reste, comme étiquette opaque `run_id` ; provenance autoportante à l'étape 2                                                                                                                                   |
| **Q4** | Kinds de démo en production | Réglé (C1, R3)                                                                                                                                                                                                          |
| **Q5** | Provenance des embeddings   | Conception avant l'étape 2                                                                                                                                                                                              |
| **Q6** | Le contrat de `replace`     | Remplacement exact par clé, avec le premier kind de détection                                                                                                                                                           |

### 4.3 Sur les écarts au plan et aux lots

Tous validés comme écarts assumés.

|     | Écart                                                                                                                                   |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- |
| A   | Les octets transitent par le worker pour les datasets `embed` et les chemins hors racine                                                |
| B   | Pas de migrations versionnées                                                                                                           |
| C   | L'application enregistre une demande, le worker insère les chunks                                                                       |
| D   | Test de partage à 200 chunks — porté à 1 000 dans le lot de suites                                                                      |
| E   | Provenance des embeddings : le modèle dans le sidecar, pas par ligne                                                                    |
| F   | `review_status` non livré                                                                                                               |
| G   | Le sémaphore d'appels est la concurrence du moteur                                                                                      |
| H   | `running` au premier chunk terminé — changé par l'arbitrage 17                                                                          |
| I   | Lot 6 : suppression par identifiants dérivés et non « scopée (job, item) ». La bonne portée est (kind, enregistrement) ; traité avec Q6 |

---

## 5. Lot de suites de revue — après la fusion

Décidé, non commencé ; une PR de plus sur l'étape 1.

1. `POST /jobs/{id}/retry` (schéma version 5), sans bouton.
2. `running` dès la réclamation.
3. Arrêt propre après 60 échecs consécutifs, `restart: unless-stopped`, démo adaptée.
4. Crochet `prepare` dans le contrat des kinds.
5. Dataset relu hors cache à la planification.
6. Requête témoin et renvoi en octets.
7. Chronométrage par phase, re-mesure 8 / 64.
8. Invalidation du cache de datasets de l'API à la fin d'un job — à vérifier d'abord.
9. Mesure de la compaction sur une table d'annotations, commentaire sur la rétention.
10. Mode manuel : les quatre composants lancés à la main, sans Docker, de bout en bout.
11. Test de partage à 1 000 chunks.

Hors du lot : pool de connexions de l'API, `replace_existing_embeddings`, règle de vue, séparation `chunk_size` / taille de lot.

## 6. Conception avant l'étape 2

- **Les chunks** : dépendances entre chunks, progression interne, limite de durée dérivée d'un poids. Le suivi vidéo par tronçons a besoin des trois ; c'est la seule pièce de moteur que l'étape 2 doit faire en premier.
- **Les embeddings** : le grain — par enregistrement ou par vue, qui est une décision de produit —, le sidecar, une table par modèle, le sort du chemin en processus de l'application, `replace_existing_embeddings`.
- **La provenance autoportante** : modèle, version et paramètres dans la ligne.
- **Le `replace` exact par clé**, de portée (kind, enregistrement).
- **`review_status`.**
- **La politique de compaction** : en fin de job, ou confiée au rôle d'écrivain.
- **Les écritures partielles** : des statistiques en colonnes triables sur des tables existantes n'ont pas d'opération dans le writer.

## 7. Ce que l'étape 4 ouvrira

1. Le plafond d'appels par modèle est impossible avec la réclamation actuelle : `job_chunks` ne porte ni kind ni modèle.
2. `job_kinds` n'a pas de vivacité, et un worker réclame la planification de kinds qu'il ne connaît pas.
3. La sérialisation des écritures est par processus ; deux créations simultanées de la table d'embeddings ne sont pas couvertes ; deux compactions se rencontreront.
4. Le bail et la sonde fichier sont couplés à docker.
5. **Un worker distant accède-t-il directement à PostgreSQL, ou passe-t-il par l'API ?** Question d'ouverture de l'étape.
6. L'équité entre jobs : FIFO par identifiant, un gros job affame les petits.
7. L'invariant « les médias ne transitent pas » reste à mesurer sur un vrai réseau.

Ce qui tiendra sans changement : le jeton de garde `attempts`, `release_own` par identité, la reprise des baux, l'écoute d'événements par processus d'API, le résolveur à deux racines.

## 8. Ce qui est bien fait, et qu'il ne faut pas casser

- **La file tient par le schéma, pas par convention.** États et baux contraints, annulation dans sa colonne, `attempts` comme jeton de garde sur chaque écriture d'un chunk, index partiel qui fond avec le travail.
- **La frontière moteur / kind est réelle.** Trois kinds de forme différente, une suite de contrat qui court sur chacun, un registre déclaré en base.
- **Le spec est honnête** — reports, défauts connus, mesures qui contredisent l'intuition. Le relecteur avertissait qu'il prenait la forme d'un journal ; il a été réécrit par décision à la clôture de cette revue.
- **La robustesse a été éprouvée sur la vraie pile** : panne de base, SIGTERM, saturation des threads, redémarrage de l'inférence.
- **Le compose ne suppose aucune colocalisation** : chaque lien est une adresse.
- **Le panneau Jobs est sobre** : composants sans logique, un seul flux pour tous les jobs.

## 9. Scénarios exécutés sur la pile locale

Inférence CPU, concurrence 4 ; état de démo restauré après chaque passe.

| Scénario                                                                        | Résultat                                                                                                                   |
| ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Trois workers se partagent 1 000 chunks                                         | 344 / 320 / 336, 1 000 distincts, 0 restant                                                                                |
| Requêtes à 256 250 chunks (41 jobs)                                             | liste des jobs 168–281 ms, `SETTLE` 0,2 ms, `OUTCOME` 0,5 ms, `CLAIM` 0,4 ms                                               |
| Énumération des 26 766 enregistrements de nuScenes à la planification           | 0,11 s                                                                                                                     |
| Inférence : modèle inconnu / chemin absent / chemin hors racine / chemin valide | 404 / 500 / 500 / 200                                                                                                      |
| Job d'embeddings réel, worker tué en `SIGKILL` à mi-course puis redémarré       | 4 chunks repris ; 96 chunks à une tentative, 4 à deux ; `done`, 400 vecteurs, 400 enregistrements distincts, dimension 512 |
| Kind qui planifie un chunk sans tâche, après correctif                          | la boucle survit, job en `error` avec sa raison, bail rendu                                                                |
| Deux jobs réels en concurrence 4, après correctif                               | `pending`, `running`, `done` dans l'ordre des identifiants ; 53 événements en table, 53 sur le flux                        |
| Worker arrêté, flux ouvert, annulation, après correctif                         | événement `cancelled` reçu                                                                                                 |
| 64ᵉ écriture d'une table                                                        | 63 fragments fusionnés en 1                                                                                                |
| Images abîmées, chunks d'une image, après correctif                             | `done`, 57 produites, 3 en quarantaine                                                                                     |
