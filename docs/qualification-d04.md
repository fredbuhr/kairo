# D04 — campagne commune des moteurs réels et de l'exploitation

Lot actif, une branche/PR : `hardening/d04-real-engine-qualification`, [#88](https://github.com/fredbuhr/nevolium/pull/88).
Les preuves exactes sont dans PROJECT_STATE et le rapport daté. Cette procédure ne déclare pas H5 terminé.
Les fixtures n'emploient ni documents privés ni fournisseur payant. Les tests qui arrêtent/restaurent
des services sont limités au projet CI jetable ; ne pas les lancer sur une installation existante.

## Une campagne, plusieurs moyens de mesure

| Scénario | Exécution commune | Critère fixé avant mesure |
|---|---|---|
| Worker complet | Image canonique, extra intelligence, lockfile inchangé | Imports et exécution réelle ; aucun remplacement par stub |
| PDF Docling | PDF original avec couche texte, même enfant borné que le Worker | Texte attendu et parser `docling`, ≤210 s, délai parser 180 s conservé |
| Mémoire | Mem0/embeddings ONNX + PostgreSQL, Graphiti + Neo4j | Projection et rejeu ≤240 s, mêmes clés, recherche du bon scope et aucun résultat étranger |
| Modèles hors ligne | Préparation réseau explicite ; exécution réseau Docker interne et bundle en lecture seule | IP publiques injoignables, cache absent refusé, SHA-256 inchangés après les adaptateurs |
| Modèle local | Petit Qwen2.5 0.5B de qualification → Ollama → LiteLLM → gateway Core | Texte/tokens réels ≤115 s, admission/comptabilité canoniques ; aucune clé externe configurée |
| Perte/reprise moteur | Arrêt d'Ollama, rejeu connu, nouvel appel interrompu, redémarrage | Résultat connu relu sans moteur ; issue inconnue non rejouée aveuglément ; nouvelle inférence réussie |
| Recherche | Adaptateur Worker → SearXNG → moteurs Web publics | ≥1 source publique ≤65 s ; panne/restriction amont signalée, pas de résultat fabriqué |
| OpenBao | Serveur persistant, token workload et policy de lecture | Lecture Nevolium autorisée ; écriture, autre namespace, liste et administration refusées |
| Sauvegarde hors hôte | Restic chiffré, second job sur autre boot de VM, volumes neufs | Vérification de tous les packs ; SQL, vrai message JetStream, objet filer et secret OpenBao relus |
| Charge légère cible | 1/10/100/1000 clients virtuels, 3 lectures chacun, concurrence ≤20 par défaut | Zéro erreur ; p95 ≤2 s ; arrêt dès échec, 180 s maximum par palier |

Les seuils sont des critères de qualification initiaux, pas une promesse commerciale. Le modèle 0.5B
sert à prouver le câblage et les pannes ; sa qualité ne sélectionne pas le modèle quotidien de Nevolium.
La couche texte PDF ne prouve pas à elle seule les scans/OCR, tableaux complexes et grands documents.
Les scopes Mem0/épisodes Graphiti sont des projections : aucune extraction générative ni mindmap produit
n'est déclarée livrée. La recherche dépend d'amonts publics et peut être limitée sur une IP de CI.

## Préparer les modèles une fois, exécuter sans téléchargement

Sur un environnement de développement isolé avec Docker et le dépôt courant :

```bash
cp .env.example .env
mkdir -p .nevolium-qualification/models .nevolium-qualification/evidence
# Donner à l'UID 10001 l'accès en écriture à ces deux répertoires de préparation/mesure.
docker compose -f compose.yaml -f compose.qualification.yaml build nevolium-model-prepare nevolium-qualification
docker compose -f compose.yaml -f compose.qualification.yaml run --rm --no-deps nevolium-model-prepare
docker compose -f compose.yaml -f compose.qualification.yaml up -d postgres neo4j
docker compose -f compose.yaml -f compose.qualification.yaml run --rm --no-deps nevolium-qualification
```

Ne pas superposer les overlays `qualification` et `production`. La CI conserve les JSON de mesure,
pas les clés ou documents. Un nouveau bundle possède son propre inventaire ; ne pas écraser un bundle
déjà enregistré pour cacher une modification. Le Worker inclut les bibliothèques système requises par OpenCV/RapidOCR ; leurs versions Debian
observées dans le job `103333822364` sont figées dans `services/worker/runtime-packages.txt`.
Une version retirée du miroir fait échouer le build au lieu de choisir une version différente ; conserver
les images construites avec leurs digests pour le rollback. La qualification courante cible Linux x86_64.
Les versions des packages, révisions amont et l'inventaire SHA-256 de tous les fichiers du bundle
sont enregistrés avec les résultats. Les modèles Ollama possèdent leur
digest obtenu par `/api/tags`. La préparation a révélé une dépendance système OCR manquante ; le PDF réel passe désormais
sans réseau. Mem0 créait aussi son dossier SDK sous HOME en lecture seule : son dossier technique
est maintenant dans le TMPDIR de l’enfant, avec historique SQLite en mémoire et télémétrie désactivée.
Les modèles demeurent en lecture seule et les données canoniques restent dans PostgreSQL.
Le matériel, les quotas de conteneur et les pics RSS sont enregistrés ;
un maximum RSS du processus/des enfants est cumulatif, pas une mesure de toute la machine par scénario.

## Cible reçue et répétition ultérieure sur portable

Le serveur netcup RS 4000 G12 est livré et en fonctionnement d'après les captures utilisateur.
Elles montrent Vienne, 12 CPU AMD64, 32 Gio de RAM, un disque de 1 Tio et IPv4/IPv6 attribuées.
Le panneau affiche zéro règle de pare-feu : vérifier la politique effective avant toute installation.
Le type `HDD` affiché pour le périphérique de démarrage ne mesure pas le support NVMe sous-jacent ;
`lsblk` et une mesure ultérieure établiront seulement ce que voit le système invité.
Ne pas versionner hostname fournisseur, IP, MAC, identifiants client ou secrets issus des captures.
Budget préféré 50 €/mois, plafond 90 €, pilote de 3–4 personnes principalement utilisé par une personne.
L'ASUS TUF Gaming A16 FA608PM est une cible locale candidate : Windows x64, Ryzen 9 8940HX,
32 Go de RAM, NVIDIA RTX 5060 Laptop 8 Go avec iGPU Radeon, environ 586 Go libres sur 954 Go.
Aucun résultat du portable ne vaut mesure de netcup, et aucune compatibilité GPU n'est présumée.

Sur Windows, relever dans le Gestionnaire des tâches (Performance) le CPU, la RAM et les GPU,
et dans Paramètres > Système > Informations système la version de Windows. Relever le disque libre.
Ne transmettre ni numéro de série, ni identifiant de produit, ni identifiants de connexion.
Si Linux est déjà installé, utiliser directement l'inventaire ci-dessous.
Windows peut héberger les conteneurs Linux avec WSL2 et Docker Desktop ; utiliser un checkout dans
le système de fichiers Linux de WSL, pas dans /mnt/c. Vérifier la mémoire réellement allouée à WSL/Docker.
Le minimum de Docker ne constitue pas le minimum de toute la pile Nevolium.

Repères de préparation, non mesures : 16 Go physiques conduisent à tester les moteurs successivement ;
32 Go offrent davantage de marge, sans garantir toute la pile simultanée. Garder de la mémoire pour l'OS
et vérifier l'espace nécessaire aux images, caches de build et modèles avant téléchargement.
Ne pas acheter de RAM ou de GPU avant cet inventaire. Première répétition CPU pour rester comparable
au serveur ; accélération GPU éventuelle après identification précise de la carte et de ses pilotes.

Dans un checkout distinct de la branche D04 et un environnement Linux/WSL disposant de Python 3.11+
et Docker opérationnel, commencer par ces lectures sans installation ni démarrage de services :

```bash
python3 scripts/qualification/target.py inventory --output .nevolium-qualification/evidence/laptop-inventory.json
docker version
docker compose version
docker context show
```

Vérifier que le contexte Docker cible le portable, et relever les limites mémoire de Docker/WSL.
L'inventaire voit l'environnement Linux disponible ; ce n'est pas nécessairement toute la RAM physique.
Pour la répétition des moteurs, réutiliser la section « Préparer les modèles » de ce document :
aucune deuxième implémentation ni overlay spécifique ASUS. Employer un projet Compose distinct
(`COMPOSE_PROJECT_NAME=nevolium-d04-laptop`) pour chaque commande de cette répétition. Les ports loopback
restent fixes malgré le nom de projet : vérifier leur disponibilité avant démarrage. Utiliser uniquement
des fixtures et un .env neuf dans ce checkout ; ne jamais écraser la configuration d'une installation existante.
Sous Linux/WSL, donner l'accès UID 10001 uniquement aux dossiers de modèles et de preuves de cette répétition.
La préparation télécharge les modèles ; seul le passage suivant des adaptateurs teste l'absence d'Internet.
Conserver le SHA Git, les JSON et le manifeste. Arrêter en cas d'échec ou de manque de mémoire ;
ne pas élargir les délais pour transformer une mauvaise mesure en succès.

Travail réalisable avant netcup : répétition build/PDF/mémoire CPU, revue de configuration production,
préparation des noms DNS et des secrets sans les versionner, choix du stockage de sauvegarde indépendant,
et préparation du scénario de mise à jour/restauration déjà décrit dans deployment/operations.
Les tests lourds de panne/restauration des workflows restent sur des environnements jetables dédiés.
Les preuves CI existantes évitent de relancer toute la campagne uniquement pour attendre un serveur.

Qwen3 4B et 8B sont candidats à comparer, 14B un essai conditionnel à la marge mémoire ; aucun modèle
quotidien n'est encore validé. Mesurer un seul modèle chargé et une génération à la fois, avec contexte
borné identique, puis ingestion documentaire concurrente. Consigner qualité sur demandes françaises,
temps avant premier token, durée complète, mémoire totale et latence des lectures Nevolium. Le modèle
0.5B des fixtures conserve son rôle de preuve de câblage ; ne pas le remplacer silencieusement.

Sur netcup : reprendre l'inventaire serveur, production/TLS/authentification, preflight,
parcours canonique, charge mixte et restauration hors hôte. Le portable peut alors servir de client de
mesure indépendant. D04 reste ouvert ; les vues Mycelium/Gantt/mindmap restent dans les lots prévus.

Référence installation : [Docker Desktop Windows / WSL2](https://docs.docker.com/desktop/setup/install/windows-install/).

## Inventaire et charge sur la cible privée

Le serveur netcup est livré et son socle Debian durci a été vérifié manuellement, y compris après un
cold boot : accès par clé, SSH sans root/mot de passe, maintenance automatique, journalisation,
Fail2ban, pare-feu hôte/fournisseur et connectivité IPv4/IPv6. Le rapport public est volontairement
expurgé de toutes les valeurs d'accès : [socle serveur](archive/server-foundation-2026-09-11.md).
Docker, le stockage de sauvegarde indépendant et la campagne Nevolium restent à réaliser. Les commandes
suivantes sont prêtes pour la cible retenue après installation contrôlée :

```bash
python scripts/qualification/target.py inventory --output .nevolium-qualification/evidence/server-inventory.json
# Après configuration production validée et authentification réelle :
uv run --locked --project services/worker python scripts/qualification/target.py preflight \
  --core https://api.example.org --tokens-file /chemin/prive/access-tokens.json \
  --output .nevolium-qualification/evidence/server-access.json
uv run --locked --project services/worker python scripts/qualification/target.py load \
  --core https://api.example.org --tokens-file /chemin/prive/access-tokens.json \
  --output .nevolium-qualification/evidence/target-load.json
```

Avant de cloner le dépôt ou d'installer des paquets, ouvrir une première session SSH depuis le PC de
l'opérateur et exécuter uniquement cet inventaire sans secrets :

```bash
cat /etc/os-release
uname -m
nproc
free -h
lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS
df -hT /
python3 --version || true
git --version || true
docker --version || true
docker compose version || true
```

Ne pas transmettre le mot de passe root, une clé privée, `/etc/shadow`, les variables d'environnement
ou les fichiers de configuration SSH. Une fois l'accès confirmé, créer l'accès par clé d'un compte
d'administration, vérifier une seconde connexion dans un autre terminal, puis seulement désactiver
l'authentification root/mot de passe. Appliquer la politique pare-feu hôte et fournisseur en conservant
la session active et la console de secours. SSH est limité à l'adresse opérateur ; 80/443 ne sont ouverts
qu'au moment de configurer l'ingress. PostgreSQL, Neo4j, NATS, OpenBao, Ollama et les interfaces
d'administration ne sont jamais publiés. Créer un snapshot après mise à jour et durcissement, avant le
déploiement ; ce snapshot ne remplace pas la restauration Restic hors hôte.

Le fichier de tokens est un tableau JSON de jetons d'accès, jamais committé. Les jetons ne sont pas
imprimés. L'inventaire doit être lancé sur le serveur ; le matériel enregistré par la commande `load`
est celui du générateur de charge, qui peut être une autre machine. Le rapport distingue clients virtuels,
comptes réellement utilisés, requêtes et concurrence. Un contrôle préalable refuse de mesurer une
cible qui accepte l'accès anonyme aux projets.
1000 clients utilisant un compte ne deviennent pas 1000 utilisateurs authentifiés distincts. Cette
charge ne fait que lire ; elle ne mesure pas 1000 générations IA simultanées. Les tests D02 restent
la preuve des transactions d'admission et rafales synthétiques ; ne pas dupliquer ce simulateur ici.

Le contrôle `preflight` fait dix lectures au maximum : accès anonyme et faux jeton refusés, puis
réponses JSON Nevolium attendues sur projets/Today/capacité avec le premier jeton fourni ; enfin refus
403/404 sur cinq chemins privés (`/internal/v1/work-capacity/acquire`, `/docs`, `/redoc`, `/openapi.json`,
`/health/trust`). Un 405 indique que l'ingress laisse atteindre la route ; une redirection ou une
page HTML avec statut 200 ne vaut pas une API valide. Les trois lectures authentifiées ne prouvent
pas l'isolation entre tous les comptes ; les autres jetons seront utilisés lors des paliers de charge.

Le contrôle est automatiquement répété avant `load`. Les lectures de charge vérifient elles aussi
la forme JSON, avec Today limité à 20 par catégorie. Taille de réponse ≤2 Mio, délai total ≤10 s par
requête, timeout socket 5 s ; réponses compressées refusées (Accept-Encoding: identity), redirections
et proxys ambiants désactivés. Le rapport garde des codes de diagnostic, jamais les jetons ni le contenu
des réponses. Un échec préalable préserve le rapport et empêche tout palier de charge.

TLS vérifie certificat et nom d'hôte ; pour une PKI privée, ajouter `--ca-file /chemin/ca.pem` après
vérification opérateur de cette CA. Aucune option ne désactive la vérification TLS. HTTP reste permis
sur loopback pour les fixtures, explicitement sans preuve TLS. Les chemins privés sont sondés en GET
uniquement : aucun POST de mutation, scan de ports ou effet externe. Ce contrôle ne remplace pas
la revue des règles proxy pour toutes les méthodes, les droits internes SQL/réseau et le parcours
utilisateur réel. Le test HTTP/TLS en CI qualifie cet outil, pas un proxy de production déployé.

## Restauration et passage de H5

Le scénario CI transfère uniquement un dépôt Restic chiffré contenant des données originales de test.
Sa phrase de passe publique et son séquestre de clés OpenBao **sont des fixtures** ; les vraies clés de
récupération doivent être conservées séparément du backup et du serveur. Le contrôle d'un boot différent
prouve deux environnements système distincts, pas la séparation géographique de deux centres de données.
La conservation des artefacts CI est courte ; les résultats essentiels doivent aussi être résumés dans
le rapport versionné, avec les IDs des jobs.

Pour la cible : utiliser [deployment](deployment.md) et [operations](operations.md), backup quiescent,
destination chiffrée indépendante, vérification `restic check --read-data`, restauration sur volumes neufs,
déscellement OpenBao et relecture d'une Task, d'un document, d'un événement et d'un secret de test. Conserver
les IDs de workflow et les obligations financières ; aucune lease ni dépense inconnue effacée.

D04/H5 demeure incomplet tant que les éléments suivants manquent : scénario canonique complet sur la
cible retenue (PDF/mémoire/recherche/modèle réellement choisi), charge mesurée et files en usage mixte,
proxy TLS et refus des routes internes, droits réseau/SQL sur cible, upgrade/rollback compatible,
restauration indépendante avec récupération des clés et vérification utilisateur. Un fournisseur externe
reste optionnel et nécessite une configuration/autorisation existante ; aucun achat n'est requis par ce lot.
Ne pas déplacer ces conditions vers un nouveau sous-lot pour déclarer D04 terminé. D05 attend la sortie H5.

## Sources et récupération sélective

- Le prototype d'interface historique (`ed12d503…`) contient une policy OpenBao et son test textuel.
  Le principe de namespace est repris ; ses écritures/effacements liés au futur cycle de compte ne sont
  pas accordés au Core actuel, qui lit seulement les valeurs/statuts. La preuve D04 utilise le serveur réel.
- Le réservoir `consolidate/g49-research-durable-stages` (`57a1a217…`) possède le même adaptateur Mem0/Graphiti
  antérieur ; il n'apporte pas de preuve de modèles hors ligne ou de restauration sur deux hôtes.
- [Docling : modèles préchargés et options](https://docling-project.github.io/docling/usage/advanced_options/).
- [FastEmbed 0.8.0](https://github.com/qdrant/fastembed/tree/v0.8.0) et
  [adaptateur Mem0 2.0.20](https://github.com/mem0ai/mem0/blob/v2.0.20/mem0/embeddings/fastembed.py).
- [Modèle de qualification Ollama](https://ollama.com/library/qwen2.5:0.5b) et
  [API d'inventaire avec digest](https://docs.ollama.com/api/tags).
