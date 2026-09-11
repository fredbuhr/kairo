# Nevolium — état fonctionnel vérifié

Révision : 2026-09-11, D03 terminé par #87 ; merge `d8b8025bb9143e49093eaaac3295affefc6fc07f`.
Toujours vérifier le live ; branche/PR/lot actif dans [PROJECT_STATE](../PROJECT_STATE.md).

## Acquis canoniques

- Reset R0–R7 terminé, G51 Daily Spine intégré.
- H1–H4 intégrés dans leurs périmètres ; H5 reste D04. H1–H3 : handoff mémoire authentifié, nettoyage, lockfiles et builds figés,
  digests des images recensées. Baseline v9 : zéro référence non épinglée dans son périmètre.
- #82 : attente de complétion mémoire corrigée, fixture sans News parasite ; 16/16 workflows verts.
- #83 : création publique de capacités internes interdite, rattachements d'exécution et rejeu
  MCP protégés ; 18/18 workflows verts dont isolation authentifiée et vrai SIGKILL Research.
- Les huit workflows déclenchés par le checkpoint `4790e1e…` ont ensuite réussi.

- #84 / D01 : plan D01–D22 et reprise documentés, parsing enfant borné/annulable, streaming limité,
  slots Worker et ressources Compose configurables. Head `45869904808d6216a967978767c19bc4a8f881f3`
  validé par 16/16 workflows, dont dix nouvelles régressions et ingestion/réingestion réelles.

- #85 / D02 partiel : réservations et admission atomiques du gateway IA, limites globales/par propriétaire,
  coûts incertains conservés/rapprochés et visibilité authentifiée. Head `3a531b967349d61e253c5d7491d95d8ff87901c3`
  validé par 16/16 workflows, dont transactions PostgreSQL concurrentes, migration aller-retour et SIGKILL Research.

- #86 / D02 terminé : admission documents/mémoire, attente Temporal et enfants annulables,
  pagination SQL/Web/Today, reconstruction à reçus idempotents, outbox à claims courts et rétention,
  limites JetStream et observation des files. Head `3ed90a8bdd3eafd47d73fe21b8e2eddf3e5b1c2c`
  validé par **17/17 workflows** ; PostgreSQL et JetStream réels, 1000 Tasks et demandes synthétiques,
  six nouvelles preuves Worker et toutes les gates existantes. [Preuves](archive/checkpoint-through-d02-2026-09-11.md).

- #87 / D03 terminé : production/JWT/SQL/ops, lecteur Web à IP vérifiée, topologie optionnelle,
  images applicatives non root et Web statique, modèles inventoriés, CI sans doublons de push de branche.
  Head `d931f9607b662272daf315ddc1988fede28af96c` : **9/9 workflows PR**, dont HTTP/TLS, PostgreSQL et réseau Docker réels.
  [Preuves et limites](archive/checkpoint-through-d03-2026-09-11.md). D04 conserve les vrais moteurs/H5.

## Travail de branche D04 — pas encore canonique

