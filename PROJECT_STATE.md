# Nevolium — checkpoint de reprise

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
| Livraison active | [PR #88](https://github.com/fredbuhr/nevolium/pull/88), ouverte en draft, non fusionnée |
| Head de code Nevolium | `18dff4d7507fad285fae871e35e56c0567e42c3a`, arbre `e39f8ebfe2a55a0869cafb6531a6fbabbf3a70f4` ; publié sur la PR, CI complète en attente |
| Validation | Avant transition : **9/9 workflows**, **5/5 jobs D04** sur `a5a61db…`. Arbre renommé : contrats locaux rapides réussis ; CI/Docker complets à rejouer, aucun ancien succès ne qualifie ce nouveau head |
| Prochaine action | Publier/contrôler le head Nevolium, exiger les 10 workflows verts, puis renommer le dépôt GitHub avant toute installation serveur |
| Conditions manquantes | Nouveau head CI, renommage GitHub, inventaire OS réel, pare-feu, domaine/TLS, sauvegarde indépendante et modèle quotidien non validés |
| Méthode | Garder cette PR ; commits internes comme checkpoints, aucun nouveau sous-lot et aucun D05 avant la sortie H5 |

## Transition d'identité en cours dans D04

Nevolium est l'unique identité publique et technique conformément à l'[ADR-030](docs/decisions/ADR-030-nevolium-canonical-identity.md).
Le changement couvre marque, modules Python, paquets npm, variables, Compose, SQL, Keycloak,
OpenBao, NATS, Temporal, stockage, télémétrie, protocoles, scripts, CI et documentation. Aucun alias
de compatibilité n'est prévu avant le premier déploiement : bases, volumes, streams, realm et secrets
doivent être créés frais. L'arbre suivi passe le verrou zéro résidu, les imports/builds des deux
paquets Python, les typechecks/builds JS, 12 contrats Core, 11 contrats Worker, les contrats identité,
mémoire et reproductibilité, ainsi que les validations JSON et Bash. Docker est absent du workspace,
le `uv` local est 0.12.11 au lieu du 0.12.13 imposé ; la CI fraîche reste donc l'autorité.

## Réalisé sur la branche, sans promotion de main

- Image Worker complète avec dépendances natives OCR figées ; écriture technique Mem0 dans TMPDIR
  et historique SDK en mémoire pour respecter le système en lecture seule.
- Vrai PDF Docling, embeddings Mem0/PostgreSQL, épisodes Graphiti/Neo4j, recherche sémantique et
  isolation des scopes ; exécution CPU sans Internet, modèles en lecture seule et inventaire SHA-256 conservé.
- Petite IA locale Ollama/LiteLLM via gateway/comptabilité Nevolium, panne/rejeu connu/refus du rejeu
  incertain/redémarrage ; recherche publique réelle SearXNG. Aucun fournisseur payant configuré dans les fixtures.
- OpenBao persistant corrigé pour la version épinglée ; policy de lecture Nevolium et quatre refus vérifiés.
- Sauvegarde Restic chiffrée et restauration sur un autre hôte CI avec vrais SQL, message JetStream,
  objet filer et secret OpenBao. Attente bornée des volumes SeaweedFS au démarrage, contenu original exigé.
- Inventaire et contrôle préalable cible prêts : TLS, refus anonyme/faux jeton, JSON Nevolium attendu et
  routes privées bloquées avant la charge ; réponses bornées et erreurs sans secrets. Six tests HTTP/TLS
  réussis en CI. Les clients virtuels ne sont pas des comptes distincts ; le serveur de fixture ne mesure pas la capacité Nevolium.

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

## Orientation utilisateur précisée après la campagne

Serveur prioritaire ; installation complète sur PC personnel également visée. Clients PC, smartphone
et tablette, avec mode hors ligne borné et 3D adaptative. [ADR-029 et critères](https://github.com/fredbuhr/nevolium/blob/hardening/d04-real-engine-qualification/docs/decisions/ADR-029-server-personal-and-offline-clients.md)
et plan D05–D22 ajustés dans la même PR ; choix de conception, pas fonctionnalités livrées.
Netcup RS 4000 G12 livré à Vienne et en fonctionnement selon captures utilisateur : 12 CPU AMD64,
32 Gio de RAM, disque 1 Tio et IPv4/IPv6 attribuées. Aucun identifiant réseau ou de compte n'est versionné.
Le panneau montre zéro règle de pare-feu ; état réel à vérifier avant installation. ASUS TUF Gaming A16
FA608PM relevé pour une répétition ultérieure : Ryzen 9 8940HX, 32 Go RAM, RTX 5060 Laptop 8 Go,
environ 586 Go libres sous Windows x64. Budget préféré 50 €/mois, maximum 90 €, pilote 3–4 personnes.
Protocole local/serveur ajouté dans qualification-d04 ; captures seulement, aucun test exécuté sur les machines.
D04 reste centré sur le premier serveur Linux ; modèle quotidien non choisi. Ne pas confondre
ces cibles produit avec trois serveurs à synchroniser ou exiger tous les OS/mobiles avant de fermer H5.

## Références

- [Complément accès public et validation](https://github.com/fredbuhr/nevolium/blob/hardening/d04-real-engine-qualification/docs/archive/d04-public-access-2026-09-11.md)

- [Protocole D04](https://github.com/fredbuhr/nevolium/blob/hardening/d04-real-engine-qualification/docs/qualification-d04.md)
- [Rapport D04 daté et preuves](https://github.com/fredbuhr/nevolium/blob/hardening/d04-real-engine-qualification/docs/archive/qualification-d04-2026-09-11.md)
- [Plan stable D01–D22](docs/implementation-plan.md) · [reprise](docs/development-workflow.md) · [déploiement](docs/deployment.md)
- [Acquis D03](docs/archive/checkpoint-through-d03-2026-09-11.md) · [état produit](docs/status.md) · [roadmap](docs/roadmap.md)

Les anciennes branches D01–D03/H1–H4 sont retirées. Réservoirs non canoniques inspectés :
prototype d'interface historique (`ed12d503…`) et `consolidate/g49-research-durable-stages` (`57a1a217…`).
Aucun merge en bloc ; principe de namespace OpenBao repris après revue, droits futurs non accordés.
