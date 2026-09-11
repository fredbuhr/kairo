# KAIRO — checkpoint de reprise

Dernière revue : 2026-09-11. **Vérifier GitHub live avant toute action.**

## État canonique établi

- D01 intégré à `main` par [PR #84](https://github.com/fredbuhr/kairo/pull/84), merge `3d37afa77e6aecee87b6001bb81884b7545d9425`.
- Head final validé : `45869904808d6216a967978767c19bc4a8f881f3` ; **16/16 workflows réussis**.
- Base D01 vérifiée : `4790e1eab979a1f8c4c25459fb1c57dc59e8f977`. Ce fichier est un suivi documentaire du merge, pas un SHA à reprendre sans fetch.
- Reset R0–R7 terminé ; baseline `r7-baseline-2026-09-11` à `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Dernier jalon produit : G51 Daily Spine. H1–H3 intégrés, baseline images v8 et dette recensée zéro.
- #82 : merge `6286819f1cf924dd1338311e8e43a1941c496dba`, 16/16 workflows.
- #83 : P0 dispatch/isolation corrigé, merge `b4f7b8e49f0afbe74643f78f12523bf69b4871d1`, 18/18 workflows.
- **H4 partiel ; H5 non terminé. Nouvelles fonctions produit après D04/H5.**

## Où reprendre

| Champ | Valeur |
|---|---|
| Branche de développement active | `hardening/d02-model-admission` |
| PR active | [#85](https://github.com/fredbuhr/kairo/pull/85) |
| Dernier lot terminé | **D01 — Worker disponible et traitements bornés** |
| Prochain lot | **D02 en cours — première tranche : admission et réservation des appels IA** |
| Première action | Inspecter les checks du head live de #85, notamment PostgreSQL, isolation authentifiée et Research SIGKILL ; ne pas extrapoler le succès du premier head |
| Résultat attendu | Travail coûteux admis/attendu/refusé explicitement ; budgets atomiques et requêtes bornées |
| Scope | Une tranche cohérente admission/réservation, puis matérialisation/rétention si le découpage du plan est nécessaire ; pas de nouvelle queue ni de fonction produit |

## D01 — livré et vérifié

- Plan D01–D22 avec dépendances, scénarios de sortie et matrice de couverture ; jalons socle D04,
  visuel D10, pilote quotidien à deux D13. Documentation initiale : `5e8598c423972ba987ee2c00e9d3ffa0d3781a30`.
- Status/roadmap corrigés, historique long archivé, protocole de reprise après nouvelle discussion/incident.
- Parser enfant hors boucle async ; source téléchargée en flux avec borne/digest, texte/résultat bornés,
  timeout/annulation avec kill/reap/nettoyage, heartbeat pendant attente/traitement.
- Slots Worker et capacité document bornés ; CPU/RAM/PIDs Compose configurables. Aucun nouveau service,
  broker, schéma ou migration. Contrats Task/DocumentVersion/chunks et policy/replay préservés.
- Local : compilation, 4 régressions d'attente mémoire, reproductibilité, vrai parser enfant
  fallback/limite texte, liens de documentation et D01–D22 vérifiés.
- CI : 10 nouvelles régressions avec vrais processus contrôlés ; ingestion/réingestion via
  Core/Temporal/Worker ; Foundation complet, isolation authentifiée et Research SIGKILL réussis.
- Head et merge ref testé `591cd01e9ff7145780d2e2a5132e216f3facd7d1` partagent l'arbre
  `a0ff04d9c5da15d3dd3c2e3cde920c842363a2e8`. Merge avec garde de head et main/arbre revérifiés.

Preuves des 8 workflows PR (les 8 miroirs push ont également réussi) :

- Autonomous research validation — `34602654870` — success ;
- Baseline reproducibility validation — `34602654933` — success ;
- Code quality validation — `34602654938` — success ;
- Document ingestion validation — `34602654976` — success ;
- Foundation validation — `34602654968` — success ;
- MCP tool registry validation — `34602655085` — success ;
- Multi-user isolation validation — `34602654942` — success ;
- UI workspace validation — `34602655098` — success ;

## Limites à préserver

- Les documents en attente occupent encore des slots d'activité bornés : équité multi-utilisateur
  et admission globale restent D02. Les limites locales se multiplient avec les réplicas.
- Les chiffres CPU/RAM et les timeouts sont des bornes initiales, pas une capacité mesurée.
- Les tests de parsing sont déterministes et utilisent un processus contrôlé ; vrais PDF/Docling,
  Mem0/Graphiti, modèles locaux/API et restauration hors hôte restent D04/H5.
- Production/secrets/egress et simplification runtime restent D03. Le parser enfant n'est pas une sandbox de sécurité complète.
- Rollback D01 sans migration possible, mais il réintroduit le parsing bloquant ; ne pas revenir
  en arrière pour masquer un échec CI. Suivre le protocole de récupération.
- Aucune nouvelle fonction Mycelium/Gantt/Brain, aucun achat, déploiement ni action financière effectué dans ce lot.

## Références et branches

- [Plan détaillé](docs/implementation-plan.md), [roadmap](docs/roadmap.md), [état produit](docs/status.md),
  [protocole de reprise](docs/development-workflow.md), [opérations et limites](docs/operations.md).
- [Audit initial](docs/audit-2026-09-11.md) ; [historique jusqu'à #83](docs/archive/checkpoint-through-pr83-2026-09-11.md).
- `hardening/d01-bounded-worker-execution` est **retirée** ; ne pas la réutiliser.
- Toutes les anciennes branches H1–H3b2e et `hardening/h4-task-dispatch-isolation` sont retirées.
- Réservoirs non canoniques : `feat/kairo-test-interface-v1`, `consolidate/g49-research-durable-stages`.
  Inspection/récupération sélective uniquement, jamais reprise ou merge en bloc.

## Travail D02 en cours

- Base live vérifiée : `ceec99309c389aa2f24e30350d0a11d232a99edf`, aucune PR ouverte au départ.
- Objectif de cette tranche : réservation atomique avant fournisseur, admission globale/par
  propriétaire, reprise sans double appel/dépense et expiration prudente ; pool DB configurable.
- Reproduction locale du garde canonique : deux estimations de 0,60 sont acceptées sur 1,00
  tant que le ledger reste à zéro. Les deux réservoirs inspectés n'ont pas de réservation.
- Premier head `e7eefa0bbccb3249c77121cb3b93599db917a014` : 8/8 workflows PR réussis,
  dont PostgreSQL concurrent et migration aller-retour (job `103282867108`) et Research SIGKILL.
- Révision préparée : rapprochement suivi d'un ancien heartbeat, renouvellement sûr avant dispatch,
  concurrence monétaire entre deux propriétaires, visibilité avec vrais tokens et estimation News.
  **Revérifier tous les checks sur le head révisé avant merge.**
- Migration 0013 ; vider/arrêter les anciens Workers avant upgrade. Aucune migration sur une
  installation utilisateur, aucun fournisseur payant appelé. Retenir/rapprocher les coûts incertains.
- D02 restant après cette tranche : admission des documents/travaux non IA, SQL/pagination/Today,
  projections par lots, outbox/rétention et mesure de saturation. Ne pas déclarer D02 terminé.
