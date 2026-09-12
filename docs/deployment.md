# Nevolium — déploiement contrôlé et profils

Procédure D03, PR #87. Le checkpoint indique si son head final est validé/intégré.
Les commandes ci-dessous sont des actions opérateur ; cette livraison ne les exécute pas chez l'utilisateur.

## Topologie utile

Le socle sans profils comprend PostgreSQL, NATS, SeaweedFS, les trois conteneurs de bootstrap/exécution
Temporal, OpenBao, Keycloak, Core, Worker et Web. Les tâches, projets et documents canoniques restent
accessibles sans services financiers ou graphiques séparés. Une capacité dont le moteur manque reste
indisponible ; ne pas confondre interface accessible et intelligence complète.

| Profil / overlay | Services et consommation actuelle |
|---|---|
| `memory` | Neo4j ; le Worker réel utilise aussi la base Mem0. Indispensable au scénario mémoire réel D04 |
| `ai` | LiteLLM ; appels IA bornés et comptabilisés par Nevolium |
| `local-ai` | Ollama ; backend de l'alias local-fast, modèle à provisionner explicitement |
| `search` | SearXNG et Valkey ; News et recherches |
| `compose.web-mcp.yaml` | Outils publics search/fetch ; inclut SearXNG/Valkey et raccorde le Worker. En production ajouter aussi `compose.web-mcp.production.yaml` |
| `observability` + `compose.observability.yaml` | Langfuse, ClickHouse, Valkey et activation des callbacks LiteLLM ; hors autorité canonique |
| `voice` | Kokoro TTS ; adaptateur audio News, preuve de ressources réelles à faire |
| `admin` | Temporal UI ; administration interne uniquement |
| `automation`, `notifications` | Activepieces et ntfy : configurés, aucun consommateur Nevolium livré ; activation de production refusée |
| `collaboration-experimental`, `voice-experimental` | Hocuspocus et LiveKit : prototypes ; activation de production refusée |
| `finance`, `home`, `dev-agent`, `remote` | Moteurs non intégrés ; activation de production refusée |
| `gpu` | vLLM optionnel ; révision amont de modèle de 40 caractères hexadécimaux obligatoire, intégration non validée |
| `ops` | Provisionnement SQL et migration ponctuels ; sauvegarde avec `compose.ops.yaml` |

Les ressources CPU/RAM/PIDs et `init` sont bornées pour les services. Ce sont des plafonds de
sécurité, pas des recommandations matérielles : notamment 4 Go peuvent être insuffisants pour
un modèle local. D04 mesure et ajuste sur le matériel choisi. Worker : 45 s de délai Docker,
20 s de grâce Temporal puis annulation/nettoyage ; les contrôles d'interruption D01/D02 restent requis.

## Préparer et contrôler

Utiliser Compose >= 2.24.4 (`!reset`/`!override`). Copier `.env.production.example` dans un fichier
privé, remplacer les placeholders par des secrets distincts et les URLs par les adresses réelles.
Pour les mots de passe interpolés dans les DSN, utiliser 32 octets aléatoires encodés en hexadécimal.
Le fichier modèle n'est volontairement pas une configuration acceptée par le garde de production.

```bash
python scripts/ops/production.py check --env-file .env.production
# Scénario mémoire/recherche/modèle local, lorsque ses assets seront préparés :
python scripts/ops/production.py check --env-file .env.production \
  --profile memory --profile ai --profile local-ai --web-mcp
```

Le contrôleur analyse le JSON effectif de Compose sans afficher les secrets. Il refuse entre autres
le mélange avec l'overlay dev/noauth, les identifiants SQL administratifs côté Core, les secrets de
modèle, les ports publics non contrôlés et les prototypes à privilèges hôte. Le Core et le Worker
vérifient aussi leur configuration au démarrage ; Core vérifie ses privilèges SQL effectifs.
`make prod-template` ne vérifie que la syntaxe du modèle ; `make prod-config` valide le fichier réel.

## SQL : installation initiale et transition depuis le développement

Arrêter les anciens Core/Workers et autres consommateurs SQL ; sauvegarder et vérifier la procédure
de restauration avant de modifier une installation existante. Ne pas mélanger versions/identifiants
pendant le changement. La procédure ne supprime pas de données et ne relance aucun workflow.

