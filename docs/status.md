# Nevolium — état fonctionnel vérifié

Révision : 2026-09-13, D03 terminé par #87 ; D04/H5 actif dans #88.
Toujours vérifier le live ; branche/PR/lot actif dans [PROJECT_STATE](../PROJECT_STATE.md).

## Complément courant : mémoire et incident sémantique

Les contrôles opérateur ont prouvé Mem0 sur le bon propriétaire, un scope étranger vide, un épisode
Graphiti et le rejeu mémoire génération 2 sans doublon. Le correctif sémantique `dd20b002…` est actif :
appel modèle 110 s, heartbeat 120 s, activité 180 s, sortie limitée à 256 jetons. Après déchargement
explicite du modèle, une commande termine en 61,34 s avec 1176 jetons ; modèle préchargé, une seconde
termine en 50,43 s avec 1118 jetons. Coût local nul déclaré et réservation réglée dans les deux cas.
Le second essai révèle cependant une erreur de pertinence : le modèle propose `news.brief` à 90 % malgré
« classe uniquement » et « ne lance aucune action », et Core crée une Task News terminée. Le correctif
`e3adbe6…` ajoute le veto déterministe dans Core et passe 10/10 workflows. La CI force une proposition
`news.brief` valide et confiante, puis prouve son refus et l'absence de Task métier. Sur la cible, une
nouvelle commande termine en 59,57 s avec `semantic.execution-veto`, zéro Task métier, un usage modèle
et une réservation réglée. Le modèle cible a lui-même répondu `unsupported` sans capacité proposée :
cette exécution confirme le déploiement et le refus, tandis que la CI qualifie la frontière avec une
proposition valide. La commande News historique et les anciennes réservations inconnues restent inchangées.
Le préflight Research trouve ensuite zéro serveur et zéro outil Web enregistré. La première activation
isolée de l'adaptateur est refusée par Docker avant création : la forme YAML compacte du TMPFS sépare
`mode=1777` en faux chemin relatif. Le nettoyage automatique retire le conteneur ; Worker, registre et
services publics restent inchangés. La correction rend le montage unique et le garde de production
refuse désormais tout chemin TMPFS non absolu. Le commit `db3da89…` passe ensuite 10/10 workflows,
est synchronisé et permet l'activation isolée du Web MCP. Le conteneur reste limité aux réseaux
`search` et `egress`, sans port hôte ni jeton interne, avec racine en lecture seule, capacités supprimées
et TMPFS `/tmp` valide. Son catalogue réel contient exactement les outils en lecture seule `search` et
`fetch` ; `web.search` renvoie trois sources publiques et `web.fetch` refuse une destination loopback.
Le Worker existant n'est pas recréé, les services publics restent sains et le registre canonique demeure
vide. Après synchronisation du checkpoint, une session OIDC éphémère de l'administrateur nominatif crée
exactement un serveur `nevolium-web`, synchronise exactement `web.search` et `web.fetch`, puis active les
deux politiques en autorité A1, lecture seule, rejeu sûr et coût nul. La vérification SQL en lecture seule
confirme les comptes `1|1|2|2|2|0|0` : serveur unique attendu, deux outils exacts et actifs, aucun doublon
de clé, namespace ou nom distant. Le jeton n'est ni versionné, ni écrit dans l'environnement de production,
ni conservé après la commande. Le parcours Research authentifié de bout en bout reste requis.

Les sections ci-dessous conservent l'historique des paliers. Six espaces UI sont raccordés, pas quinze
modules futurs ; le cockpit Mycelium reste D05. L'erreur partagée Command/News, les débordements de panneaux
et la qualité des réponses ne sont pas corrigés par ce changement de budget.

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
([ADR-030](decisions/ADR-030-nevolium-canonical-identity.md)) avant le premier déploiement. Le head
`d9478de…` et son arbre `898306b…` passent 10/10 workflows et 5/5 jobs D04 ; le dépôt GitHub
s'appelle désormais `fredbuhr/nevolium`, et le remote local a été vérifié après la bascule.
[Preuves de transition](archive/nevolium-identity-transition-2026-09-11.md).
Docling/PDF et Mem0/Graphiti en lecture seule sans Internet, inférence locale avec comptabilisation,
arrêt/rejeu/redémarrage d’Ollama et recherche SearXNG ont passé des essais réels CPU sur la branche.
Le premier head de campagne `10cb57c…` avait passé 9/9 workflows, dont les cinq jobs D04 ; ces preuves
ont ensuite été rejouées avec succès sur le head Nevolium cité plus haut. La restauration sur une autre
VM relit SQL, message JetStream, objet filer et secret OpenBao. [Rapport, mesures et inventaire des modèles](archive/qualification-d04-2026-09-11.md).
Corrections trouvées : bibliothèques natives OCR absentes, écritures techniques Mem0 hors TMPDIR,
configuration OpenBao persistante incompatible avec sa version épinglée. La cible privée reste à qualifier ;
ne pas utiliser les résultats de branche comme une validation de production du main D03.

