# KAIRO — checkpoint de reprise

Dernière revue : 2026-09-11. **Vérifier GitHub live avant toute action.**

## Source canonique

- `main` porte D03 terminé (#87), merge `d8b8025bb9143e49093eaaac3295affefc6fc07f`.
- Base canonique vérifiée avant D04 : `0e2d22d8b49d1ddda6f2c0432de8dfe991b3ee0a`.
  Les checkpoints suivants sont documentaires ; vérifier leurs diffs, ne pas les prendre pour une intégration de D04.
- D01–D03, reset R0–R7 et H1–H4 terminés dans leurs périmètres. **D04/H5 ouvert** ; dernier jalon produit G51 Daily Spine.
- Migration canonique : `0014_capacity_and_data`. Baseline images v9 ; aucun nouveau digest inventé.

## Où reprendre — un seul lot et une seule PR

| Champ | Valeur |
|---|---|
| Lot actif | **D04 — moteurs réels et exploitation (H5)** |
| Branche active | `hardening/d04-real-engine-qualification` |
| Livraison active | [PR #88](https://github.com/fredbuhr/kairo/pull/88), ouverte en draft, non fusionnée |
| Head de code à contrôler | `10cb57c27e8018ea55b738dbf02495a3eff44aff` |
| Arbre de ce head | `bfd2bdd857da639d2792428d7659e246d11abaf6` |
| Validation | **9/9 workflows réussis** sur ce head, dont **5/5 jobs D04** ; rapport et JSON versionnés ci-dessous |
| Prochaine action | Identifier la machine privée retenue, y lancer l'inventaire D04, puis exécuter le scénario commun avec la configuration réelle |
| Condition manquante | Matériel/cible privée et destination indépendante de sauvegarde non fournis ; aucun accès ni modèle quotidien inventé |
| Méthode | Garder cette PR ; commits internes comme checkpoints, aucun nouveau sous-lot et aucun D05 avant la sortie H5 |

## Réalisé sur la branche, sans promotion de main

- Image Worker complète avec dépendances natives OCR figées ; écriture technique Mem0 dans TMPDIR
  et historique SDK en mémoire pour respecter le système en lecture seule.
- Vrai PDF Docling, embeddings Mem0/PostgreSQL, épisodes Graphiti/Neo4j, recherche sémantique et
  isolation des scopes ; exécution CPU sans Internet, modèles en lecture seule et inventaire SHA-256 conservé.
- Petite IA locale Ollama/LiteLLM via gateway/comptabilité KAIRO, panne/rejeu connu/refus du rejeu
  incertain/redémarrage ; recherche publique réelle SearXNG. Aucun fournisseur payant configuré dans les fixtures.
- OpenBao persistant corrigé pour la version épinglée ; policy de lecture KAIRO et quatre refus vérifiés.
- Sauvegarde Restic chiffrée et restauration sur un autre hôte CI avec vrais SQL, message JetStream,
  objet filer et secret OpenBao. Attente bornée des volumes SeaweedFS au démarrage, contenu original exigé.
- Inventaire cible et générateur de charge en lecture seule prêts ; arrêt sur erreur/seuil, accès anonyme
  refusé, distinction entre clients virtuels et comptes réellement utilisés. Ce contrat HTTP n'est pas une mesure de capacité KAIRO.

## Conditions de sortie et reprise après interruption

Les preuves CPU de CI ne clôturent pas H5. Restent sur la cible retenue : parcours canonique complet
PDF/mémoire/recherche/modèle choisi, charge et files en usage mixte, TLS/ingress, droits SQL/réseau,
upgrade/rollback compatible et restauration indépendante avec récupération séparée des clés.
Le modèle de test 0.5B ne sélectionne pas le modèle quotidien ; le PDF à couche texte ne qualifie pas
les scans complexes ; aucun test GPU ni 1000 comptes privés réels revendiqué. Les coûts inconnus D02
restent inconnus, même si une réponse locale expose un montant numérique nul.

Avant reprise : lire AGENTS, comparer `main`, PR #88 et son head live ; lire le rapport et ses limites.
Les commits de preuves/checkpoint après le head de code doivent rester documentaires. Si un test échoue,
conserver ses résultats, corriger dans D04 et revalider le code changé ; ne pas effacer leases, dépenses
inconnues ou données pour débloquer une gate. Aucun déploiement utilisateur exécuté dans cette session.

## Références

- [Protocole D04](https://github.com/fredbuhr/kairo/blob/hardening/d04-real-engine-qualification/docs/qualification-d04.md)
- [Rapport D04 daté et preuves](https://github.com/fredbuhr/kairo/blob/hardening/d04-real-engine-qualification/docs/archive/qualification-d04-2026-09-11.md)
- [Plan stable D01–D22](docs/implementation-plan.md) · [reprise](docs/development-workflow.md) · [déploiement](docs/deployment.md)
- [Acquis D03](docs/archive/checkpoint-through-d03-2026-09-11.md) · [état produit](docs/status.md) · [roadmap](docs/roadmap.md)

Les anciennes branches D01–D03/H1–H4 sont retirées. Réservoirs non canoniques inspectés :
`feat/kairo-test-interface-v1` (`ed12d503…`) et `consolidate/g49-research-durable-stages` (`57a1a217…`).
Aucun merge en bloc ; principe de namespace OpenBao repris après revue, droits futurs non accordés.
