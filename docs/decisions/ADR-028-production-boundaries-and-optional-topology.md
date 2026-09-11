# ADR-028 — Frontières de production et topologie optionnelle

Date : 2026-09-11. Livraison D03 / PR #87 ; validation finale dans PROJECT_STATE.

## Problème constaté

Le Core acceptait l'authentification désactivée et des secrets de développement, ne vérifiait
pas l'audience JWT et tolérait l'absence d'`azp`. Les moteurs partageaient le compte SQL initial.
Le lecteur News/Web MCP résolvait une destination pour la contrôler, puis HTTPX la résolvait
à nouveau lors de la connexion. L'ensemble Compose lançait des services sans consommateur,
le Web utilisait Vite dev, et le contrôle d'images ignorait les stages suivants et les COPY externes.

Les réservoirs `feat/kairo-test-interface-v1` (`ed12d503…`) et
`consolidate/g49-research-durable-stages` (`57a1a217…`) ont été comparés au main de départ
`ec38ce3…`. Leurs lecteurs Web conservaient la même fenêtre DNS/HTTP et leurs validations JWT
la même absence d'audience/azp obligatoire. Aucun code de ces branches n'a été fusionné en bloc.

## Décisions

- Production refuse le mode inconnu, le contournement d'identité, les secrets faibles/placeholders
  et les identifiants SQL non dédiés. JWT RS256 : issuer, audience `kairo-core`, authorized party
  du client Web et type d'access token `Bearer` ; rôles structurés, sujet non vide, dates requises.
- Le Core possède `kairo_app` (DML), la migration possède `kairo_migrator` (DDL). Mem0, Keycloak,
  Temporal, LiteLLM, Langfuse et Activepieces possèdent des comptes/bases distincts sans privilèges
  administratifs ni connexions croisées. Le démarrage Core vérifie aussi les droits effectifs SQL.
- Le Worker reste un composant de confiance chargé d'exécuter les Tasks déjà liées et autorisées.
  Son token interne n'est pas une identité utilisateur ni une sandbox par Task. Un autre token,
  conservé côté opérateur/Core, autorise les reconstructions mémoire globales en production.
- Des réseaux Compose internes limitent les consommateurs de chaque moteur. Le Web statique
  ne rejoint pas les réseaux de données. Seuls les composants ayant un besoin Web disposent
  d'une sortie réseau ; les ports d'infrastructure ne sont plus publiés en production.
- Le lecteur public connecte l'IP contrôlée, tout en conservant Host, SNI et vérification TLS.
  Chaque redirection est contrôlée ; nouveau client sans proxy d'environnement, cookies ou secrets.
  Ports 80/443, quatre destinations au maximum, 30 s, 2,5 Mo pendant lecture ; compression refusée.
- Services sans usage courant : profils explicites. Les prototypes sans frontière de production
  sont refusés par le précontrôle ; ils ne sont pas promus en fonctionnalités livrées.
- Images applicatives multi-stage et non root, ressources bornées et arrêt Worker explicite.
  Pas de nouveau moteur ni de nouveau orchestrateur. Direct browser-use/Playwright Worker retirés
  faute d'appel ; les cibles produit restent documentées pour le lot navigateur.
- Modèles locaux : inventaire de sources et SHA-256, bundle monté en lecture seule, mode hors ligne
  explicite ; mise à jour volontaire dans un nouveau bundle. La compatibilité réelle est D04.
- Les neuf workflows restent sur PR et main ; les push de branches ne les doublent plus.

## Conséquences et limites

Le montage de production suppose un opérateur de confiance, un hôte Docker privé et un proxy TLS
configuré. Les réseaux internes HTTP ne remplacent pas du mTLS sur plusieurs hôtes. Le Worker,
les moteurs et le socket Docker opérateur ne sont pas des sandboxes pour du code hostile.
Les fournisseurs externes gardent leur propre politique de versionnement/coût ; une référence
configurée n'est ni une garantie de prix ni une preuve d'exécution réelle.

D03 établit des refus vérifiables et une procédure exploitable. D04 conserve les preuves sur
PDF/Docling, Mem0/Graphiti, modèles locaux, matériel, charge et restauration chiffrée hors hôte.
Aucune donnée utilisateur, ressource payante ou installation de production n'a été touchée ici.
