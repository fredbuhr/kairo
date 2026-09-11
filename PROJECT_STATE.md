# KAIRO — checkpoint de reprise

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
| PR active | **Aucune** |
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

- [Plan détaillé](docs/implementation-plan.md), [roadmap](docs/roadmap.md), [état produit](docs/status.md),
  [protocole de reprise](docs/development-workflow.md), [opérations](docs/operations.md).
- [Audit initial](docs/audit-2026-09-11.md), [historique jusqu'à #83](docs/archive/checkpoint-through-pr83-2026-09-11.md),
  [checkpoint D01 archivé](docs/archive/checkpoint-through-d01-2026-09-11.md).
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