Le premier socle serveur privé est désormais vérifié avant déploiement : Debian 13, administration
non-root par clé, SSH sans root/mot de passe, mises à jour automatiques, journald persistant, Fail2ban,
pare-feu hôte à refus entrant-by-default et pare-feu fournisseur. Un cold boot a conservé l'accès et les
services ; DNS, APT, ICMP et HTTPS fonctionnent en IPv4/IPv6. Aucun moteur Nevolium, TLS applicatif ou
backup indépendant n'est qualifié par ce jalon. [Preuve expurgée](archive/server-foundation-2026-09-11.md).
Un snapshot hors ligne a ensuite précédé l'installation officielle de Docker Engine 29.8.0 et Compose
5.5.1. Le pare-feu hôte a été migré vers iptables-nft persistant, Fail2ban vers son action iptables et
la chaîne `DOCKER-USER` refuse les publications externes hors 80/443. Le démon utilise `live-restore`
et le pilote de logs local borné. OpenBao 2.6.2 utilise un backend persistant,
trois parts de déscellement avec seuil deux, jeton de workload périodique de sept jours sans policy
`default`, lecture Nevolium et renouvellement/introspection propres vérifiés. La récupération a été
chiffrée avec une identité dédiée, déchiffrée et contrôlée hors serveur sans fichier clair, puis sa copie
cloud privée retéléchargée avec une empreinte identique. Le jeton root initial est révoqué et les copies
serveur sont retirées. L'environnement et les métadonnées workload restent root 0600. Un service systemd
lie le jeton à son accessor, vérifie policy/période/TTL et le renouvelle quotidiennement ; son timer
persistant est actif après un passage réel réussi à 604799 secondes de TTL. Un premier refus dû au retrait
total des capacités Linux s'est produit avant renouvellement et activation ; `CAP_DAC_READ_SEARCH` seul
a corrigé la traversée en lecture du checkout privé. OpenBao reste sain et son port 8200 n'est pas publié.

Le déploiement par paliers a ensuite créé un volume PostgreSQL neuf : service sain, port 5432 non publié,
quatre identités SQL minimales provisionnées et migrations canoniques appliquées jusqu'à
`0014_capacity_and_data`. Keycloak 26.7.3 utilise sa base dédiée et écoute seulement sur
`127.0.0.1:8081`. Son proxy de confiance est lié à l'adresse privée exacte de la passerelle ingress ; le
realm de production `nevolium` a été importé vide et son issuer vaut exactement
`https://auth.nevolium.com/realms/nevolium`. Le premier compte applicatif a ensuite été créé avec le seul
rôle `nevolium-user` ; après la première connexion, la vérification administrative confirme le compte actif,
le TOTP configuré et l'absence d'action initiale restante. Un premier démarrage a refusé le placeholder de proxy, puis
un second a révélé que la variable du realm n'était pas transmise au conteneur ; chaque tentative a été
arrêtée sans realm partiel, corrigée dans la même branche et couverte par les dix workflows réussis sur
`b2648de…`.

Le palier interne suivant est lui aussi vérifié sur la cible. NATS 2.14.5 est sain, JetStream utilise
`/data/jetstream` dans son volume persistant et aucun port 4222/8222 n'est publié. SeaweedFS 4.46 sert
Master et S3 depuis le réseau canonique, conserve son volume et ne publie aucun port. Le premier essai
multiréseau a montré qu'il choisissait et annonçait seulement l'interface `telemetry` ; l'identité stable
`-ip=seaweedfs` et l'écoute `-ip.bind=0.0.0.0` corrigent le routage sur les deux réseaux sans ouvrir l'hôte.
Temporal 1.31.2 est sain, ses schémas d'exécution/visibilité sont présents dans PostgreSQL, le namespace
`default` répond et le port 7233 reste interne. Les tâches ponctuelles SQL et namespace sont sorties avec
le code 0. Le correctif SeaweedFS `b5acf0e…` et le checkpoint documentaire `73492a9…` passent chacun
10/10 workflows.

