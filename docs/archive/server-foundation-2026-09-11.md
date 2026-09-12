# D04 — socle serveur privé validé le 11 septembre 2026

Ce rapport conserve le jalon opératoire vérifié avant puis pendant l'installation de Docker. Il ne contient ni
adresse IP/MAC, identifiant fournisseur, compte d'administration, clé, empreinte de clé, secret ou
capture du panneau. Les valeurs propres à l'installation restent dans le registre d'exploitation privé.

## Cible et limites du jalon

- Netcup RS 4000 G12, Linux AMD64 virtualisé KVM, 12 vCPU, 32 Gio de RAM et disque d'environ 1 Tio.
- Debian 13 (trixie), noyau `6.12.107+deb13-amd64`, horloge UTC et synchronisation NTP active.
- Nom d'hôte court et FQDN cohérents ; résolution locale normalisée. Cloud-init est désactivé sur l'image
  fournisseur et ne réécrit pas ces valeurs.
- Ce jalon qualifie l'accès, le socle système et l'exécution Docker. Il ne qualifie encore ni Nevolium, ni TLS,
  ni les moteurs, ni les sauvegardes applicatives.

## Accès administratif

- Compte non-root dédié, membre de `sudo`, avec authentification Ed25519 protégée par phrase secrète.
- Nouvelle session par clé vérifiée avant fermeture de l'accès initial et de nouveau après les deux
  pare-feu puis après un cycle d'arrêt/rallumage fournisseur.
- SSH effectif : root et mots de passe interdits, clé publique obligatoire, utilisateur autorisé borné,
  trois essais, cinq sessions, délai de connexion 30 secondes, X11/agent/tunnel interdits et transfert
  TCP limité au local.
- La console fournisseur reste la voie de récupération. La clé privée et sa phrase secrète ne résident
  ni dans Git, ni sur le serveur.

## Maintenance et journalisation

- `unattended-upgrades`, les deux timers APT, Fail2ban et `netfilter-persistent` sont activés et persistants.
- Mises à jour automatiques quotidiennes, nettoyage hebdomadaire, noyaux inutilisés supprimables et
  redémarrage automatique interdit. Le dry-run s'est terminé avec le code 0.
- Journal systemd persistant, compressé et scellé, plafond 1 Gio, réserve disque 5 Gio, plafond runtime
  256 Mio et rétention maximale 30 jours.
- Fail2ban utilise le backend systemd et l'action `iptables-multiport` pour SSH : quatre échecs sur dix minutes,
  bannissement initial d'une heure, croissance jusqu'à une semaine. Configuration, socket et jail SSH
  ont été vérifiés après redémarrage.

## Défense réseau en profondeur

Le premier snapshot hors ligne conserve le socle nftables antérieur à Docker. L'hôte courant a ensuite
été migré vers `iptables-nft`, backend pris en charge par Docker : chaînes INPUT et FORWARD à refus par
défaut, OUTPUT autorisée, loopback, états `established,related`, ICMP/ICMPv6 et nouveaux flux TCP vers
22/80/443 acceptés. Les fichiers IPv4/IPv6 sont restaurés par `netfilter-persistent` ; l'ancien service
nftables est désactivé. PostgreSQL, NATS, Neo4j, OpenBao, Ollama et les interfaces d'administration ne
doivent jamais être publiés.

Le pare-feu fournisseur applique avant ses règles implicites une politique personnalisée :

- entrées TCP 22, 80 et 443 autorisées ;
- ICMP et ICMPv6 autorisés ;
- réponses entrantes DNS TCP/UDP, HTTP/HTTPS TCP, NTP UDP et HTTPS UDP autorisées explicitement pour
  rester compatibles avec un filtrage fournisseur sans état documenté ;
- autres entrées TCP et UDP refusées ;
- blocage fournisseur par défaut des sorties SMTP 25/465/587 conservé.

Le pare-feu hôte avec suivi d'état reste l'autorité fine : une source distante utilisant un port source
autorisé par la couche fournisseur n'obtient pas pour autant l'accès à un port local arbitraire. Le
blocage SMTP empêche pour l'instant l'envoi direct via un relais SMTP, y compris Infomaniak ; choisir
et tester ultérieurement une API transactionnelle ou une exception de relais bornée.

## Preuves observées et reprise

- DNS, APT, ping IPv4/IPv6 et HTTPS IPv4/IPv6 réussis après application du pare-feu fournisseur.
- Arrêt propre puis rallumage exigé par le panneau Netcup effectué.
- Après le premier cold boot : SSH par clé, nftables, Fail2ban et timers APT actifs ; règles restaurées ;
  réponses HTTPS IPv4 et IPv6 `200`.
