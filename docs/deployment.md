# KAIRO — déploiement contrôlé et profils

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
| `ai` | LiteLLM ; appels IA bornés et comptabilisés par KAIRO |
| `local-ai` | Ollama ; backend de l'alias local-fast, modèle à provisionner explicitement |
| `search` | SearXNG et Valkey ; News et recherches |
| `compose.web-mcp.yaml` | Outils publics search/fetch ; inclut SearXNG/Valkey et raccorde le Worker. En production ajouter aussi `compose.web-mcp.production.yaml` |
| `observability` + `compose.observability.yaml` | Langfuse, ClickHouse, Valkey et activation des callbacks LiteLLM ; hors autorité canonique |
| `voice` | Kokoro TTS ; adaptateur audio News, preuve de ressources réelles à faire |
| `admin` | Temporal UI ; administration interne uniquement |
| `automation`, `notifications` | Activepieces et ntfy : configurés, aucun consommateur KAIRO livré ; activation de production refusée |
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
  --profile ops run --rm --build kairo-db-provision
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml \
  --profile ops run --rm --build kairo-migrate
```

Sur un volume existant, `POSTGRES_USER/PASSWORD` doivent identifier le **compte administrateur existant** :
changer ces variables ne renomme pas le compte du volume. Le provisioneur crée/actualise les comptes,
révoque leurs appartenances, limite leurs bases, transfère les tables applicatives de la base concernée
sans `REASSIGN OWNED` global et accorde le DML au Core. Il peut être relancé après interruption/rotation.
Le compte administrateur ne se trouve ni dans Core, ni dans Worker, ni dans les moteurs en production.

| Identité | Droits |
|---|---|
| `kairo_app` | Connexion KAIRO, usage du schéma, SELECT/INSERT/UPDATE/DELETE, séquences ; pas CREATE/DROP/TRUNCATE |
| `kairo_migrator` | Propriétaire du schéma canonique et DDL ; seulement dans le conteneur de migration ponctuel |
| `mem0_app` | Base dérivée Mem0, aucun accès canonique |
| `keycloak_app`, `temporal_app`, `litellm_app`, `langfuse_app`, `activepieces_app` | Bases propres ; Temporal possède exécution et visibilité |

Le cluster est dédié à KAIRO : la révocation de CONNECT public sur les bases gérées/postgres/template1
n'est pas une recette à appliquer à un cluster partagé avec des applications inconnues.
Après migration, démarrer les moteurs choisis et les services compatibles ; vérifier santé, jetons,
droits, une Task et son résultat. Revenir à l'image précédente n'annule pas les droits SQL : conserver
les comptes restreints, examiner la compatibilité, ou restaurer le backup quiescent. Ne jamais accorder
le superuser au Core pour faire disparaître une erreur de migration.

## Identité, secrets et accès réseau

Configurer le realm Keycloak sans comptes de développement, le client public Web avec code flow + PKCE,
URLs de redirection/origines HTTPS exactes. Ajouter le mapper audience `kairo-core` sur **l'access token**,
comme dans la fixture de développement. Le Core vérifie RS256, issuer, audience, `azp` égal au client Web,
`typ=Bearer`, sujet/rôles et dates. Un ID token ou un access token d'un autre client est refusé.
Limiter `KEYCLOAK_PROXY_TRUSTED_ADDRESSES` à l'adresse/CIDR du proxy TLS réellement utilisé.

Initialiser et désceller OpenBao, créer le chemin KV et une policy limitée aux chemins KAIRO utilisés ;
fournir un token de workload non root. Le contrôle de configuration détecte les valeurs dev/faibles,
pas la portée réelle d'un token OpenBao : vérifier ses droits dans le scénario D04 et les renouveler.
`KAIRO_OPERATIONS_TOKEN`, distinct, reste avec Core/opérateur ; le Worker n'autorise plus le rebuild global
via son token interne en production. Le CLI de rebuild lit désormais `KAIRO_OPERATIONS_TOKEN` ; en dev,
y mettre la valeur du token interne de développement.

D04 ajoute la policy `infrastructure/openbao/policies/kairo-core-read.hcl` pour le Core actuel : lecture
du namespace `secret/data/kairo/*`, sans écriture/liste/administration. Les anciens chemins hors de ce
namespace doivent être migrés explicitement. L'entrypoint de l'image OpenBao charge déjà `/openbao/config` :
utiliser `command: [server]` ; ajouter une seconde fois le fichier charge deux listeners et empêche le démarrage.
OpenBao 2.6.2 refuse aussi l'ancienne option `disable_mlock` : elle et la capacité IPC_LOCK inutilisée
sont retirées. La politique mémoire/swap de l'hôte reste à vérifier sur la cible D04.
La [campagne D04](qualification-d04.md) vérifie le serveur persistant et la restauration sur un autre hôte.

Seuls Web/Core/Keycloak conservent des ports sur loopback. Le proxy TLS de l'opérateur doit publier
uniquement le Web, l'auth et `/v1/` de Core ; refuser `/internal/`, `/docs` et `/openapi.json` à l'ingress.
Inclure `/redoc` et les endpoints `/health/` dans cette restriction publique ; les sondes opérateur
restent internes. Avant la charge D04, lancer le contrôle `target.py preflight` décrit dans
[qualification-d04](qualification-d04.md) : TLS, authentification, formes JSON de l'API et refus des
routes privées. Ce contrôle en lecture seule ne configure ni ne démarre le proxy.
Les connexions entre moteurs sont sur des réseaux Docker internes séparés. Core/Keycloak ont
un pont d’entrée sans masquerading IP pour rendre leurs ports loopback joignables depuis le proxy hôte. Web MCP n'a ni token Core,
ni accès au réseau canonique. Les composants ayant une sortie Internet restent du code de confiance.
Ces réseaux ne prouvent ni isolation contre l'administrateur hôte, ni sandbox de code hostile, ni mTLS
multi-hôte. Le déploiement effectif et les rejets réseau sur matériel cible appartiennent à D04.

## Modèles et mise à jour explicite

Préparer les fichiers hors runtime, noter moteur, identifiant, révision et licence, puis enregistrer
un nouveau bundle contenant les caches `docling/`, `fastembed/`, `huggingface/` :

```bash
python -m kairo_worker.model_assets record ./model-assets --source 'moteur / modèle / révision / licence vérifiés'
python -m kairo_worker.model_assets verify ./model-assets
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
