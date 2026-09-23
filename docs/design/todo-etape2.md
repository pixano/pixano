# Étape 2 — Pré-annotation : les lots

**Périmètre de cette première version :** la pré-annotation seulement — embeddings finalisés,
détection, segmentation, file de relecture — et sa démo. NER, statistiques, indexation,
clustering et suivi vidéo viennent après, dans une seconde version de l'étape. Les décisions
qui les concernent sont prises quand ils arrivent, sauf celles consignées dans
[`etape2-conception.md`](./etape2-conception.md) parce qu'elles engagent le schéma.

Le suivi vidéo est **en suspens** : il demandera au moteur une progression interne au chunk et
une limite de durée par poids (`Chunk.weight`) — option A de la conception, retenue en
principe — et ces deux ajouts ne se font que quand il arrive.

Règles inchangées : un lot à la fois, plan court validé avant de coder, commits atomiques,
chaque correctif avec un test qui échoue sans lui, robustesse vérifiée sur la vraie pile.

| Lot                                  | Contenu                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Définition de fini                                                                                                                                                                                                     |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **0 — Socle**                        | Worker en anglais (commentaires, journaux, tests). `review_status` (`pending`, `accepted`, `corrected`, `rejected`) sur les schémas d'annotation, vide pour une annotation humaine, `pending` posé par le writer. Provenance complète posée par le writer dans `source_metadata` : `job_id`, `kind`, `model`, `model_version`, `params`. `replace` exact par clé (kind, modèle, enregistrement, vue), et la règle « ne remplace que les lignes `pending` ». | Suite de contrat verte sur tous les kinds ; une ligne écrite par un job dit quel modèle, quelle version, quels paramètres ; une sortie qui rétrécit ne laisse aucun reste ; une ligne relue survit à une ré-exécution. |
| **1 — Embeddings finalisés**         | Un embedding par **média** (vue image) et non par enregistrement, `view_id` rempli ; la recherche retrouve un média et rend son enregistrement. Vues multiples (nuScenes : six caméras). `replace_existing_embeddings` via `prepare`, avec confirmation dans le formulaire. Le chemin en processus de l'API (`/embeddings/compute`) reste tel quel pour l'instant.                                                                                          | nuScenes : six vecteurs par enregistrement, recherche inchangée en surface ; relancer avec un autre modèle est refusé sans le paramètre, et le paramètre vide la table une fois, sous bail.                            |
| **2 — Détection**                    | Premier kind « à relire », via pixano-inference. Boîtes écrites en `pending` avec leur provenance. Un second modèle **s'ajoute** ; le même modèle relancé remplace ses propres lignes ; `replace_previous: true` efface d'abord les lignes `pending` du kind, tous modèles, via `prepare`.                                                                                                                                                                  | Job sur Demo shapes : boîtes visibles dans l'explorateur, marquées à relire ; deux modèles coexistent ; une relance ne double rien.                                                                                    |
| **3 — File de relecture**            | Nouvelle interface : accepter, corriger (→ `corrected`, `source_type` reste `model`, trace conservée), rejeter ; filtre par statut ; une ligne rejetée reste, marquée ; export selon statut.                                                                                                                                                                                                                                                                | Relecture en séance sur les boîtes du lot 2 ; une relance du modèle ne touche pas les lignes relues.                                                                                                                   |
| **4 — Segmentation**                 | Masques RLE, même contrat et même circuit que la détection.                                                                                                                                                                                                                                                                                                                                                                                                 | Idem lot 2 avec des masques.                                                                                                                                                                                           |
| **5 — Jobs dans l'interface legacy** | En attendant que la nouvelle interface soit pleinement livrée : soumettre un job, suivre sa progression, voir son bilan, depuis `ui/apps/pixano`. Une exception assumée à la règle « pas de nouvelle fonctionnalité dans la legacy » ; périmètre minimal, sans logique nouvelle (le panneau de `ui/apps/web` sert de référence).                                                                                                                            | Un job d'embeddings ou de détection lancé et suivi depuis la legacy.                                                                                                                                                   |
| **6 — Démo**                         | Import puis embeddings ; détection + masques sur Demo shapes arrivant « à relire » ; relecture en séance ; relance avec un second modèle. Script et doc comme `demo-etape1.md`.                                                                                                                                                                                                                                                                             | Rejouable par un tiers.                                                                                                                                                                                                |

**Ordre :** 0, 1, 2, 3, 4, 5, 6. La file de relecture (3) avant la segmentation (4), pour
valider le circuit complet sur un seul kind.

**Reporté à la seconde version de l'étape 2 :** NER, statistiques (écritures partielles dans
le writer), indexation vectorielle, clustering, suivi vidéo, nettoyage du chemin en processus
de l'API, colonnes dédiées de provenance (quand un filtre par modèle sera un besoin),
politique de compaction (mesurer à 500 k lignes d'abord).

## Relevé par la revue du lot 0 (2026-09-23)

Consigné ici pour ne pas le perdre ; chaque point se traite dans le lot indiqué.

- **Lot 2 — figer n'est pas apparier.** Une ligne relue est figée, mais une relance qui
  détecte le même objet l'écrit à nouveau en `pending`, à côté. Au kind de détection de
  décider s'il apparie (IoU avec les lignes relues) avant d'écrire.
- **Lot 2 ou 3 — une édition humaine d'une ligne `pending` doit la passer en `corrected`.**
  Aujourd'hui l'API met à jour la géométrie et laisse le statut : une relance écraserait la
  correction. À régler avant qu'un utilisateur puisse éditer une pré-annotation.
- **Plus tard — l'aller-retour export/import JSONL perd `review_status` et `source_metadata`**
  mais garde les identifiants : une ligne acceptée réimportée redevient remplaçable.
- **Étape 4 — course entre l'API et le worker** : une relecture faite entre la lecture et
  l'écriture de `replace` peut être écrasée. Le verrou d'écriture ne couvre que le worker ;
  à reprendre avec le rôle d'écrivain.
- **Datasets de l'étape 1** : leurs vecteurs portent l'ancien format d'identifiant, qu'une
  relance ne remplace pas (elle ajoute). Rien n'a été livré avec ; régénérer les datasets de
  démo suffit (`prepare_demo.py`).
