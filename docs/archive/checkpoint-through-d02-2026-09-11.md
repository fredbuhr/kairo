# KAIRO — clôture D02, 11 septembre 2026

Archive historique ; seule la prochaine action de [PROJECT_STATE](../../PROJECT_STATE.md) fait foi.

## Livraison complète

D02 est terminé par #85 (budgets IA) et [#86](https://github.com/fredbuhr/kairo/pull/86)
(reste du lot en une PR). Base `cc550150664b1c4c11924ad6b486f863831633d6` ;
head `3ed90a8bdd3eafd47d73fe21b8e2eddf3e5b1c2c` ; arbre `e3233b9d4cff20263a39574e1ed7e7d53b984ec9`.
Merge ref CI `2af631c5283af7a5ee2d547e7ed7bea5c2d03462` ; merge réel
`8a9787d04cbeb346da86cc82d23dbf2b6dd01b90`. Parents et arbre vérifiés identiques aux attendus.

17/17 workflows du head final ont réussi : neuf PR, huit push. News est filtré par chemins sur push,
et a bien tourné sur le diff cumulé de la PR. Aucun succès d'un ancien head ne remplace cette gate.

| Workflow | Événement | Run | Résultat |
|---|---|---|---|
| Autonomous research validation | pull_request | [34611948296](https://github.com/fredbuhr/kairo/actions/runs/34611948296) | success |
| Baseline reproducibility validation | pull_request | [34611948380](https://github.com/fredbuhr/kairo/actions/runs/34611948380) | success |
| Code quality validation | pull_request | [34611948300](https://github.com/fredbuhr/kairo/actions/runs/34611948300) | success |
| Document ingestion validation | pull_request | [34611948315](https://github.com/fredbuhr/kairo/actions/runs/34611948315) | success |
| Foundation validation | pull_request | [34611948382](https://github.com/fredbuhr/kairo/actions/runs/34611948382) | success |
| MCP tool registry validation | pull_request | [34611948381](https://github.com/fredbuhr/kairo/actions/runs/34611948381) | success |
| Multi-user isolation validation | pull_request | [34611948520](https://github.com/fredbuhr/kairo/actions/runs/34611948520) | success |
| News ownership validation | pull_request | [34611948388](https://github.com/fredbuhr/kairo/actions/runs/34611948388) | success |
| UI workspace validation | pull_request | [34611948397](https://github.com/fredbuhr/kairo/actions/runs/34611948397) | success |
| Autonomous research validation | push | [34611944187](https://github.com/fredbuhr/kairo/actions/runs/34611944187) | success |
| Baseline reproducibility validation | push | [34611944203](https://github.com/fredbuhr/kairo/actions/runs/34611944203) | success |
| Code quality validation | push | [34611944197](https://github.com/fredbuhr/kairo/actions/runs/34611944197) | success |
| Document ingestion validation | push | [34611944334](https://github.com/fredbuhr/kairo/actions/runs/34611944334) | success |
| Foundation validation | push | [34611944156](https://github.com/fredbuhr/kairo/actions/runs/34611944156) | success |
| MCP tool registry validation | push | [34611944206](https://github.com/fredbuhr/kairo/actions/runs/34611944206) | success |
| Multi-user isolation validation | push | [34611944229](https://github.com/fredbuhr/kairo/actions/runs/34611944229) | success |
| UI workspace validation | push | [34611944327](https://github.com/fredbuhr/kairo/actions/runs/34611944327) | success |

## Preuves ciblées et portée

- [PostgreSQL et JetStream réels](https://github.com/fredbuhr/kairo/actions/runs/34611948382/job/103304549425) :
  budgets #85, jeu de 1000 Tasks, ownership avant LIMIT, curseurs/versions, six rubriques Today,
  invalidité des types de curseur refusée par 422, quotas concurrents, expiration, cache/rejeu,
  échec mémoire terminal, reconstruction bornée à reçus idempotents, outbox sans verrou SQL pendant
  le réseau, rétention et conservation des données, limites du stream et du consumer existant.
- [Build et processus Worker](https://github.com/fredbuhr/kairo/actions/runs/34611948382/job/103304549889) :
  typecheck/build Web, six régressions nouvelles sur attente/timers, continue-as-new, perte de lease,
  arrêt/récupération de l'enfant avant libération, sous-processus mémoire réel en mode stub et
  exclusion des jetons Core/fournisseur. Les dix régressions D01 restent dans la CI Documents.
- Core/Temporal/Worker réels, deux comptes Keycloak, sauvegarde/restauration destructrice en CI
  et vrai SIGKILL Research : réussis dans les gates ci-dessus. Vrai Docling/PDF et Mem0/Graphiti
  restent à prouver en D04 ; leurs fixtures ne sont pas promues en preuve de moteur réel.

Mesure synthétique finale sur le runner GitHub CI, concurrence client 20, deux créneaux configurés :

| Demandes | Temps total | Créneaux actifs |
|---|---|---|
| 1 | 0,005 s | 2 |
| 10 | 0,176 s | 2 |
| 100 | 2,378 s | 2 |
| 1000 | 17,459 s | 2 |

Ceci mesure le refus/l'attente d'admission sur fixtures ; ce n'est ni un débit de vrais moteurs ni
une preuve de 1000 utilisateurs actifs. Les budgets portent sur l'exposition estimée, sans plafond
fournisseur garanti. Le seuil outbox tolère les écritures déjà concurrentes ; les données canoniques,
les reçus d'audit et les obligations financières ne sont pas des déchets à purger.

## Revue et récupération

Une seule branche/PR pour le reste de D02. Les quatre commits sont des points de validation,
pas des sous-lots. La première CI a révélé qu'une entrée expirée gardait sa candidature FIFO :
`requested_at` est maintenant effacé à l'expiration. La revue a ajouté la réconciliation d'un
consumer existant, la réutilisation du client NATS pendant reconnexion et le refus des curseurs
JSON de mauvais type. Toutes ces corrections sont comprises dans le head final testé.

Les procédures de migration/arrêt, observation et reconstruction sont dans [operations](../operations.md).
Prochaine livraison : D03 ; aucun déploiement utilisateur ou appel fournisseur payant n'a été effectué.

## Checkpoint conservé avant clôture

Les anciennes actions de reprise ci-dessous sont historiques et ne doivent pas être exécutées.

### Ancien checkpoint de reprise

Dernière revue : 2026-09-11. **Vérifier GitHub live avant toute action.**

## État canonique établi

- Première tranche D02 intégrée par [PR #85](https://github.com/fredbuhr/kairo/pull/85).
- Merge : `759db57211dcc4960e20cc9486558a88ac063b52` ; base vérifiée : `ceec99309c389aa2f24e30350d0a11d232a99edf`.
- Head final testé : `3a531b967349d61e253c5d7491d95d8ff87901c3` ; **16/16 workflows réussis**.
- Merge ref testé `9c1ac617da9b465e4be2a722dfb0fd75796da70b`, même arbre
  `77933c65a7ecc65d243658827040c4a1cbef04e5` que le head.
- D01 terminé (#84) ; R0–R7 terminé, baseline `r7-baseline-2026-09-11` à `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Dernier jalon produit : G51 Daily Spine. H1–H3 intégrés, baseline images v8 sans dette recensée.
- **D02 reste partiel ; H4 partiel ; H5 non terminé. Nouvelles fonctions produit après D04/H5.**

## Où reprendre

| Champ | Valeur |
|---|---|
| Branche de développement active | `hardening/d02-complete-capacity-and-data` |
| PR active | [#86](https://github.com/fredbuhr/kairo/pull/86) |
| Dernière livraison | **D02 — admission et réservations des appels IA** |
| Dernier lot entièrement terminé | **D01** |
| Prochain travail | **Terminer D02 dans une livraison commune : capacité et volume des données** |
| Première action | Compléter admission globale documents/mémoire avec attente Temporal, pagination SQL/UI, rebuild par lots et rétention ; valider ensemble avant merge |
| Reste D02 | Admission hors model_gateway, SQL assets/pagination/Today, projections par lots, outbox/rétention, observation du backlog et mesure de saturation |
| Scope | Pas de nouveau broker ni de fonction produit ; conserver les invariants budgétaires et SIGKILL |

## D02 — première tranche livrée et vérifiée

- Migration `0013_model_reservations` ; réservations par clé stable, liées à Task/exécution/alias/propriétaire.
- Admission atomique globale/par propriétaire, budgets tâche/jour, HTTP 429 explicite en surcharge.
  Défauts : 8 appels globaux, 2 par propriétaire, 50/10 USD d'exposition quotidienne ; configurables.
- Réservation avant départ, claim utilisable une seule fois ; expiration avant départ renouvelable
  sans double allocation ; expiration après départ libère le créneau et conserve le coût incertain.
- Comptabilité/settlement atomiques, rapprochement tardif, replay d'un ancien coût inconnu sans
  écraser un coût vérifié ; dépassements enregistrés/audités. Visibilité strictement owner-scoped.
- Worker : clé transmise à Core avant fournisseur, délai absolu de 120 s, sortie bornée à 4 096 tokens ;
  retries LiteLLM configurés à zéro ; estimation News explicite de 0,01 USD par défaut.
- Pool DB Core configurable (5 + 5 connexions par processus par défaut). Aucun nouveau service.
- Reproduction initiale : garde canonique autorisant deux fois 0,60 sur un budget de 1,00.
- Local : compilation, diff et reproductibilité. CI PostgreSQL réel : transactions concurrentes,
  deux propriétaires, expiration, round-up, rapprochement, surcoût, limites et migration aller-retour.
  Job `103284177709` ; identités ASGI de test, sans appel fournisseur.
- Isolation publique avec deux vrais comptes Keycloak, Documents, Foundation et vrai SIGKILL Research
  également réussis sur le head final. Aucun échec masqué ni fournisseur payant utilisé.

Preuves des 8 workflows PR (les 8 miroirs push ont aussi réussi) :

- Autonomous research validation — `34605917763` — success ;
- Baseline reproducibility validation — `34605917725` — success ;
- Code quality validation — `34605917806` — success ;
- Document ingestion validation — `34605917722` — success ;
- Foundation validation — `34605917732` — success ;
- MCP tool registry validation — `34605917705` — success ;
- Multi-user isolation validation — `34605917759` — success ;
- UI workspace validation — `34605917873` — success ;

## Limites et récupération

- Estimation réservée et borne en tokens **ne garantissent pas un plafond fournisseur en dollars**.
  Une dépense inconnue n'est jamais effacée pour débloquer artificiellement un budget.
- Vider/arrêter les anciens Workers avant migration 0013, puis mettre à jour Core et Workers ensemble.
  Les anciens handoffs comptables restent acceptés pour reprise ; ils ne créent pas de réservations.
- Après départ ambigu : pas de nouvel appel aveugle ; récupérer les coûts vérifiés et rapprocher
  via le même Task/exécution/clé/alias. Rollback 0012 détruit les réservations : uniquement avant
  dispatch, ou après arrêt, rapprochement et archivage de toutes les obligations.
- Les créneaux couvrent le gateway canonique. Documents, mémoire/embeddings et SDK hors gateway
  ne sont pas couverts ; les limites locales D01 se multiplient avec les réplicas.
- Vrais Docling/PDF, Mem0/Graphiti, modèles et restauration hors hôte restent D04 ; production,
  secrets/egress et topologie restent D03. Capacité réelle et comportement du proxy à mesurer.
- Aucun déploiement utilisateur, achat ni nouvelle fonction Mycelium/Gantt/Brain dans cette tranche.

## Références et branches

- [Plan détaillé](../implementation-plan.md), [roadmap](../roadmap.md), [état produit](../status.md),
  [protocole de reprise](../development-workflow.md), [opérations](../operations.md).
- [Audit initial](../audit-2026-09-11.md), [historique jusqu'à #83](checkpoint-through-pr83-2026-09-11.md),
  [checkpoint D01 archivé](checkpoint-through-d01-2026-09-11.md).
- `hardening/d02-model-admission` et `hardening/d01-bounded-worker-execution` sont **retirées**.
  Les anciennes branches H1–H3b2e et `hardening/h4-task-dispatch-isolation` restent retirées.
- Réservoirs non canoniques : `feat/kairo-test-interface-v1`, `consolidate/g49-research-durable-stages`.
  Inspection/récupération sélective uniquement, jamais reprise ou merge en bloc.

## D02 — livraison groupée en cours

- Base live vérifiée : `cc550150664b1c4c11924ad6b486f863831633d6`, aucune PR ouverte au départ.
- Instruction utilisateur : conserver les lots, éviter leur fragmentation ; travail restant regroupé.
- Inspection : documents/mémoire occupent les activités pendant leur attente ; Mem0 utilise un thread
  non annulable ; assets/documents filtrés après chargement ; Today et rebuild lisent tout ; outbox
  conserve ses verrous pendant NATS. Réservoir : convergence NATS bornée récupérable conceptuellement,
  pagination Today du prototype insuffisante ; aucune admission équivalente retenue.
- Validation prévue : même PostgreSQL réel pour concurrence/leases/pages/maintenance, vrais processus
  contrôlés, UI et toutes intégrations existantes dont SIGKILL. Aucun nouveau service ni fonction produit.

### Point de travail D02 (non encore validé)

Implémentation groupée : migration 0014, admission documents/mémoire, attente Temporal,
processus mémoire annulable, curseurs SQL et contrôles de pagination Projects/Research/Knowledge/Today,
rebuild à reçus idempotents, outbox à claims courts et rétention bornée. Première compilation,
reproductibilité et `git diff --check` réussis ; CI sur le nouveau head encore à lancer.
Ne pas fusionner avant les preuves communes et tous les workflows du head final.
Prochaine action : ouvrir/mettre à jour l'unique PR D02, terminer les preuves de processus et la
procédure d'exploitation, résoudre la CI dans cette même branche, puis vérifier le merge.

PR #86 ouverte au head `629720b0f8d9939f2ead411787584e7ed68b0c6c`, arbre
`edb316db11ae8deb2f7b1b62735f54c6bfa646d9`. Première CI : build/typecheck Web,
qualité, UI et Documents réussis. Contrat PostgreSQL : pagination/Today réussis ; une entrée
expirée gardait son ancienne candidature à la file FIFO. Correction : effacer `requested_at`
à l'expiration, puis ne recandidater qu'à la prochaine demande réelle. CI finale à refaire.

Head suivant `884860a6091d7280b8ac14735b09228283bf695c`, arbre
`01362800a711fa755df46629d796fc9ddb6b7f2f` : contrat PostgreSQL commun et six preuves Worker
réussis (jobs `103301431517` / `103301431112`). Charge synthétique : 1/10/100/1000 demandes,
concurrence client 20, deux créneaux actifs sans dépassement ; 1000 demandes en 17,232 s sur runner CI,
ce qui n'est pas une capacité mesurée de vrais moteurs/utilisateurs.
Dernière vérification avant clôture : réconcilier aussi le consumer NATS existant (un simple bind
n'applique pas les nouvelles limites), conserver un seul client pendant reconnexion et les prouver
sur JetStream réel. Puis refaire les gates du head final et clôturer D02 dans la même PR #86.

Le head `9f32e6792cbb585d738a6468dab0c54d549fda4f` valide aussi les limites JetStream
et la mise à jour d'un consumer durable existant (job `103303522635`). Dernier correctif de
revue : refuser par HTTP 422 les curseurs JSON valides dont l'identifiant/type est incorrect,
au lieu de laisser remonter une erreur Python 500. Contrat PostgreSQL étendu ; attendre tous
les workflows du nouveau head avant clôture. Aucune nouvelle fonction ni sous-lot ajouté.

