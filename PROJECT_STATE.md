# Nevolium — checkpoint de reprise

Dernière revue : 2026-09-12. **Vérifier GitHub live avant toute action.**

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
| Head Nevolium qualifié | `b5acf0ef6e10d291a8e264eec40fa76dbf98bb83`, arbre `caea5b20421594c695d1476a7efddfad60869327` |
| Validation | **10/10 workflows réussis** sur `73492a9…` ; socle interne, Core et Web vérifiés sur la cible, services moteur non publiés et ports applicatifs limités au loopback |
| Prochaine action | Installer et valider Caddy avec ses trois upstreams prêts, puis exécuter le preflight TLS/routage depuis un client extérieur avant de créer le premier compte nominatif |
| Conditions manquantes | Caddy/TLS et routes publiques refusées non prouvés ; premier compte nominatif avec MFA absent ; Worker non déployé ; backup Restic indépendant, campagne cible, charge et modèle quotidien non validés |
| Méthode | Garder cette PR ; commits internes comme checkpoints, aucun nouveau sous-lot et aucun D05 avant la sortie H5 |

## Transition d'identité achevée dans D04

Nevolium est l'unique identité publique et technique conformément à l'[ADR-030](docs/decisions/ADR-030-nevolium-canonical-identity.md).
Le changement couvre marque, modules Python, paquets npm, variables, Compose, SQL, Keycloak,
OpenBao, NATS, Temporal, stockage, télémétrie, protocoles, scripts, CI et documentation. Aucun alias
de compatibilité n'est prévu avant le premier déploiement : bases, volumes, streams, realm et secrets
doivent être créés frais. L'arbre suivi passe le verrou zéro résidu, les imports/builds des deux
paquets Python, les typechecks/builds JS, 12 contrats Core, 11 contrats Worker, les contrats identité,
mémoire et reproductibilité, ainsi que les validations JSON et Bash. Docker est absent du workspace,
le `uv` local est 0.12.11 au lieu du 0.12.13 imposé. La CI fraîche sur `d9478de…` est entièrement
verte : 10 workflows, dont les cinq jobs D04. [Rapport de transition](docs/archive/nevolium-identity-transition-2026-09-11.md).
Le dépôt est renommé `fredbuhr/nevolium`, la PR #88 a suivi le changement et le remote local `origin`
a été basculé puis vérifié sur la nouvelle URL.

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
- Ingress Caddy hôte préparé pour `app`, `api` et `auth` : HTTPS automatique, upstreams loopback,
  API limitée à `/v1` et `/v1/*`, refus 404 par défaut et absence de journal d'accès. Le contrat statique
  passe 3/3 ; l'installation, les certificats et les refus depuis un client extérieur restent à prouver.
- PostgreSQL de production démarré sur un volume neuf, sain et non publié ; les quatre identités SQL
  minimales ont été provisionnées et la chaîne Alembic canonique appliquée jusqu'à `0014_capacity_and_data`.
- Keycloak 26.7.3 démarré sur `127.0.0.1:8081` avec proxy de confiance limité à la passerelle ingress
  privée. Le realm de production neuf ne contient aucun utilisateur et son document de découverte expose
  exactement `https://auth.nevolium.com/realms/nevolium`. Deux premiers démarrages ont été arrêtés sans
  realm partiel : placeholder de proxy, puis variable de realm non transmise ; les deux gardes sont couvertes en CI.
- NATS 2.14.5 est sain sur ses deux réseaux internes, sans port hôte ; JetStream écrit dans le volume
  persistant attendu. Un premier contrôle opérateur a confondu le répertoire demandé `/data` avec le
  répertoire effectif `/data/jetstream` puis a arrêté proprement le service sans perte.
- SeaweedFS 4.46 conserve son volume et ne publie aucun port hôte ; Master et S3 répondent depuis le réseau
  canonique. La cible a révélé le choix initial d'une seule interface ; `-ip=seaweedfs` et
  `-ip.bind=0.0.0.0` corrigent respectivement l'identité annoncée et l'écoute multicarte, avec contrat CI.
- Temporal 1.31.2 est sain sur les réseaux canonique/exécution, sans port hôte. Les schémas `temporal` et
  `temporal_visibility` sont installés dans PostgreSQL et le namespace `default` est vérifié ; les deux
  conteneurs ponctuels de préparation et de namespace se sont terminés avec le code 0.
