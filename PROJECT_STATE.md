# KAIRO — checkpoint de reprise

Dernière revue : 2026-09-11. **Vérifier GitHub live avant toute action.**

## Source canonique vérifiée

- **D03 terminé**, [PR #87](https://github.com/fredbuhr/kairo/pull/87), une seule livraison.
- Merge réel `d8b8025bb9143e49093eaaac3295affefc6fc07f` ; base `ec38ce3b8c479be9ff56df36a24e7ee895754ada`.
- Head final `d931f9607b662272daf315ddc1988fede28af96c` ; **9/9 workflows PR réussis**. Les gates PR/main restent présentes ;
  suppression du double lancement par push de branche, pas suppression de validation.
- Merge ref testé `4614e59f8d781020ee10cb318d8e6d7e39889bf0` ; arbre commun head/merge ref/merge réel `2309b3086cd7f38710e57bd6cdc174af7e5cf2d7`, parents vérifiés.
- Le commit qui porte cette clôture ne modifie que la documentation : vérifier son SHA et son diff
  depuis GitHub. Ne pas le confondre avec le head de code testé.
- D01 (#84), D02 (#85/#86), reset R0–R7 et H1–H4 terminés dans leurs périmètres. **H5 non terminé**.
  Dernier jalon produit : G51 Daily Spine. Baseline images v9, aucun nouveau digest inventé.

## Où reprendre

| Champ | Valeur |
|---|---|
| Branche / PR de développement active | **Aucune** |
| Dernier lot terminé | **D03 — déploiement sûr et topologie utile** |
| Prochain lot | **D04 — moteurs réels et exploitation (H5)** |
| Première action | Vérifier main/PR live, lire D04 et docs/deployment.md ; inventorier le matériel, les accès et les assets réellement disponibles, puis préparer/exécuter le scénario privé commun |
| Sortie D04 | Rapport daté avec versions/assets/matériel, PDF/mémoire/recherche/modèle réels, mesures et restauration hors hôte ; aucune preuve remplacée par un mock |
| Méthode | Une livraison cohérente par lot ; commits/checklists internes pour reprise, pas une suite de fragments |
| Limite | Ni achat/appel payant/déploiement utilisateur sans autorisation, ni nouvelles fonctions produit D05–D10 avant D04/H5 |

## Livré et prouvé en D03

- Refus des modes/secrets de développement en production ; JWT audience/azp/type et rôles stricts.
- SQL : kairo_app DML, migration distincte, bases/identités par moteur ; contrôle réel des privilèges
  au démarrage. Le token Worker ne donne plus accès au rebuild global en production.
- Web public : IP vérifiée utilisée pour la connexion, Host/SNI/TLS conservés, redirections contrôlées,
  lecture/durée bornées, pas de proxy/credentials ambiants ; six scénarios HTTP/TLS réels en CI.
- Profils et réseaux utiles, ports d'infrastructure retirés en production, Web sans accès SQL direct
  prouvé dans Docker ; images applicatives multi-stage/non root, ressources et arrêts bornés.
- Inventaire SHA-256/modèles, modes hors ligne configurés, contrôle d'images étendu ; dépendances
  Worker navigateur et variables sans consommateur retirées. Aucun moteur réel promu sur un stub.
- Build/typecheck, PostgreSQL/JetStream, identité/isolation, Documents, mémoire, politique, sauvegarde
  et SIGKILL Research passent sur le head final. Jobs ciblés `103323565532`, `103323565881`, `103323567503`.
  [Preuves détaillées](docs/archive/checkpoint-through-d03-2026-09-11.md).

## Limites et procédure de reprise

- Le passage de production exige un cluster dédié, provisionnement/rotation puis migration avec
  Core/Workers arrêtés et backup vérifié. Ne jamais réattribuer le superuser au runtime ni effacer
  une lease/dépense inconnue pour débloquer le système. Procédure complète : [deployment](docs/deployment.md).
- Migration canonique toujours `0014_capacity_and_data` ; D03 modifie les identités/droits et le
  lancement, pas le modèle métier. Une restauration des droits/versions doit être coordonnée.
- D04 doit vérifier vrais modèles, caches/bundles hors ligne, policies OpenBao, proxy TLS, réseau
  sur matériel cible, capacité et restauration chiffrée hors hôte. Les plafonds ne sont pas des mesures.
- Worker/moteurs restent des composants de confiance ; pas de sandbox de code hostile ni de mTLS
  multi-hôte revendiqués. Les estimations IA D02 ne garantissent pas un plafond fournisseur en dollars.
- Le CLI rebuild utilise maintenant `KAIRO_OPERATIONS_TOKEN`. Garder son même checkpoint ; en dev,
  cette variable reçoit le token interne de développement. Ne pas dupliquer les workflows/Tasks.

## Références et branches

[Plan D01–D22](docs/implementation-plan.md) · [roadmap](docs/roadmap.md) · [état produit](docs/status.md) ·
[reprise](docs/development-workflow.md) · [architecture](docs/architecture.md) · [ADR-028](docs/decisions/ADR-028-production-boundaries-and-optional-topology.md).

`hardening/d03-safe-deployment` et les branches D01/D02/H1–H4 précédentes sont **retirées**.
Réservoirs non canoniques : `feat/kairo-test-interface-v1`, `consolidate/g49-research-durable-stages` ;
inspection/récupération sélective uniquement, jamais merge en bloc. Historiques D01/D02 dans les archives.