Core et Web sont désormais vérifiés sur la cible. Core répond sur `127.0.0.1:8000`, confirme ses quatre
dépendances et ses trois frontières de confiance, refuse l'accès anonyme comme un faux bearer, et utilise
le jeton workload OpenBao sans élargissement de policy. Web sert le build de production sur
`127.0.0.1:5173` ; les URLs publiques API et Keycloak sont embarquées, le routage SPA, les refus 404/405
et les en-têtes de sécurité sont vérifiés. Les deux conteneurs sont non-root, en lecture seule, sans
capacités Linux et limités aux réseaux prévus. Worker reste arrêté.

Caddy est installé depuis le paquet de la distribution après blocage explicite du démarrage de sa page
par défaut. La configuration versionnée a été formatée, validée puis activée. Depuis un client Windows
extérieur, `app`, `api` et `auth` présentent des certificats et noms valides, redirigent HTTP vers HTTPS,
servent Web et le bon issuer Keycloak. La racine et les chemins privés de l'API répondent 404 ; l'accès
à `/v1` sans jeton ou avec un faux jeton répond 401. L'administration Caddy écoute seulement sur
`127.0.0.1:2019`. Le premier utilisateur réel et son enrôlement MFA sont qualifiés. Depuis Windows,
le cockpit obtenu après Authorization Code + PKCE a chargé `/v1/today` sans erreur ; Core a donc validé
le vrai bearer, son audience/issuer/azp et le rôle `nevolium-user`, puis appliqué la lecture owner-scoped.
Un administrateur nominatif distinct du seul realm Nevolium est maintenant actif avec TOTP, rôle
applicatif `nevolium-admin` et composite `realm-management/realm-admin`. Ces droits et l'absence d'action
initiale ont été vérifiés par la commande bornée ; une connexion Windows affiche réellement la console du
realm Nevolium. La branche réserve les variables bootstrap à un overlay initial explicite et exige un
redémarrage sans cet environnement avant suppression. Cette première gate est passée sur la cible :
Keycloak a été recréé sans les deux variables de conteneur ; son issuer est resté sain, puis `fred-admin`
a terminé une nouvelle authentification MFA et rouvert la console du realm.
La seconde gate a ensuite supprimé exactement le bootstrap `master`, prouvé le refus de ses anciens
identifiants et retiré atomiquement ses deux secrets du fichier privé root 0600. La topologie normale,
Keycloak et Caddy sont restés sains ; une authentification MFA neuve de `fred-admin` a encore rouvert la
console après le retrait. Aucun accès bootstrap de production ne subsiste.
Le bundle hors ligne requis par Worker est également préparé sur la cible : les quatre révisions amont et
les empreintes de huit poids correspondent au manifeste D04 archivé. Il est root-owned, destiné au montage
en lecture seule et référencé par le fichier privé. Aucun moteur n'avait été activé pendant cette préparation.
Le premier palier moteur est désormais actif sans port hôte : Neo4j, Valkey/SearXNG et Ollama ont chacun
réussi leur contrôle interne. Le modèle `qwen2.5:0.5b` n'a été accepté qu'après correspondance de son digest
complet `a8b0c515…f1827c67` avec D04 ; Ollama a ensuite redémarré dans le seul réseau `models`, sans egress.
LiteLLM est également actif sans port hôte, avec `local-fast` fixé sur ce modèle qualifié et aucune clé
OpenAI ou Anthropic chargée. Une vraie réponse locale et son comptage ont traversé le relais ; un faux jeton
a été refusé avec 401. Ollama reste hors egress et les services publics sont restés sains.
Le Worker complet est désormais actif avec son bundle exact en lecture seule et ses bibliothèques de modèles
forcées hors ligne. Il s'exécute sous UID 10001, sur un rootfs en lecture seule, sans capacité Linux, nouveau
privilège ou port hôte, avec limites CPU/RAM/PID et six réseaux bornés. Il a réellement terminé un workflow
Temporal minimal et enregistré son consumer mémoire durable JetStream.