```bash
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d postgres
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml \
  --profile ops run --rm --build nevolium-db-provision
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml \
  --profile ops run --rm --build nevolium-migrate
```

Sur un volume existant, `POSTGRES_USER/PASSWORD` doivent identifier le **compte administrateur existant** :
changer ces variables ne renomme pas le compte du volume. Le provisioneur crée/actualise les comptes,
révoque leurs appartenances, limite leurs bases, transfère les tables applicatives de la base concernée
sans `REASSIGN OWNED` global et accorde le DML au Core. Il peut être relancé après interruption/rotation.
Le compte administrateur ne se trouve ni dans Core, ni dans Worker, ni dans les moteurs en production.

| Identité | Droits |
|---|---|
| `nevolium_app` | Connexion Nevolium, usage du schéma, SELECT/INSERT/UPDATE/DELETE, séquences ; pas CREATE/DROP/TRUNCATE |
| `nevolium_migrator` | Propriétaire du schéma canonique et DDL ; seulement dans le conteneur de migration ponctuel |
| `mem0_app` | Base dérivée Mem0, aucun accès canonique |
| `keycloak_app`, `temporal_app`, `litellm_app`, `langfuse_app`, `activepieces_app` | Bases propres ; Temporal possède exécution et visibilité |

Le cluster est dédié à Nevolium : la révocation de CONNECT public sur les bases gérées/postgres/template1
n'est pas une recette à appliquer à un cluster partagé avec des applications inconnues.
Après migration, démarrer les moteurs choisis et les services compatibles ; vérifier santé, jetons,
droits, une Task et son résultat. Revenir à l'image précédente n'annule pas les droits SQL : conserver
les comptes restreints, examiner la compatibilité, ou restaurer le backup quiescent. Ne jamais accorder
le superuser au Core pour faire disparaître une erreur de migration.

## Identité, secrets et accès réseau

Configurer le realm Keycloak sans comptes de développement, le client public Web avec code flow + PKCE,
URLs de redirection/origines HTTPS exactes. Ajouter le mapper audience `nevolium-core` sur **l'access token**,
comme dans la fixture de développement. Le Core vérifie RS256, issuer, audience, `azp` égal au client Web,
`typ=Bearer`, sujet/rôles et dates. Un ID token ou un access token d'un autre client est refusé.
Limiter `KEYCLOAK_PROXY_TRUSTED_ADDRESSES` à l'adresse/CIDR du proxy TLS réellement utilisé.
Pour le proxy Caddy hôte, après création du réseau `nevolium_ingress` et avec Keycloak arrêté,
lier atomiquement cette valeur à l'unique passerelle privée détectée sans afficher ni réécrire les
autres secrets :

```bash
sudo python3 scripts/ops/configure_keycloak_proxy.py \
  --env-file /etc/nevolium/production.env
```

Le garde de production refuse les placeholders, adresses publiques, plages larges et adresses de
confiance multiples. Relancer le garde après cette opération et avant Keycloak.

Le premier démarrage de production monte uniquement `keycloak/production/nevolium-realm.json` et utilise
`--import-realm`. Ce fichier ne contient aucun utilisateur ni secret : il crée les deux rôles, le client
Web public, le code flow avec PKCE S256, les origines exactes et le mapper d'audience. La fixture
`nevolium-realm.json` reste réservée au développement et ne doit jamais être montée en production.
Keycloak ignore l'import si le realm existe déjà ; toute évolution ultérieure doit donc passer par une
opération d'administration explicite et vérifiée, jamais par l'écrasement implicite de données.

Les identifiants `KC_BOOTSTRAP_ADMIN_*` créent un administrateur temporaire dans le realm `master` au
premier démarrage. Après création et vérification d'un accès administrateur nominatif protégé par MFA,
supprimer ce compte temporaire et retirer ses identifiants de la configuration privée. Ne pas réutiliser
ce compte comme utilisateur pilote Nevolium.