- Debian n'annonçait aucun redémarrage en attente et le noyau courant correspondait au noyau attendu.
- Snapshot fournisseur hors ligne créé avant Docker. La migration suivante vers `iptables-nft` a elle
  aussi survécu à un redémarrage : règles IPv4/IPv6, bannissement Fail2ban et connectivité HTTPS conservés.
- Docker Engine 29.8.0, containerd 2.3.5, Buildx 0.37.1 et Compose 5.5.1 installés depuis le dépôt Docker
  officiel pour Debian 13. `overlayfs`, cgroups v2/systemd et le conteneur `hello-world` ont été vérifiés.
- Démon Docker : `live-restore` actif et journaux `local` bornés à cinq fichiers de 10 Mio. Un
  `ExecStartPost` recalcule l'interface externe et peuple `DOCKER-USER` à chaque démarrage : connexions
  établies puis ports originaux 80/443 acceptés, autres nouveaux flux externes vers des conteneurs refusés.
  Le compte d'administration n'est pas membre du groupe root-equivalent `docker`.

## Extension vérifiée le 12 septembre — OpenBao

- OpenBao 2.6.2 utilise seul son backend fichier persistant ; aucun autre service Nevolium n'est démarré.
- Initialisation avec trois parts de déscellement et seuil de deux, puis reprise contrôlée après deux
  incompatibilités CLI détectées sans perte du matériel de récupération.
- Jeton de workload périodique orphelin de sept jours, sans policy `default` ; lecture du namespace
  Nevolium, introspection et renouvellement propres autorisés, quatre opérations hors portée refusées.
- Environnement et métadonnées du workload détenus par root en mode 0600 ; garde de production accepté,
  service sain et port OpenBao 8200 absent des sockets publiées de l'hôte.
- Matériel de récupération exporté avec une identité age dédiée, puis paquet protégé par une phrase secrète
  distincte. Déchiffrement et structure 3 parts/seuil 2 vérifiés en mémoire sur le poste Windows, sans JSON
  clair ; copie cloud privée retéléchargée avec empreinte SHA-256 identique. La phrase secrète reste séparée.
- Jeton root initial révoqué après renouvellement probant du workload ; fichier clair et export intermédiaire
  retirés du serveur. Le workload orphelin reste valide et les parts hors serveur permettent une procédure
  exceptionnelle de génération d'un nouveau root.
- Renouvellement systemd quotidien à 03:17 UTC, persistant et dispersé de trente minutes. L'unité lie le
  jeton à son accessor, exige policy/période/orphelin/TTL et nettoie son fichier temporaire. Le premier essai
  a refusé la traversée du checkout privé avant toute mutation et sans activer le timer ; le correctif limite
  la capacité à `CAP_DAC_READ_SEARCH`. Le second essai a renouvelé à 604799 secondes, activé le timer et
  confirmé l'absence du jeton temporaire, des copies serveur et de dégradation OpenBao.

## Extension vérifiée le 12 septembre — PostgreSQL et identité

- PostgreSQL de production a été créé sur un volume neuf, déclaré sain et conservé derrière les réseaux
  Docker sans publication du port 5432. Les rôles `nevolium_app`, `nevolium_migrator`, `keycloak_app` et
  `temporal_app` ont été provisionnés avant l'application transactionnelle de la chaîne Alembic jusqu'à
  `0014_capacity_and_data`.
- Keycloak 26.7.3 utilise sa base dédiée et publie son service uniquement sur `127.0.0.1:8081`. L'adresse
  de proxy de confiance a été dérivée de la passerelle privée du réseau ingress et écrite atomiquement
  dans l'environnement root 0600, sans valeur réseau versionnée ni affichée.
- Le realm de production `nevolium` a été importé vide. Son document de découverte, interrogé localement
  avec les en-têtes du futur proxy TLS, expose exactement l'issuer
  `https://auth.nevolium.com/realms/nevolium`. Le premier compte applicatif a ensuite été créé avec le rôle
  `nevolium-user`. Après correction contrôlée de son adresse avant connexion, la première connexion a remplacé
  le mot de passe temporaire et enregistré le TOTP ; la vérification administrative confirme le compte actif,
  le TOTP présent et aucune action initiale restante.
- Deux essais ont échoué de manière sûre avant cette preuve : la valeur sentinelle du proxy a provoqué une
  boucle arrêtée sans import ; la variable du realm manquante a ensuite fait refuser le fichier d'import.
  Aucun realm partiel n'est resté en base. Les deux causes ont été corrigées et les contrats associés passent
  dans les dix workflows GitHub du commit `b2648de…`.

