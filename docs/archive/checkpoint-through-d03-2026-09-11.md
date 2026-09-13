# Archive — clôture D03 / 2026-09-11

Historique de preuve ; la prochaine action courante reste dans PROJECT_STATE.

## Identités vérifiées

- PR [#87](https://github.com/fredbuhr/nevolium/pull/87), une livraison D03 cohérente.
- Base `ec38ce3b8c479be9ff56df36a24e7ee895754ada`.
- Head final `d931f9607b662272daf315ddc1988fede28af96c`.
- Merge ref testé `4614e59f8d781020ee10cb318d8e6d7e39889bf0`.
- Merge réel `d8b8025bb9143e49093eaaac3295affefc6fc07f` ; parents base/head vérifiés.
- Arbre commun head / merge ref testé / merge réel : `2309b3086cd7f38710e57bd6cdc174af7e5cf2d7`.
- Quatre commits internes à la PR : `daa75ac3…`, `f5969df8…`, `7944cb85…`, `d931f960…`.
  Ils sont des points de correction/reprise, pas quatre lots distincts.
- Le checkpoint de clôture ajouté après le merge ne modifie que la documentation.

## Neuf workflows du head final

- [News ownership validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677542) — succès, PR, head `d931f960…`.
- [Code quality validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677306) — succès, PR, head `d931f960…`.
- [UI workspace validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677499) — succès, PR, head `d931f960…`.
- [Document ingestion validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677409) — succès, PR, head `d931f960…`.
- [Baseline reproducibility validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677618) — succès, PR, head `d931f960…`.
- [MCP tool registry validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677661) — succès, PR, head `d931f960…`.
- [Autonomous research validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677560) — succès, PR, head `d931f960…`.
- [Multi-user isolation validation](https://github.com/fredbuhr/nevolium/actions/runs/34617676912) — succès, PR, head `d931f960…`.
- [Foundation validation](https://github.com/fredbuhr/nevolium/actions/runs/34617677437) — succès, PR, head `d931f960…`.

Les neuf workflows restent actifs sur PR et main. Le double lancement par push de branche a été
retiré. Ne pas comparer mécaniquement 9 PR actuels avec les 17 exécutions PR+push de D02 : aucune
gate fonctionnelle n'a été retirée ; des preuves production ont été ajoutées.

## Preuves ciblées

- `103323565532` : build/typecheck/packages/contrats existants, cinq scénarios de déploiement
  (JWT RSA signés, rejets de configuration et overlays, token ops distinct, inventaire modèles),
  six scénarios HTTP/TLS réels sur une IP publique attachée au loopback CI. Connexion à l'IP validée,
  Host/SNI conservés, un seul DNS malgré rebinding simulé, mauvaise identité TLS refusée, redirection
  privée/mélange IP public-privé refusés, taille sans Content-Length/compression/délai bornés.
- `103323565881` : PostgreSQL/JetStream réels D02 conservés ; rôles dédiés, migration canonique avec
  rôle sans superuser, transfert d'une table serial de développement, répétition du provisioning,
  DML Core autorisé et DDL/TRUNCATE/table Alembic/connexions inter-bases refusés ; contrôle startup
  positif avec nevolium_app et négatif avec administrateur. Régression downgrade/reapply D02 conservée.
- `103323567503` : quatre builds multi-stage figés ; Web statique non root, routes et refus POST/fichier
  serveur ; installation SQL de production dans Docker, Core avec identité restreinte et authentification
  imposée, connexion SQL Core autorisée, refus Web→PostgreSQL par nom et IP, arrêt Uvicorn complet.
- Foundation mémoire : arrêt SIGTERM réel du Worker, code 0 et absence OOM après projections.
  Les suites Keycloak, ressources/OpenBao, politique/approbation, sauvegarde/restauration et vrai
  SIGKILL Research restent dans les workflows du head final ci-dessus.

Aucun fournisseur payant n'a été appelé. Les certificats, DNS, credentials et données de charge CI
sont des fixtures ; le transport TLS, les connexions Docker/SQL et les processus sont réels.

## Défauts trouvés puis corrigés dans le même lot

1. Provisionnement initial : grant vers nevolium_app avant sa création. Toutes les identités sont
   maintenant créées avant les grants, y compris sur une base entièrement neuve.
2. Le JSON Compose peut avoir `command: null` ; le garde traite ce cas sans erreur interne.
3. Fixture HTTP/TLS sur ports 80/443 : autorisation de bind manquante sur le runner. Corrigée dans
   l'environnement CI jetable ; aucune ouverture réseau de production n'a été effectuée.
4. Core avec uniquement des réseaux internes : port loopback inutilisable par le proxy hôte.
   Pont d'entrée sans masquerading pour Core/Keycloak ; le scénario Docker prouve l'accès et conserve
   l'interdiction d'accès SQL depuis le Web.
5. Uvicorn peut terminer à 143 après réémission de SIGTERM, malgré un teardown réussi. Le test exige
   désormais fin de lifespan/processus et code 0/143, refuse SIGKILL/OOM ; aucune assertion de fin
   propre n'a été remplacée par une simple tolérance à n'importe quel code.

## Décisions et limites conservées

[ADR-028](../decisions/ADR-028-production-boundaries-and-optional-topology.md) et
[procédures de déploiement](../deployment.md) : rôles/rotation/migration, profils, trust réseau,
OpenBao, JWT et ingress, bundles de modèles et retour arrière. Politiques G50 périmées archivées.

D03 termine le périmètre H4 affecté à D01–D03, **pas H5**. Hôte privé, opérateur de confiance,
proxy TLS correctement configuré ; les moteurs et le Worker ne sont pas une sandbox pour du code
hostile. Le contrôle de valeur d'un token ne prouve pas la policy réelle OpenBao. Les modes hors
ligne et SHA-256 des bundles ne prouvent pas l'exécution correcte de Docling/Mem0/Graphiti : D04 doit
établir les vrais assets/versions, absence effective de téléchargement/fallback non voulu et compatibilité.
Les API de fournisseurs gardent leur propre politique de versions/coûts. Une estimation D02 n'est
pas un plafond garanti en dollars. Les plafonds CPU/RAM/PIDs ne sont pas une capacité matérielle mesurée.

D04 : PDF réel, mémoire/graphe, recherche, modèle local et fournisseur seulement si configuré/autorisé ;
latence/RAM/coût/files sur matériel identifié, charge explicite 1/10/100/1000, arrêt/reprise/upgrade,
rejets réseau sur cible et restauration chiffrée hors hôte. Aucun achat/déploiement utilisateur effectué.

Branche `hardening/d03-safe-deployment` retirée après merge. Prochaine branche depuis le main live,
uniquement pour D04. Gantt, cockpit Mycelium et mindmaps restent D05–D09 après la sortie H5.