Créer le premier compte applicatif seulement après validation de TLS. La commande refuse un realm non
vide, lit les identifiants bootstrap depuis le fichier root 0600 sans les afficher, crée d'abord le compte
désactivé, puis configure un mot de passe temporaire, le rôle `nevolium-user` et les actions obligatoires
`UPDATE_PASSWORD`/`CONFIGURE_TOTP` avant de l'activer. Tout échec intermédiaire retire ce compte neuf :

```bash
sudo python3 scripts/ops/keycloak_first_user.py create \
  --env-file /etc/nevolium/production.env
```

Avant la première connexion seulement, une adresse saisie incorrectement peut être remplacée après une
double confirmation. La commande exige encore l'unique compte dans son état initial et vérifie que rôle,
et actions MFA restent intacts ; elle ne transmet aucun champ de mot de passe et restaure l'adresse
précédente sur échec :

```bash
sudo python3 scripts/ops/keycloak_first_user.py correct-email \
  --env-file /etc/nevolium/production.env
```

Après la première connexion Web, le changement de mot de passe et l'enregistrement TOTP, vérifier l'état
sans afficher l'identité ou les credentials :

```bash
sudo python3 scripts/ops/keycloak_first_user.py verify \
  --env-file /etc/nevolium/production.env
```

Ce compte standard n'est pas l'administrateur Keycloak nominatif requis avant le retrait du bootstrap.
Ne pas supprimer le bootstrap ni ses variables tant que l'accès d'administration de remplacement avec
MFA n'a pas été créé et testé séparément.

Initialiser et désceller OpenBao, créer le chemin KV et une policy limitée aux chemins Nevolium utilisés ;
fournir un token de workload non root. Le contrôle de configuration détecte les valeurs dev/faibles,
pas la portée réelle d'un token OpenBao : vérifier ses droits dans le scénario D04 et les renouveler.
`NEVOLIUM_OPERATIONS_TOKEN`, distinct, reste avec Core/opérateur ; le Worker n'autorise plus le rebuild global
via son token interne en production. Le CLI de rebuild lit désormais `NEVOLIUM_OPERATIONS_TOKEN` ; en dev,
y mettre la valeur du token interne de développement.

D04 ajoute la policy `infrastructure/openbao/policies/nevolium-core-read.hcl` pour le Core actuel : lecture
du namespace `secret/data/nevolium/*`, sans écriture/liste/administration. Le jeton de workload est
orphelin, périodique et sans policy par défaut ; cette policy lui accorde `lookup-self`,
`renew-self` et l'introspection de ses propres capacités via `sys/capabilities-self`. Cette dernière
remplace uniquement le droit normalement fourni par la policy `default`, volontairement absente, et
permet au bootstrap de vérifier les droits effectifs sans inspecter une autre identité. Le renouvellement
surveillé ne nécessite donc pas de garder le jeton racine en ligne. Renouveler
largement avant la fin de chaque période et alerter sur tout échec ; un jeton expiré doit être remplacé
par l'opérateur après déscellement. Les anciens chemins hors de ce namespace doivent être migrés explicitement. L'entrypoint de l'image OpenBao charge déjà `/openbao/config` :
utiliser `command: [server]` ; ajouter une seconde fois le fichier charge deux listeners et empêche le démarrage.
OpenBao 2.6.2 refuse aussi l'ancienne option `disable_mlock` : elle et la capacité IPC_LOCK inutilisée
sont retirées. La politique mémoire/swap de l'hôte reste à vérifier sur la cible D04.
La [campagne D04](qualification-d04.md) vérifie le serveur persistant et la restauration sur un autre hôte.

Sur une nouvelle instance privée déjà démarrée mais non initialisée, le bootstrap contrôlé génère
trois parts de déscellement avec un seuil de deux, conserve temporairement la réponse d'initialisation
dans un fichier root 0600, active KV v2, charge la policy, crée un jeton périodique orphelin de sept
jours et vérifie ses capacités ainsi que son renouvellement sans afficher de secret. Il refuse une
instance déjà initialisée ou un fichier de récupération existant et ne démarre aucun autre service :

```bash
sudo python3 scripts/ops/bootstrap_openbao.py \
  --env-file /etc/nevolium/production.env \
  --recovery-file /etc/nevolium/openbao-recovery.json
```