## Extension vérifiée le 12 septembre — socle interne

- NATS 2.14.5 est sain sur les réseaux internes canonique/exécution. JetStream stocke sous
  `/data/jetstream` dans le volume `nevolium_nats_data` ; aucun port 4222/8222 n'est publié. Le premier
  contrôle a attendu à tort `/data`, puis a arrêté NATS proprement avant une vérification corrigée.
- SeaweedFS 4.46 utilise le volume `nevolium_seaweed_data`, et Master comme S3 répondent depuis le réseau
  canonique sans publication hôte. Un premier sondage depuis l'hôte a été bloqué par l'isolation prévue ;
  le sondage interne suivant a révélé que le processus attaché à deux réseaux choisissait seulement son
  interface `telemetry`. Le correctif `-ip=seaweedfs -ip.bind=0.0.0.0` rend son identité et ses services
  accessibles sur les deux ponts internes, sans port hôte ; le volume existant a été conservé.
- Temporal 1.31.2 est sain sur les réseaux canonique/exécution sans publier 7233. Les schémas
  `temporal` et `temporal_visibility` sont présents dans PostgreSQL, le namespace `default` est joignable,
  et les deux conteneurs ponctuels d'installation SQL et de création de namespace sont sortis avec le code 0.
- Le commit de correction SeaweedFS `b5acf0e…` passe les dix workflows GitHub avant son installation sur
  la cible. NATS, SeaweedFS et Temporal restent opérationnels après leurs contrôles croisés.

## Extension vérifiée le 12 septembre — Core et Web

- Core est construit et actif sur `127.0.0.1:8000`. Ses contrôles de disponibilité confirment
  PostgreSQL, NATS, Temporal et SeaweedFS ; sa frontière de confiance confirme Keycloak, OpenBao et S3.
  L'appel anonyme et celui muni d'un faux bearer sont refusés par 401.
- Le jeton workload OpenBao de Core réalise une lecture autorisée sans disposer du jeton root. Le
  conteneur s'exécute avec l'UID/GID applicatif, racine en lecture seule, toutes capacités retirées et
  `no-new-privileges`, sur les seuls réseaux prévus.
- Web sert le build statique de production sur `127.0.0.1:5173`. Les URLs exactes de l'API et de Keycloak
  sont présentes dans les artefacts ; la page d'entrée, le repli SPA, les refus 404/405 et les en-têtes
  `nosniff`, `DENY` et `same-origin` sont vérifiés.
- Web est non-root, en lecture seule, sans capacité Linux et limité au réseau `frontend`. Core et Web ne
  sont donc joignables que depuis l'hôte ; aucune exposition Internet applicative n'est encore active.

## Extension vérifiée le 12 septembre — ingress TLS public

- L'installation du paquet Caddy a bloqué son démarrage automatique jusqu'au remplacement de la page par
  défaut par la configuration versionnée. Le fichier root 0644 a été formaté et validé avant activation.
- Caddy obtient et sert des certificats publics valides pour `app.nevolium.com`, `api.nevolium.com` et
  `auth.nevolium.com`. Les trois redirections HTTP vers HTTPS et la suppression de l'en-tête serveur sont
  confirmées depuis un client Windows extérieur ; l'administration reste sur `127.0.0.1:2019`.
- Web et le document de découverte Keycloak répondent publiquement avec l'issuer exact. Sur l'API, la
  racine, les sondes, la documentation et les chemins internes sont refusés par 404 ; `/v1` refuse par 401
  la requête anonyme comme celle munie d'un faux bearer.
- Le premier compte nominatif et son enrôlement MFA sont vérifiés. Depuis un client Windows, Web a achevé
  Authorization Code + PKCE sans exposer le jeton, puis `/v1/today` a rendu l'état vide du propriétaire.
  Cette réponse n'est produite qu'après validation par Core de la signature, de l'issuer, de l'audience,
  de l'azp et du rôle `nevolium-user` ; les refus anonyme et faux bearer restent également prouvés.
- Un second compte nominatif, distinct, porte `nevolium-admin` et le composite
  `realm-management/realm-admin` du seul realm Nevolium. Mot de passe initial remplacé, TOTP, absence
  d'action restante et rôles ont été vérifiés ; une connexion Windows affiche la console administrative
  du realm. Le bootstrap `master` reste intact jusqu'à la preuve d'un redémarrage sans ses variables.

Prochain point sûr : recréer Keycloak avec la topologie normale sans environnement bootstrap, revérifier
la console nominative, puis retirer le compte et les identifiants bootstrap. Le paquet de clés ne remplace pas le futur
backup Restic chiffré, indépendant du serveur et restauré sur volumes neufs.
