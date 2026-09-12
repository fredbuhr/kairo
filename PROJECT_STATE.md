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
| Dernier code déployé confirmé | `e3adbe648b245e2567970769e6a4bf4333b3e4a4` ; Core porte le veto d'exécution, Worker reste opérationnel avec le budget 110/120/180 s et la sortie 256 jetons |
| Validation | `e3adbe6…` : 10/10 workflows réussis. Sur cible, la commande de veto termine en 59,57 s avec `semantic.execution-veto`, un usage modèle, une réservation réglée et zéro Task métier. Le modèle cible n'a proposé aucune capacité ; la CI prouve séparément le blocage d'une proposition `news.brief` valide et confiante |
| Prochaine action | Qualifier le parcours Research sur la cible avec ses outils réels, en conservant les commandes sémantiques et la Task News historiques |
| Conditions manquantes | Pertinence générale du routage et choix du modèle quotidien, Research avec outils réels, backup Restic indépendant, campagne cible/charge/rollback |
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

Les paragraphes suivants sont un historique des paliers, pas une description simultanée de l'état
actuel. Le tableau de reprise ci-dessus et le complément d'incident dans le rapport serveur font foi.

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
- Ingress Caddy hôte actif pour `app`, `api` et `auth` : certificats publics et redirections HTTPS
  vérifiés depuis Windows, upstreams loopback, API limitée à `/v1` et `/v1/*`, refus 404 par défaut et
  absence de journal d'accès. Les routes privées et les requêtes anonyme/faussement authentifiée sont
  refusées ; le parcours OIDC avec un utilisateur réel reste à prouver.
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
- Provisionnement du premier utilisateur applicatif préparé par une commande root sans sortie de secret :
  realm vide obligatoire, compte désactivé jusqu'au mot de passe temporaire, rôle `nevolium-user` et
  actions `UPDATE_PASSWORD`/`CONFIGURE_TOTP`, avec suppression du compte neuf sur échec. Cette commande
  a créé le premier compte sur la cible ; son adresse a été corrigée avant connexion par double confirmation,
  sans transmettre de champ de mot de passe. La première connexion a remplacé le mot de passe temporaire
  et configuré le TOTP. Une vérification administrative confirme le compte actif, le rôle `nevolium-user`,
  le TOTP présent et l'absence d'action initiale restante. Depuis Windows, Web a ensuite obtenu son jeton
  par Authorization Code + PKCE et `/v1/today` a rendu l'état vide du propriétaire sans erreur : Caddy et
  Core ont donc accepté le vrai bearer `nevolium-user`. Ce compte ne remplace pas le futur administrateur
  Keycloak nominatif.
- Transition vers un administrateur nominatif préparée sans réutiliser le compte standard : création
  désactivée, mot de passe temporaire et TOTP obligatoires, rôle applicatif `nevolium-admin` et composite
  `realm-management/realm-admin` limité au realm Nevolium. La commande refuse un état initial ambigu et
  supprime la nouvelle identité sur attribution incomplète. La cible contient désormais ce compte actif :
  mot de passe initial remplacé, TOTP présent, aucune action restante, deux rôles vérifiés et console du
  realm Nevolium ouverte depuis Windows. L'administrateur bootstrap du realm `master` reste intact.
- Retrait bootstrap préparé en deux gates. Les variables `KC_BOOTSTRAP_ADMIN_*` quittent les topologies
  standard et restent uniquement dans les overlays dev et bootstrap initial explicite. Le protocole
  exigeait d'abord de recréer Keycloak et de revérifier sa console nominative sans ces variables. Cette première
  gate est maintenant prouvée sur la cible : topologie rendue sans les deux variables, conteneur recréé,
  issuer public sain, compte nominatif vérifié puis nouvelle connexion MFA à la console réussie depuis
  Windows. La seconde gate est également achevée : les deux identités MFA ont été revérifiées, l'unique
  bootstrap `master` supprimé, ses anciens identifiants explicitement refusés et ses deux affectations
  retirées atomiquement du fichier root 0600. La topologie, Keycloak et Caddy sont restés sains ; une
  authentification MFA neuve de l'administrateur nominatif a rouvert la console après le retrait.
- Bundle Worker préparé hors runtime dans un répertoire temporaire avec l'image complète verrouillée.
  Les versions, les quatre révisions amont Docling/FastEmbed et les empreintes des huit fichiers de poids
  correspondent exactement au manifeste D04 archivé. Le bundle vérifié a été promu sous `/opt/nevolium`,
  appartient à root et sera monté en lecture seule ; la configuration privée root 0600 pointe vers lui.
  Aucun service Neo4j, Valkey, SearXNG, Ollama, LiteLLM ou Worker n'a été démarré à cette étape.
- Premier palier de moteurs activé sans exposition hôte. Neo4j répond à une requête Cypher authentifiée ;
  Valkey répond `PONG` et SearXNG sert son endpoint interne. Ollama a reçu le petit modèle de qualification
  par un conteneur temporaire borné, puis le digest complet `a8b0c515…f1827c67` a été comparé à la preuve
  D04 avant redémarrage dans le seul réseau interne `models`, sans egress. Keycloak, Caddy et Web sont
  restés sains.