Exporter ensuite le fichier de récupération hors serveur par un canal chiffré, séparer les parts et
vérifier la récupération avant d'effacer la copie serveur et de révoquer le jeton racine initial.
Le jeton de workload reste dans le fichier d'environnement privé et son accessor non secret dans
`openbao-workload.json`. Les jetons de service OpenBao 2.6 suivent le format opaque `s.` avec au
moins 24 caractères alphanumériques ; ils sont validés par leur format et leurs capacités effectives,
tandis que les autres secrets Nevolium conservent le minimum de 32 caractères.

Le renouvellement surveillé est installé comme un exécutable root stable et un timer systemd. Le service
lit les deux fichiers privés sans les afficher, lie le jeton à l'accessor enregistré, exige l'unique policy
`nevolium-core`, l'absence de parent et de policy `default`, la période de sept jours et un TTL renouvelé
d'au moins six jours. Il verrouille les exécutions concurrentes, nettoie le jeton temporaire du conteneur
et échoue sans inclure le secret dans ses diagnostics.
L'unité conserve seulement `CAP_DAC_READ_SEARCH` pour traverser le checkout privé en lecture ; le reste
de son espace système demeure en lecture seule et elle ne reçoit aucune capacité d'écriture privilégiée.

```bash
sudo install -D -o root -g root -m 0755 \
  scripts/ops/renew_openbao_token.py \
  /usr/local/libexec/nevolium-openbao-renew
sudo install -o root -g root -m 0644 \
  infrastructure/systemd/nevolium-openbao-renew.service \
  infrastructure/systemd/nevolium-openbao-renew.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start nevolium-openbao-renew.service
sudo systemctl enable --now nevolium-openbao-renew.timer
systemctl --no-pager status nevolium-openbao-renew.service
systemctl list-timers --all nevolium-openbao-renew.timer
```

Le démarrage manuel du service est la gate avant activation du timer. Celui-ci renouvelle chaque jour à
03:17 UTC avec jusqu'à trente minutes de dispersion et rattrape une échéance manquée. Un échec reste
visible dans l'état systemd et dans `journalctl -u nevolium-openbao-renew.service` sans valeur secrète ;
une notification externe demeure à raccorder au futur canal d'exploitation. Après un redémarrage avec
Shamir, OpenBao reste scellé jusqu'au déscellement opérateur : contrôler ensuite le service immédiatement,
sans attendre le timer. Réinstaller l'exécutable et les unités après une mise à niveau de cette procédure.

Si une première exécution a été interrompue après l'initialisation et avant l'écriture du jeton dans
l'environnement, ne jamais réinitialiser le coffre. Après diagnostic, reprendre explicitement :

```bash
sudo python3 scripts/ops/bootstrap_openbao.py \
  --env-file /etc/nevolium/production.env \
  --recovery-file /etc/nevolium/openbao-recovery.json \
  --resume
```

La reprise exige le fichier de récupération root 0600 et le placeholder encore présent dans
`production.env`. Elle déscelle si nécessaire et exige de retrouver exactement l'unique jeton
périodique interrompu correspondant à la policy Nevolium avant de le révoquer ; tout écart arrête
la procédure sans révocation. Elle recrée ensuite et vérifie un unique jeton de workload.

Seuls Web/Core/Keycloak conservent des ports sur loopback. Le proxy TLS de l'opérateur doit publier
uniquement le Web, l'auth et `/v1/` de Core ; refuser `/internal/`, `/docs` et `/openapi.json` à l'ingress.
Inclure `/redoc` et les endpoints `/health/` dans cette restriction publique ; les sondes opérateur
restent internes. Avant la charge D04, lancer le contrôle `target.py preflight` décrit dans
[qualification-d04](qualification-d04.md) : TLS, authentification, formes JSON de l'API et refus des
routes privées. Ce contrôle en lecture seule ne configure ni ne démarre le proxy.

La configuration hôte versionnée dans `infrastructure/caddy/Caddyfile` publie les trois noms Nevolium
avec HTTPS automatique. L'API suit une liste positive : seuls `/v1` et `/v1/*` atteignent Core ; tout
autre chemin reçoit un 404 directement du proxy. Les upstreams restent exclusivement sur loopback et
le journal d'accès Caddy n'est pas activé, afin de ne pas conserver accidentellement de paramètres
sensibles. Installer Caddy depuis le paquet de la distribution seulement après validation du DNS et
des pare-feu, puis valider le fichier avant toute activation :