Le premier parcours métier `news.brief` a ensuite terminé en production avec dix sources owner-scoped.
La synthèse LiteLLM a expiré au délai borné ; le fallback déterministe a produit le briefing sans inventer
un usage modèle. La réservation sans réponse reste donc `uncertain`. Le routage sémantique du Command
Center a également traversé le Worker et `local-fast` : 924 jetons de prompt, 101 de complétion, 1025 au
total et limite de sortie 256 respectée. La proposition prudente `semantic.unsupported` a été refusée par
Core et correctement affichée dans le panneau Command.

LiteLLM déclare désormais explicitement le coût nul de l'alias local, et le Worker reconnaît l'absence
d'en-tête de coût comme zéro confirmé uniquement pour cet alias qualifié. La nouvelle réservation a été
réglée directement ; l'ancien usage local identique a été réconcilié par rejeu idempotent de l'API
canonique, sans doublon ni mutation métier. Le timeout News sans usage est resté inchangé.

Le parcours PDF réel owner-scoped est également qualifié. Le premier essai a échoué avant parsing parce que
Worker ne pouvait ni résoudre ni joindre SeaweedFS ; la version `v1` et son erreur ont été conservées.
Un réseau Docker interne dédié `assets` relie désormais Worker et SeaweedFS sans élargir `canonical`
vers Worker ni `egress` vers le stockage. La réingestion du même objet SHA-256 a produit une `v2`
Docling 2.126.0 terminée avec un chunk canonique contenant le marqueur de qualification. PostgreSQL confirme
deux générations, la cohérence du propriétaire entre projet, asset et document, et l'absence d'erreur sur
`v2`. Aucun port hôte n'a été ajouté et les services publics sont restés sains.

Une campagne intermédiaire réexécutée sur `a5a61db…` avait également passé 9/9 workflows et 5/5 jobs D04.
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
| État durable | PostgreSQL migré, NATS/JetStream, SeaweedFS et Temporal/namespace `default` actifs sur réseaux internes ; Core relit ses dépendances ; migrations jusqu'à `0014_capacity_and_data`, pagination SQL et rétention technique | Parcours Worker, dimensionnement réel, archivage canonique et charge sur matériel identifié |
| Exécution Worker | Parsing borné/annulable, admission partagée, bundle exact hors ligne ; Worker confiné, Temporal et JetStream actifs ; Neo4j, Valkey/SearXNG, Ollama et LiteLLM sans port hôte ; parcours News, routage sémantique et PDF Docling réellement exécutés | Parcours mémoire/recherche, puis mesure progressive et campagne de charge sur le matériel cible |
| Identité et actions | Keycloak et Core derrière Caddy/TLS public ; utilisateur et administrateur nominatifs actifs avec TOTP et rôles bornés ; bootstrap `master` et secrets privés retirés après redémarrage sans environnement bootstrap ; connexions MFA, Authorization Code + PKCE/lecture owner-scoped et refus anonyme/faux jeton vérifiés | UX de rapprochement des coûts incertains |
| Intelligence | Routing/recherche, Context Packs et gateway avec admission, sortie 256 bornée et replay comptable ; `local-fast` exécuté à coût nul explicite, 924/101/1025 jetons comptés, réservation réglée et ancien usage réconcilié ; timeout sans réponse conservé incertain | Choix utilisateur du modèle quotidien/des clés, UX Agents/Skills et parcours mémoire/recherche |
| Documents et mémoire | Ingestion/version/chunks et inspection Web ; PDF réel owner-scoped réingéré par Docling 2.126.0 en un chunk canonique, source SHA-256 et échec antérieur conservés ; projections mémoire reconstruisibles | CI Documents emploie le fallback texte et mémoire des stubs ; vraie intégration Mem0/Graphiti à mesurer en D04 |
| Cockpit | Web de production publié par Caddy/TLS ; OIDC nominatif/PKCE, panneaux persistés, Command Center, Projects, Today, Research, News et Knowledge ; états terminaux sémantiques affichés dans leur panneau | Design Mycelium complet, réglages, attention et parcours cohérents |
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