- LiteLLM est maintenant actif sans port hôte sur ses seuls réseaux `models`, `telemetry` et `egress`.
  Sa configuration de qualification ne charge aucune clé OpenAI ou Anthropic et route `local-fast` vers
  le modèle Ollama D04 présent. Une vraie complétion non vide et son nombre de jetons ont été reçus ; un
  faux jeton LiteLLM a répondu 401. Ollama demeure limité à `models`, sans egress. À ce palier, Worker
  restait arrêté.
- L'image Worker complète a ensuite été construite et démarrée avec le bundle vérifié monté en lecture
  seule et les téléchargements Hugging Face/Transformers désactivés. Le processus UID 10001 est en lecture
  seule, sans capacité Linux ni nouveau privilège, borné en CPU/RAM/PID, sans port hôte et limité aux cinq
  réseaux nécessaires. Un vrai workflow `FoundationWorkflow` a été pris puis terminé via Temporal ; le
  durable JetStream `nevolium-memory-projector-v1` est actif. Les services publics sont restés sains.
- Un premier parcours métier `news.brief` authentifié a terminé son Task et son workflow Temporal, conservé
  dix sources owner-scoped et rendu un briefing déterministe après expiration bornée de la synthèse LiteLLM.
  Comme aucune réponse modèle n'a été obtenue, aucun usage ni jeton n'a été inventé et la réservation reste
  `uncertain` conformément à la politique de refus prudent.
- Le Command Center a ensuite exercé le routage sémantique `local-fast` avec 924 jetons de prompt, 101 de
  complétion et 1025 au total sous la limite de 256 jetons de sortie. Le modèle a proposé `unsupported` et
  Core a refusé l'exécution métier ; l'interface affiche désormais cet état terminal dans le bon panneau.
  Les configurations LiteLLM déclarent explicitement le coût nul local et le Worker ne traite l'absence de
  l'en-tête de coût comme zéro confirmé que pour cet alias qualifié. La nouvelle écriture a réglé sa
  réservation ; l'écriture antérieure identique a été rapprochée par rejeu idempotent de l'API canonique,
  sans créer de doublon ni modifier de donnée métier. La réservation News sans usage demeure inchangée.
- Le parcours PDF réel owner-scoped est maintenant qualifié. Le premier essai a conservé une `v1` échouée
  avant parsing, car Worker ne partageait aucun réseau avec SeaweedFS. Un réseau interne dédié `assets`
  relie désormais seulement les services nécessaires, sans placer Worker sur `canonical` ni SeaweedFS sur
  `egress`. La réingestion du même objet SHA-256 a produit une `v2` Docling 2.126.0 terminée, un chunk
  canonique et le marqueur attendu ; projet, asset et document portent le même propriétaire. Le confinement,
  l'absence de ports hôte et la santé des services publics ont été revalidés.
- Récupération OpenBao exportée avec une identité dédiée, chiffrée par une seconde phrase secrète et
  vérifiée hors serveur, puis copie cloud privée retéléchargée et contrôlée par SHA-256. Jeton root initial
  révoqué seulement après preuve du workload ; sources locale et serveur retirées. Renouvellement quotidien
  systemd installé, premier passage réel réussi et jeton temporaire absent après exécution.

## Conditions de sortie et reprise après interruption

Les preuves CPU de CI ne clôturent pas H5. La séparation des clés OpenBao et le renouvellement du workload
sont désormais prouvés sur la cible, ainsi que les projections mémoire propriétaire et leur rejeu sans doublon.
Restent : routage à froid/chaud, parcours Research, charge et files en usage mixte, upgrade/rollback
compatible et restauration applicative Restic indépendante sur volumes neufs. TLS/ingress, identités
nominatives, premiers parcours News/sémantique et comptabilité locale sont maintenant prouvés sur la cible.
Le modèle de test 0.5B ne sélectionne pas le modèle quotidien ; le PDF à couche texte ne qualifie pas
les scans complexes ; aucun test GPU ni 1000 comptes privés réels revendiqué. Une réservation sans usage
issue du timeout News reste inconnue par prudence ; les usages locaux réellement observés sont rapprochés
à coût nul sans généraliser cette règle aux alias potentiellement payants.

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
SeaweedFS, Temporal, Core, Web, Worker et moteurs internes qualifiés fonctionnent. OpenBao utilise son backend
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
Keycloak utilise sa base dédiée ; son realm de production initialement vide contient désormais le premier
utilisateur applicatif actif avec TOTP et rôle borné. Son issuer public est exact derrière les en-têtes du
proxy de confiance privé et son port 8081 est limité au loopback. Le cockpit Web authentifié a obtenu un
jeton PKCE et Core a autorisé sa lecture owner-scoped de `/v1/today`. Caddy
publie désormais les trois noms HTTPS avec certificats valides et refus public borné. NATS/JetStream et SeaweedFS
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
