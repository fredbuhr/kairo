# KAIRO — checkpoint de reprise

Dernière revue : 2026-09-11. **Vérifier GitHub live avant toute action.**

## État canonique établi

- `main` vérifié à `4790e1eab979a1f8c4c25459fb1c57dc59e8f977` avant le lot courant.
- Reset R0–R7 terminé ; tag `r7-baseline-2026-09-11` à `6cf3647a609bbd8463cb734e87eb4088572bc037`.
- Dernier jalon produit : G51 Daily Spine. H1–H3 intégrés ; baseline images v8, dette recensée zéro.
- #82 fusionnée à `6286819f1cf924dd1338311e8e43a1941c496dba` après 16/16 workflows.
- P0 H4 dispatch/isolation corrigé par #83, merge `b4f7b8e49f0afbe74643f78f12523bf69b4871d1` ;
  head `41a31005885884382674f11913d7b213a7fe7937` validé par 18/18 workflows.
- Les huit workflows du checkpoint `4790e1e…` ont également réussi.
- **H4 partiel ; H5 non terminé. Nouvelles fonctions produit après D04/H5.**

## Lot actif

| Champ | Valeur |
|---|---|
| ID | **D01 — Worker disponible et traitements bornés** (suite H4) |
| Mandat | Plan détaillé durable, documentation cohérente, puis première implémentation ; demande utilisateur du 2026-09-11 |
| Base | `4790e1eab979a1f8c4c25459fb1c57dc59e8f977` |
| Branche | `hardening/d01-bounded-worker-execution` |
| PR | À ouvrir sur cette branche après le premier commit reviewable |
| Objectif | Parsing hors boucle async, exécution bornée et nettoyage à l'annulation/timeout |
| État | Documentation préparée ; implémentation et validation à poursuivre |
| Prochaine action | Implémenter D01, prouver réactivité/limites/nettoyage, exécuter les intégrations finales avant merge |

## Travail et preuves de cette reprise

- Live `main`, PR ouvertes (aucune au départ), branches et huit runs du checkpoint revérifiés.
- AGENTS/checkpoint/code/audit/vision/ancien plan inspectés. Les réservoirs contiennent des
  prototypes graphes ; leur parsing présente le même appel Docling synchrone. Aucun merge de réservoir.
- Plan D01–D22 : dépendances, scénarios de sortie, limites et matrice des besoins dans
  [implementation-plan](docs/implementation-plan.md). Jalons : socle D04, visuel D10, pilote à deux D13.
- Status/roadmap corrigés : R7 n'est plus indiqué comme « next », fonctions installées distinguées
  des fonctions livrées. Historique volumineux préservé en archive, protocole de reprise documenté.
- Docker et les dépendances applicatives ne sont pas disponibles dans ce workspace ; la CI du
  head final doit fournir les preuves d'intégration. Ne pas déclarer D01 terminé sur compilation seule.

## Limites, reprise et point d'arrêt

- D01 ne certifie ni les modèles réels ni la capacité commerciale. Admission équitable/budgets
  atomiques/données : D02 ; production/topologie/egress : D03 ; vrais moteurs et exploitation : D04.
- Pas de migration prévue dans D01 ; conserver Task/DocumentVersion/chunks et politique/replay.
  Les bornes seront configurables/documentées, pas des chiffres de capacité commerciaux.
- Avant de quitter un travail incomplet, remplacer la PR/état/preuves/prochaine action ci-dessus
  avec les faits. Après merge, retirer la branche et pointer vers D02 sans démarrer silencieusement un nouveau lot.

## Références et branches

- [Protocole de reprise](docs/development-workflow.md), [plan détaillé](docs/implementation-plan.md),
  [roadmap](docs/roadmap.md), [état produit](docs/status.md), [maturité composants](docs/component-matrix.md).
- [Audit indépendant](docs/audit-2026-09-11.md) ; [historique exact jusqu'à #83](docs/archive/checkpoint-through-pr83-2026-09-11.md).
- Réservoirs non canoniques : `feat/kairo-test-interface-v1`, `consolidate/g49-research-durable-stages`.
  Inspection/récupération sélective uniquement, jamais reprise ou merge en bloc.
- Toutes les branches H1–H3b2e et `hardening/h4-task-dispatch-isolation` sont retirées.
  Leurs refs inertes peuvent rester ; elles ne sont pas des branches actives.