[#88](https://github.com/fredbuhr/nevolium/pull/88) réunit la campagne des vrais moteurs et de reprise.
La même PR porte la transition atomique de l'identité publique et technique vers Nevolium
([ADR-030](decisions/ADR-030-nevolium-canonical-identity.md)) avant le premier déploiement. Les
anciens succès CI qualifient uniquement leurs commits ; le runtime renommé doit être entièrement
revalidé avant installation sur la cible.
Docling/PDF et Mem0/Graphiti en lecture seule sans Internet, inférence locale avec comptabilisation,
arrêt/rejeu/redémarrage d’Ollama et recherche SearXNG ont passé des essais réels CPU sur la branche.
Le head `10cb57c…` passe 9/9 workflows, dont les cinq jobs D04. La restauration sur une autre VM relit
SQL, message JetStream, objet filer et secret OpenBao. [Rapport, mesures et inventaire des modèles](archive/qualification-d04-2026-09-11.md).
Corrections trouvées : bibliothèques natives OCR absentes, écritures techniques Mem0 hors TMPDIR,
configuration OpenBao persistante incompatible avec sa version épinglée. La cible privée reste à qualifier ;
ne pas utiliser les résultats de branche comme une validation de production du main D03.

La campagne réexécutée sur `a5a61db…` passe 9/9 workflows et 5/5 jobs D04.
Le contrôle préalable d’accès D04 vérifie désormais TLS/authentification/routage avant la charge,
avec lectures bornées et diagnostics sans secrets. Six tests HTTP/TLS du runner réussis en CI ;
[portée et reprise serveur](archive/d04-public-access-2026-09-11.md). Aucun serveur utilisateur qualifié par cette fixture.

## Orientation multi-appareil — décidée, non implémentée

[ADR-029](decisions/ADR-029-server-personal-and-offline-clients.md) : serveur prioritaire, même
backend installable sur PC personnel, clients Web/PWA PC/téléphone/tablette et Desktop ultérieur.
Le cache métier hors ligne, les conflits de synchronisation, le packaging personnel grand public et
la qualification graphique mobile restent à livrer. Présence de Three/Tauri/Yjs ne vaut pas validation.

## Capacités et limites

| Domaine | Présent dans le code | Ce qui reste à prouver/livrer |
|---|---|---|
| État durable | PostgreSQL, objets SeaweedFS, outbox/NATS, exécution Temporal, migrations jusqu'à `0014_capacity_and_data`, pagination SQL et rétention technique | Dimensionnement réel, archivage canonique et charge sur matériel identifié |
| Exécution Worker | Parsing hors boucle async, téléchargement/texte/durée bornés, nettoyage timeout/annulation, admission globale/par propriétaire, attente Temporal, enfants annulables | Mesure réelle des moteurs et du matériel en D04 |
| Identité et actions | Keycloak, ownership, policy/approbations, registre MCP et invocations idempotentes | Policies/ingress sur cible réelle D04 ; UX de rapprochement des coûts incertains |
| Intelligence | Routing/recherche, Context Packs et gateway avec admission, estimations réservées, sortie bornée et replay comptable | Choix utilisateur des modèles/clés, UX Agents/Skills, preuve coûts et vrais moteurs |
| Documents et mémoire | Ingestion/version/chunks, recherche/inspection Web, projections mémoire reconstruisibles | CI Documents emploie le fallback texte, mémoire emploie des stubs ; vraie intégration Docling/Mem0/Graphiti à mesurer en D04 |
| Cockpit | Panneaux persistés par sujet, Command Center, Projects, Today, Research, News, Knowledge | Design Mycelium complet, réglages, attention et parcours cohérents |
| Planification | Priorité, dates prévues/échéance, PATCH owner-scoped, Today/fuseaux | Gantt, calendrier complet, dépendances/jalons/Kanban et récurrences |
| Graphes | Relations canoniques, interfaces dans `packages/graph` | Mindmap 2D éditable et rendu Mycelium 3D absents du `main` inspecté |
| Realtime/Desktop/voix | Scaffolds ou moteurs configurés | Auth/persistence collaboration, Sidecar, permissions appareil et parcours vocal |
| Finance/Crypto/Home/Dev | Moteurs déclarés/configurés et profils | Adaptateurs Nevolium, policy, workspaces et parcours réels |
| Exploitation | Sauvegarde/restauration destructrice testée en CI, overlays de production | Restauration hors hôte, vrais moteurs, charge, sandbox et lancement commercial |

## Périmètre de confiance

Nevolium a un socle et un cockpit initial utilisables en développement, pas encore l'ensemble du
produit Mycelium/Gantt/Brain. Des tests contrôlés prouvent des invariants précis ; ils ne certifient
ni tous les moteurs réels, ni toutes les frontières de production, ni 1 000 utilisateurs.
Les budgets réservent des estimations : ils ne garantissent pas un plafond fournisseur en dollars.
D01–D03 et le périmètre H4 associé sont terminés ; D04 porte les preuves de moteurs réels et H5, encore non terminé. Le [plan D01–D22](implementation-plan.md) conduit au
pilote central D13, puis aux extensions et à la distribution.

L'[audit du 11 septembre](audit-2026-09-11.md) contient les preuves initiales, les services et
les risques classés. L'[historique jusqu'à #83](archive/checkpoint-through-pr83-2026-09-11.md)
conserve les SHAs/runs des anciennes gates ; ses anciens « next action » ne sont plus courants.
