# KAIRO — checkpoint de reprise

Dernière revue : 2026-09-11. **Vérifier GitHub live avant toute action.**

## Source canonique vérifiée

- **D02 terminé**, via #85 puis [#86](https://github.com/fredbuhr/kairo/pull/86).
- Merge #86 : `8a9787d04cbeb346da86cc82d23dbf2b6dd01b90` ; base `cc550150664b1c4c11924ad6b486f863831633d6`.
- Head final testé : `3ed90a8bdd3eafd47d73fe21b8e2eddf3e5b1c2c` ; **17/17 workflows réussis** (9 PR, 8 push).
- Merge ref testé : `2af631c5283af7a5ee2d547e7ed7bea5c2d03462` ; même arbre
  `e3233b9d4cff20263a39574e1ed7e7d53b984ec9` que le head et le merge réel ; parents vérifiés.
- Le commit de clôture qui porte ce checkpoint ne modifie que la documentation ; vérifier son
  identité depuis GitHub et son diff contre le merge ci-dessus. Ne pas confondre ce commit avec le head de code testé.
- D01 terminé (#84), reset R0–R7 terminé ; dernier jalon produit G51 Daily Spine.
  H1–H3 intégrés, baseline images v8 sans dette recensée. **H4 partiel ; H5 non terminé.**

## Où reprendre

| Champ | Valeur |
|---|---|
| Branche / PR de développement active | **Aucune** |
| Dernier lot entièrement terminé | **D02 — admission, budgets et volume des données** |
| Prochain lot | **D03 — déploiement sûr et topologie utile** |
| Première action | Vérifier main/PR live, lire D03 du plan, auditer les gardes production/secrets/JWT/egress et les consommateurs de services ; construire une livraison D03 cohérente depuis main |
| Critère de sortie D03 | Configurations/destinations interdites refusées, topologie minimale justifiée et gates préservées |
| Méthode | Une livraison cohérente par lot ; commits/checklists internes pour reprise, sans nouveaux sous-lots sauf obstacle démontré |
| Limite | Ne pas commencer les fonctions produit D05–D10 avant D04/H5 |

## Livré et prouvé en D02

- Réservations IA atomiques, quotas et budgets par propriétaire ; conservation/rapprochement
  des dépenses inconnues, absence de redépart aveugle ; pool SQL configurable (#85).
- Documents et mémoire : admission PostgreSQL partagée, backlog borné, attente Temporal,
  leases et rapports protégés contre les anciennes tentatives ; cache des résultats terminés.
- Mémoire dans un enfant annulable ; arrêt/récupération avant libération ; limites d'activités
  conservant de la place pour le travail léger. Projections en échec rendues terminales.
- Collections filtrées/paginées en SQL, Today borné par rubrique ; pagination Web et sélection
  des anciens objets par ID. Rebuild mémoire à watermark et reçus idempotents, CLI de reprise.
- Outbox à claims courts hors réseau, rétention technique bornée, observation des files ;
  limites JetStream/consumer existant réconciliées et reconnexion sans multiplication des clients.
- CI du head final : PostgreSQL/JetStream réels, 1000 Tasks, rafales 1/10/100/1000 à concurrence 20,
  six nouvelles preuves Worker, dix régressions D01, Web build/typecheck, comptes Keycloak,
  Documents/mémoire/Temporal, sauvegarde/restauration et vrai SIGKILL Research.
  Jobs ciblés : `103304549425`, `103304549889`. [Preuves archivées](docs/archive/checkpoint-through-d02-2026-09-11.md).

## Limites et reprise

- Une estimation réservée ne garantit pas un plafond fournisseur en dollars. Ne jamais effacer
  une obligation inconnue pour débloquer un budget. Le seuil outbox tolère les transactions déjà concurrentes.
- Les mesures CI sont synthétiques ; elles ne prouvent ni vrais moteurs ni 1000 utilisateurs actifs.
  Docling/PDF, Mem0/Graphiti, modèles réels, capacité sur matériel identifié et restauration hors hôte : D04.
- Migration `0014_capacity_and_data` : arrêter/drainer les anciens Workers et Core, migrer puis
  redémarrer des versions/configurations compatibles. Ne pas effacer une lease dont l'enfant peut vivre.
  Downgrade 0013 uniquement sans travail lourd actif ; 0012 supprime aussi les réservations financières.
- Reprise mémoire : conserver l'identité du workflow/Task ; pour reconstruire, utiliser
  `scripts/ops/rebuild_memory.py` et son même checkpoint. Au-delà de la fenêtre NATS de 14 jours,
  reconstruire depuis les messages canoniques. Procédures dans [operations](docs/operations.md).
- Aucun déploiement utilisateur ni achat/appel fournisseur payant effectué dans #86.

## Références et branches

[Plan D01–D22](docs/implementation-plan.md) · [roadmap](docs/roadmap.md) · [état produit](docs/status.md) ·
[protocole de reprise](docs/development-workflow.md) · [architecture](docs/architecture.md).

`hardening/d02-complete-capacity-and-data`, `hardening/d02-model-admission` et les branches D01/H1–H4
précédentes sont **retirées**. Elles ne sont pas des lignes de développement à reprendre.
Réservoirs non canoniques : `feat/kairo-test-interface-v1`, `consolidate/g49-research-durable-stages` ;
inspection/récupération sélective uniquement, jamais merge en bloc.