```bash
sudo install -D -o root -g root -m 0644 \
  infrastructure/caddy/Caddyfile /etc/caddy/Caddyfile
sudo caddy fmt --overwrite /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable --now caddy
```

Les ports 80 et 443 doivent être joignables depuis Internet pour les challenges ACME. Ne pas activer
le proxy avec la page par défaut du paquet. Vérifier les trois certificats, les redirections HTTP vers
HTTPS et les refus API depuis un client extérieur. Un upstream absent doit produire un échec explicite,
jamais élargir la route publique. La valeur `KEYCLOAK_PROXY_TRUSTED_ADDRESSES` doit correspondre à
l'adresse source réellement observée par Keycloak pour le proxy hôte, pas à une plage large inventée.
Les connexions entre moteurs sont sur des réseaux Docker internes séparés. Core/Keycloak ont
un pont d’entrée sans masquerading IP pour rendre leurs ports loopback joignables depuis le proxy hôte. Web MCP n'a ni token Core,
ni accès au réseau canonique. Les composants ayant une sortie Internet restent du code de confiance.
Ces réseaux ne prouvent ni isolation contre l'administrateur hôte, ni sandbox de code hostile, ni mTLS
multi-hôte. Le déploiement effectif et les rejets réseau sur matériel cible appartiennent à D04.

SeaweedFS appartient simultanément aux réseaux internes `canonical` et `telemetry`. Le serveur tout-en-un
doit donc conserver `-ip=seaweedfs` comme identité annoncée, résoluble sur les deux réseaux, et
`-ip.bind=0.0.0.0` afin que Master, Filer, volumes et S3 répondent sur les deux interfaces du conteneur.
Cette écoute interne n'expose aucun port hôte : l'overlay de production remet explicitement la liste
`ports` à zéro. Retirer l'un de ces paramètres laisse SeaweedFS choisir ou annoncer une seule interface
et coupe les consommateurs de l'autre réseau.

## Modèles et mise à jour explicite

Préparer les fichiers hors runtime, noter moteur, identifiant, révision et licence, puis enregistrer
un nouveau bundle contenant les caches `docling/`, `fastembed/`, `huggingface/` :

```bash
python -m nevolium_worker.model_assets record ./model-assets --source 'moteur / modèle / révision / licence vérifiés'
python -m nevolium_worker.model_assets verify ./model-assets
```

Les commandes n'effectuent aucun téléchargement. Un inventaire vide, des fichiers modifiés ou un lien
sortant du bundle sont refusés. Production monte ce bundle en lecture seule, active les modes hors
ligne et vérifie tous les SHA-256 avant de démarrer Worker. Cela ne garantit pas qu'un cache contient
les bons modèles : la preuve PDF/embeddings réelle D04 doit passer avant promotion. Un échec de modèle
ne doit pas être contourné en revenant silencieusement au mode mémoire stub.

Ollama stocke ses modèles dans son volume et n'a pas de sortie Internet en production. Préparer ses
poids explicitement, enregistrer les digests du manifeste et les versions avec le rapport D04 ; aucun
`pull` automatique au démarrage. vLLM exige une révision explicite. OpenHands reste hors production ;
son image enfant est `UNCONFIGURED` tant qu'un opérateur n'a pas fourni un tag incluant son digest
(`version@sha256:…`). Ne pas inventer un digest pour permettre un démarrage.

Pour chaque upgrade : nouvel inventaire, nouvelles références digérées, lockfiles validés, gates PR,
backup quiescent, migration contrôlée et scénario D04. Conserver ancienne image/bundle pour retour
arrière. Les API externes ne garantissent pas une immutabilité des poids malgré leur nom de modèle.

## Références techniques

Le transport suit l'[extension SNI de HTTPCore](https://www.encode.io/httpcore/extensions/).
Le cache Docling suit son [mode de préchargement/hors ligne](https://docling-project.github.io/docling/usage/advanced_options/).
Les preuves exactes et les éventuels défauts restant ouverts sont dans PROJECT_STATE et les archives.