- Core est opérationnel sur `127.0.0.1:8000` : ses dépendances et frontières de confiance répondent,
  la requête anonyme et celle munie d'un faux jeton sont refusées, le jeton workload OpenBao est utilisable
  et le conteneur non-root reste en lecture seule, sans capacités Linux. Web sert le build de production
  sur `127.0.0.1:5173`, avec URLs API/auth publiques embarquées, routage SPA et en-têtes de sécurité
  vérifiés ; son unique réseau est `frontend`. Aucun de ces deux ports n'est encore exposé sur Internet.
- Récupération OpenBao exportée avec une identité dédiée, chiffrée par une seconde phrase secrète et
  vérifiée hors serveur, puis copie cloud privée retéléchargée et contrôlée par SHA-256. Jeton root initial
  révoqué seulement après preuve du workload ; sources locale et serveur retirées. Renouvellement quotidien
  systemd installé, premier passage réel réussi et jeton temporaire absent après exécution.

## Conditions de sortie et reprise après interruption

Les preuves CPU de CI ne clôturent pas H5. La séparation des clés OpenBao et le renouvellement du workload
sont désormais prouvés sur la cible. Restent : parcours canonique complet PDF/mémoire/recherche/modèle
choisi, charge et files en usage mixte, TLS/ingress, droits SQL/réseau, upgrade/rollback compatible et
restauration applicative Restic indépendante sur volumes neufs.
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
Netcup RS 4000 G12 livré à Vienne : 12 CPU AMD64, 32 Gio de RAM et disque 1 Tio. Debian 13,
accès administratif non-root par clé, SSH durci, mises à jour automatiques, journald persistant,
Fail2ban et pare-feu nftables/fournisseur ont été vérifiés, puis revérifiés après cold boot. DNS,
APT, HTTPS et ICMP fonctionnent en IPv4/IPv6. Un snapshot hors ligne a précédé la migration du pare-feu
hôte vers iptables-nft compatible Docker. Docker Engine/Compose officiels, rotation des logs,
`live-restore` et `DOCKER-USER` ont été vérifiés ; le checkout D04 public est propre. Aucun identifiant
réseau, compte ou secret n'est versionné ; [preuve expurgée](docs/archive/server-foundation-2026-09-11.md).
Le socle Nevolium est déployé par paliers : OpenBao 2.6.2, PostgreSQL, Keycloak, NATS/JetStream,
SeaweedFS, Temporal, Core et Web fonctionnent ; Worker reste arrêté. OpenBao utilise son backend
fichier persistant et son port 8200 n'est pas publié sur l'hôte. Après deux arrêts sûrs ayant révélé le format de jeton puis
la réponse CLI des accessors, la reprise contrôlée a révoqué l'unique jeton interrompu et enregistré
un nouveau jeton périodique orphelin de sept jours. Sa policy sans policy `default` autorise seulement
la lecture du namespace Nevolium, l'introspection de ses propres capacités et son renouvellement ;
quatre refus ont été vérifiés. Le service est sain et le garde de production accepte la configuration. L'environnement et les métadonnées
workload restent root 0600. Le matériel de récupération a été chiffré avec une identité dédiée, vérifié sans
écriture en clair sur le poste, copié sur un cloud privé puis retéléchargé avec empreinte identique. Le jeton
root initial a ensuite été révoqué et les copies de récupération retirées du serveur ; les parts hors serveur
permettent la génération exceptionnelle d'un nouveau root. Le workload orphelin a été renouvelé après
révocation. Son service systemd quotidien et persistant est actif après correction d'un premier refus de
traversée du checkout, survenu sans renouvellement ni activation du timer. PostgreSQL utilise un volume
neuf, reste sain et non publié ; les rôles SQL et la migration `0014_capacity_and_data` sont vérifiés.
Keycloak utilise sa base dédiée et un realm de production neuf sans utilisateur ; son issuer public est
exact derrière les en-têtes du proxy de confiance privé et son port 8081 est limité au loopback. Caddy
n'est pas encore installé et aucun certificat public n'est donc revendiqué. NATS/JetStream et SeaweedFS
conservent leurs volumes dédiés derrière les réseaux internes. SeaweedFS annonce le nom `seaweedfs` et
écoute ses deux interfaces après correction du défaut multiréseau découvert sur la cible. Temporal utilise
ses deux schémas PostgreSQL, son namespace `default` est présent et son port 7233 n'est pas publié.
ASUS TUF Gaming A16
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
