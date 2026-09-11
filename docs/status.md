# KAIRO — état fonctionnel vérifié

Révision : 2026-09-11, base inspectée `4790e1eab979a1f8c4c25459fb1c57dc59e8f977`.
Toujours vérifier le live ; branche/PR/lot actif dans [PROJECT_STATE](../PROJECT_STATE.md).

## Acquis canoniques

- Reset R0–R7 terminé, G51 Daily Spine intégré.
- H1–H3 intégrés : handoff mémoire authentifié, nettoyage, lockfiles et builds figés,
  digests des images recensées. Baseline v8 : zéro référence non épinglée dans son périmètre.
- #82 : attente de complétion mémoire corrigée, fixture sans News parasite ; 16/16 workflows verts.
- #83 : création publique de capacités internes interdite, rattachements d'exécution et rejeu
  MCP protégés ; 18/18 workflows verts dont isolation authentifiée et vrai SIGKILL Research.
- Les huit workflows déclenchés par le checkpoint `4790e1e…` ont ensuite réussi.

## Capacités et limites

| Domaine | Présent dans le code | Ce qui reste à prouver/livrer |
|---|---|---|
| État durable | PostgreSQL, objets SeaweedFS, outbox/NATS, exécution Temporal, migrations jusqu'à `0012_task_planning` | Pagination/rétention, dimensionnement et saturation maîtrisée |
| Identité et actions | Keycloak, ownership, policy/approbations, registre MCP et invocations idempotentes | Production, privilèges internes, egress, budgets atomiques sous concurrence |
| Intelligence | Routing sémantique, recherche bornée, Context Packs, provenance et gateway de modèles | Choix utilisateur des modèles/clés, UX Agents/Skills, preuve coûts et vrais moteurs |
| Documents et mémoire | Ingestion/version/chunks, recherche/inspection Web, projections mémoire reconstruisibles | CI Documents emploie le fallback texte, mémoire emploie des stubs ; vraie intégration Docling/Mem0/Graphiti à mesurer en D04 |
| Cockpit | Panneaux persistés par sujet, Command Center, Projects, Today, Research, News, Knowledge | Design Mycelium complet, réglages, attention et parcours cohérents |
| Planification | Priorité, dates prévues/échéance, PATCH owner-scoped, Today/fuseaux | Gantt, calendrier complet, dépendances/jalons/Kanban et récurrences |
| Graphes | Relations canoniques, interfaces dans `packages/graph` | Mindmap 2D éditable et rendu Mycelium 3D absents du `main` inspecté |
| Realtime/Desktop/voix | Scaffolds ou moteurs configurés | Auth/persistence collaboration, Sidecar, permissions appareil et parcours vocal |
| Finance/Crypto/Home/Dev | Moteurs déclarés/configurés et profils | Adaptateurs KAIRO, policy, workspaces et parcours réels |
| Exploitation | Sauvegarde/restauration destructrice testée en CI, overlays de production | Restauration hors hôte, vrais moteurs, charge, sandbox et lancement commercial |

## Périmètre de confiance

KAIRO a un socle et un cockpit initial utilisables en développement, pas encore l'ensemble du
produit Mycelium/Gantt/Brain. Des tests contrôlés prouvent des invariants précis ; ils ne certifient
ni tous les moteurs réels, ni toutes les frontières de production, ni 1 000 utilisateurs.
H4 reste partiel et H5 n'est pas terminé. Le [plan D01–D22](implementation-plan.md) conduit au
pilote central D13, puis aux extensions et à la distribution.

L'[audit du 11 septembre](audit-2026-09-11.md) contient les preuves initiales, les services et
les risques classés. L'[historique jusqu'à #83](archive/checkpoint-through-pr83-2026-09-11.md)
conserve les SHAs/runs des anciennes gates ; ses anciens « next action » ne sont plus courants.
