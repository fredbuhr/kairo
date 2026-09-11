# KAIRO — plan de développement exécutable

Révision : 2026-09-11. Ce document remplace les anciens blocs trop larges comme guide
d'implémentation ; leur [historique](archive/implementation-blocks-through-g51.md) est conservé.
L'état intégré et le lot actif sont dans [PROJECT_STATE](../PROJECT_STATE.md).
La [roadmap](roadmap.md) résume l'ordre ; [status](status.md) décrit les capacités présentes.

## Résultat recherché et règles communes

Un KAIRO accessible par le Web, utilisable quotidiennement, avec espace Mycelium personnalisable,
Gantt, calendrier, mindmap 2D/3D et assistant travaillant sur les mêmes données. Les comptes,
projets, tâches, documents, liens, permissions, coûts et décisions restent sous contrôle de KAIRO.
Les moteurs ne deviennent ni des produits juxtaposés ni des sources de vérité parallèles.

- Construire des tranches verticales : modèle/API nécessaire, interface, comportement réel et reprise.
- Réutiliser les primitives présentes ; aucun nouveau service/cache/framework sans manque démontré.
- Une modification du Gantt se retrouve dans Today et le graphe ; une idée devenue tâche garde sa provenance.
- Distinguer fait, hypothèse, déduction et décision ; sources et incertitudes inspectables.
- Préférer le déterminisme, puis le modèle suffisant le moins coûteux via les alias existants.
  Une indisponibilité n'autorise pas un fournisseur payant supplémentaire.
- Chaque lot traite ownership, erreurs visibles, annulation, reprise, limites et données temporaires.
- Une dépendance installée, un service présent et un mock vert ne valent pas une fonction livrée.
- Les actions financières, externes et locales intègrent leur sécurité dès leur première implémentation.
- Aucun lot ne suppose un Worker ou un conteneur permanent par utilisateur.

## Taille des lots et définition de terminé

Les IDs D01–D22 sont stables et désignent des résultats, pas des changements de deux lignes.
Privilégier une PR cohérente par lot ; deux ou trois seulement si une contrainte démontrée le justifie. Si son risque/périmètre dépasse cela,
définir une sous-livraison utilisable et sa raison dans le checkpoint avant de coder ; éviter
une chaîne de sous-gates par fichier. Estimer le lot suivant à partir du code inspecté et du
débit réellement observé ; ne pas promettre des dates pour 22 lots encore non exécutés.

Un lot est terminé quand son scénario de sortie passe, que les régressions et checks requis
du head final sont verts, que le merge est revérifié et que checkpoint/status sont à jour.
Toute limitation est nommée et rattachée à un lot futur. Une preuve exigeant un serveur, une clé,
du matériel ou une autorisation absent reste **non vérifiée** ; préparer les éléments indépendants,
sans substituer un mock à cette preuve ni déclarer abusivement le lot terminé.

## Phase A — socle avant nouvelles fonctions produit

H1–H3 et le P0 d'isolation H4 sont intégrés (#74–#83). D01–D03 couvrent les risques H4
restants de l'audit ; D04 est la sortie H5. G51 reste le dernier jalon produit.

### D01 — Worker disponible et traitements bornés

- **Prérequis :** #83 canonique ; relire Docling et l'exécution Temporal.
- **Livraison :** conversion hors boucle async ; activités/conversions simultanées limitées ;
  téléchargement, parsing et résultat bornés ; heartbeat, timeout, annulation et nettoyage sans
  processus orphelin. Conserver les contrats document/version/chunks.
- **Sortie :** parser lent sans bloquer une activité légère ; capacité maximale respectée ;
  timeout/annulation libèrent processus/fichiers ; réingestion et replay restent corrects.
- **Limite :** bornes par Worker ; équité globale et budget atomique passent à D02/D04.

### D02 — admission, budgets et volume de données

- **Prérequis :** D01.
- **Livraison :** admission globale/par propriétaire des travaux coûteux ; attente/rejet explicite
  en surcharge ; réservation/libération atomique des budgets ; retries et résultats incertains
  cohérents ; pool DB dimensionnable. Filtrer les assets en SQL, paginer collections/Today,
  reconstruire les projections par lots et borner rétention/outbox.
- **Sortie :** deux propriétaires concurrents sans double dépense ni dépassement silencieux ;
  interruption sans réservation éternelle ; backlog observable et requêtes sans chargement intégral.
  Préserver les preuves SIGKILL existantes.
- **État : terminé** par #85 (budgets IA) et #86 (tout le reste en une livraison commune).
  Admission documents/mémoire, pages SQL/UI, rebuild, outbox/rétention et observation sont intégrés.
  Head final #86 `3ed90a8bdd3eafd47d73fe21b8e2eddf3e5b1c2c` : 17/17 workflows réussis,
  PostgreSQL/JetStream réels, contrôles d'interruption et saturation synthétique jusqu'à 1000 demandes.
  [Preuves et limites](archive/checkpoint-through-d02-2026-09-11.md). Les commits/checklists sont des
  points de reprise internes au lot. D03 est le prochain lot ; D04 conserve la mesure des vrais moteurs.
  Les estimations réservées et les tokens de sortie bornés ne constituent pas un plafond fournisseur
  garanti en dollars ; enregistrer/rapprocher les coûts incertains et signaler les dépassements réels.

### D03 — déploiement sûr et topologie utile

- **Prérequis :** D02.
- **Livraison :** refus des secrets/modes de développement en production ; claims JWT, privilèges
  internes/SQL et réseau ; fermeture de la fenêtre DNS/HTTP des sorties Web. Profils pour services
  inutilisés, bornes CPU/RAM/PIDs et arrêt propre ; retrait du code/env/dépendances sans consommateurs démontrés.
- **Reproductibilité :** bases multi-stage, références nouvelles déjà digérées, conteneurs enfants
  dynamiques et modèles téléchargés ; upgrades explicites ; moins de CI dupliquée sans perdre les gates.
- **Sortie :** configurations et destinations interdites refusées ; topologie minimale utilisable ;
  services optionnels justifiés ; aucune promesse de sandbox non testée.

### D04 — moteurs réels et exploitation (H5)

- **Prérequis :** D01–D03.
- **Livraison :** scénario privé avec vrai PDF/Docling, mémoire/graphe, recherche, modèle local et
  fournisseur externe si configuré ; mesurer latence, mémoire, coût et files. Restauration chiffrée
  hors hôte, perte de moteur, redémarrage, upgrade/rollback et refus réseau.
- **Charge :** scénarios 1/10/100/1 000 utilisateurs, concurrence/débit explicites ; distinguer
  simulation sans API payante et mesure sur matériel identifié. Fixer les seuils avant mesure.
- **Sortie :** rapport daté (versions, matériel, résultats, limites), aucun P0/P1 bloquant l'usage
  privé, récupération prouvée et baseline/tag post-audit.
- **Condition externe :** ne pas acheter serveur/API ni publier sans autorisation ; préparer scripts
  et protocole même si le matériel manque. La capacité commerciale sera approfondie en D21.

## Phase B — interface quotidienne et pensée visuelle

### D05 — cockpit cohérent et langage visuel Mycelium

- **Prérequis :** D04.
- **Livraison :** design partagé issu des références utilisateur disponibles : réseau organique,
  labels sobres, centre lisible, panneaux adaptés ; navigation, recherche d'accès rapide,
  inspecteur, états vides/chargement/erreur, clavier et réduction des animations. Conserver Dockview,
  layouts par propriétaire et profils manuels réversibles, sans permission implicite.
- **Sortie :** ouvrir projet/conversation/Today/document, réorganiser et recharger sans perte ;
  téléphone et navigateur sans WebGL utilisables. Pas de graphe 3D décoratif permanent dans ce lot.
- **Références :** les images de conversations ne sont pas automatiquement dans Git. Consigner
  les références réellement disponibles ; ne pas revendiquer une fidélité visuelle sans les voir.

### D06 — listes, Kanban, Gantt et calendrier

- **Prérequis :** D05 et modèle G51.
- **Livraison :** sous-tâches, jalons, dépendances et dates canoniques ; Gantt éditable,
  progression/déplacement/redimensionnement, calendrier, listes/Kanban sur les mêmes tâches.
  Cycles/conflits détectés, chemin critique déterministe sur périmètre défini, calendrier de travail,
  fuseaux/DST et récurrences sans doublons ; replanification avec aperçu et annulation.
- **Sortie :** décaler un prédécesseur, inspecter les effets et valider ; Today/Gantt/calendrier
  concordent après rechargement et conflit d'édition ; aucune mutation implicite par l'IA.
- **Limite :** pas de solveur universel ; calendriers externes en D11.

### D07 — connaissances éditables, recherche et provenance

- **Prérequis :** D05 ; ordre nominal après D06.
- **Livraison :** notes/documents riches, versionnement et recherche universelle owner-scoped,
  sources/citations ; objets idée/décision et statuts épistémiques nécessaires. Pièces jointes,
  whiteboard liés à ces objets, export/import dans des formats documentés.
- **Sortie :** importer, annoter, créer une décision sourcée, retrouver depuis un autre espace,
  restaurer une version ; panne d'index sans perte du document ni de ses droits.
- **Limite :** coédition en D12 ; ne pas implémenter tous les objets spéculatifs du domain-model.

### D08 — mindmap 2D éditable

- **Prérequis :** D06–D07.
- **Livraison :** idées/décisions/notes/projets/tâches représentés par leurs identités ; liens typés,
  édition, groupes, sélection multiple, positions/layouts sauvegardés, filtres, recherche,
  undo/redo et liens profonds. Conversion idée→tâche conservant la référence, sans copie du métier.
- **Sortie :** construire une carte, convertir une branche en tâches visibles au Gantt ;
  rechargement/export préservent identités/liens ; isolation et chargement par périmètre testés.
- **Réemploi :** inspecter le prototype `feat/kairo-test-interface-v1` sélectivement, jamais fusionner en bloc.

### D09 — Mycelium 3D interactif et vue spatiale

- **Prérequis :** D08.
- **Livraison :** caméra/focus/zoom/sélection, filaments/groupes, labels limités, activité et liens
  vers le cockpit. Mêmes identités 2D/3D ; positions distinctes des relations métier. Qualité
  adaptative, rendu du visible, arrêt quand masqué, fallback 2D et préférences persistantes.
- **Sortie :** passer 2D↔3D, modifier un objet et vérifier sa cohérence partout ; reconnexion sans
  événements dupliqués ; mesurer fluidité et mémoire sur des jeux de tailles annoncées.
- **Limite :** bureau spatial et graphe de connaissances gardent leurs usages, avec composants/données partagés.

### D10 — assistant opérant sur les espaces

- **Prérequis :** D06–D09 et budgets/policy D02.
- **Livraison :** contexte de sélection contrôlé ; propositions de tâches/liens/replanification,
  aperçu, approbation, progression, annulation et historique. Interface Agents/Skills : portée,
  modèle, budget, outils, mémoire ; commandes/raccourcis déterministes avant le modèle.
- **Sortie :** une demande sur des sources propose un plan inspectable ; rejet sans mutation,
  approbation idempotente, conflit concurrent détecté, coût/provenance visibles.
- **Limite :** adaptation du profil proposée ou paramétrée ; aucune autorité augmentée à l'insu de l'utilisateur.

## Phase C — intégrations et pilote personnel

### D11 — comptes connectés, personnes et communication

- **Prérequis :** D10.
- **Livraison :** OAuth/secret-reference, état/révocation, sync incrémentale et reprise ; calendrier,
  contacts, fichiers et courrier. Un fournisseur réellement utilisé, puis preuve sur un second
  via les mêmes contrats. Lecture/brouillons avant envoi ; suppressions/doublons/fuseaux/rate limits.
- **Sortie :** rendez-vous/contact/documents reliés ; message préparé, autorisé et envoyé une seule
  fois malgré incident ; révocation effective et isolation.
- **Décision différée :** comptes/scopes au raccordement ; pas besoin de clés pour établir le plan.

### D12 — synchronisation, attention et collaboration

- **Prérequis :** D11.
- **Livraison :** boîte d'attention (approbations/tâches/messages/alertes), préférences et livraison
  des notifications ; reconnexion multi-appareil. Realtime authentifié, documents persistés,
  partage/rôles/conflits explicites sans casser l'isolation privée.
- **Sortie :** deux appareils reprennent un travail ; deux personnes autorisées éditent sans perte,
  tiers exclu ; coupure réseau récupérable et absence de notifications répétées indéfiniment.

### D13 — version personnelle utilisable, pilote à deux

- **Prérequis :** D05–D12.
- **Livraison :** onboarding/aide, réglages modèles locaux/API et clés propres (BYOK), coûts/quotas,
  sauvegarde/export/suppression, santé/erreurs actionnables, Web mobile/PWA, accessibilité, FR/EN
  de base et upgrades réversibles ; aucun cache offline de secrets.
- **Sortie :** document→discussion→mindmap→tâches→Gantt→rappel→reprise sur installation privée avec
  deux comptes ; bilan d'usage, bugs triés, dépenses mesurées et restauration vérifiée.
- **Jalon :** premier KAIRO complet pour l'usage quotidien central, sans attendre tous les modules spécialisés.

## Phase D — présence et autonomie étendue

### D14 — Desktop et permissions locales

- **Prérequis :** D13.
- **Livraison :** Tauri, enregistrement/révocation, raccourci global/notifications, accès choisi
  au presse-papiers, écran et dossiers ; mises à jour signées/contrôlées.
- **Sortie :** traiter un fichier autorisé, refuser hors périmètre ; appareil déconnecté sans
  arrêter les tâches serveur ; aucune autorité locale héritée d'une simple session Web.

### D15 — voix conversationnelle

- **Prérequis :** D14.
- **Livraison :** push-to-talk avant wake word optionnel, VAD/transcription, transport temps réel,
  synthèse/interruption, reprise texte, consentement et conservation audio.
- **Sortie :** latence mesurée, microphone réellement coupé, action sensible confirmée sur le
  contenu exact ; incident sans doublon d'action ni écoute cachée.

### D16 — automatisations et navigateur contrôlé

- **Prérequis :** D11–D13 ; D14 seulement pour les actions sur appareil.
- **Livraison :** horaires/événements, conditions/actions, pause/expiration, simulation/historique ;
  réutiliser Temporal/MCP/Activepieces selon besoin. Browser déterministe avant navigation IA,
  comptes/domaines autorisés, téléchargements bornés, effets externes contrôlés.
- **Sortie :** automatisation utile simulée puis autorisée, résistante à retry/restart ; révocation
  empêche les prochains effets ; une page injectée ne change pas les permissions.

### D17 — agent de développement et maintenance assistée

- **Prérequis :** D16 et sandbox éprouvée.
- **Livraison :** OpenHands/adaptateur existant, dépôt isolé, tests/diff/PR/budget, secrets minimaux
  et journal ; diagnostic et proposition d'upgrade/rollback contrôlée.
- **Sortie :** petit bug corrigé dans un dépôt de test, PR validée, annulation propre ; aucun accès
  hors dépôt ni modification silencieuse de policy/production.

## Phase E — modules spécialisés et exploitation à plusieurs

### D18 — finances et portefeuille crypto en lecture

- **Prérequis :** D13 ; ordre nominal après D17.
- **Livraison :** comptes/budget (Actual), portefeuille/historique (rotki/adaptateurs), devises,
  prix datés, import/rapprochement, dashboard d'exposition et alertes sourcées.
- **Sortie :** transactions connues rapprochées sans doublons, frais/manques/prix périmés visibles ;
  aucune clé de signature ni transaction réelle dans ce lot.

### D19 — propositions financières et simulations

- **Prérequis :** D18.
- **Livraison :** proposition non signée : destination/réseau/montant/frais/validité/simulation ;
  paper trading si utile ; signer isolé et confirmation exacte avant toute voie réelle.
  CCXT/viem/Hummingbot derrière ces règles.
- **Sortie :** simulation/rejet/expiration/replay sûr sans argent réel.
- **Gate explicite :** trading/transferts réels exigent revue et autorisation séparées ; ce plan
  ne les active pas. Applicabilité/licences revérifiées avant activation commerciale.

### D20 — maison, lieux et dashboards transversaux

- **Prérequis :** D13 ; D16 pour automatiser.
- **Livraison :** Home Assistant, états/scènes, lieux/cartes porteurs de données utiles, widgets
  reliant projets, maison et finances.
- **Sortie :** panne/états périmés visibles, action bornée sur dispositif de test ; aucune commande
  dangereuse déduite d'une suggestion IA.

### D21 — capacité multi-utilisateur mesurée

- **Prérequis :** D13 et tous les modules exposés dans l'offre retenue.
- **Livraison :** mesures 1/5/10/20/30/40/50/100/500/1 000 utilisateurs ; distinguer inscrits,
  actifs/simultanés ; fairness/quotas ; local/cloud/BYOK ; CPU/RAM/GPU/API/stockage ; rétention,
  incidents et restauration multi-tenant. Scale Workers/DB seulement sur goulot mesuré.
- **Sortie :** capacité/coût reproductibles sur matériel identifié, saturation connue et
  dégradation contrôlée ; aucune promesse de capacité déduite de la présence de Compose.

### D22 — distribution et lancement maîtrisés

- **Prérequis :** D21 pour offre hébergée ; D13 et revue dédiée pour distribution personnelle.
- **Livraison :** installation/upgrade/rollback, support/diagnostics, licences/SBOM,
  confidentialité/rétention/export/effacement, packaging personnel ou hébergé ; mesure d'usage,
  plafonds et facturation si offre payante.
- **Sortie :** utilisateur externe installé/inscrit, récupération après incident, export/suppression
  et fin de service vérifiés ; abonnement testé si activé.
- **Décisions utilisateur :** hébergement/tarifs, dépenses/support et choix stratégiques avant
  publication. OS NixOS/boîtier restent des pistes distinctes, pas des dépendances du Web.

## Couverture des besoins et dettes

| Besoin/constat | Lots responsables |
|---|---|
| Parsing, annulation, processus/temporaires, charge Worker | D01 |
| Budgets atomiques, quotas/équité, pools DB, SQL/pagination, outbox/rétention | D02, D21 |
| Secrets/JWT, jeton interne, SSRF/DNS, sandbox, topologie/composants inutiles | D03, D16–D17 |
| Locks/digests/modèles dynamiques, upgrades/SBOM, CI redondante | D03–D04, D22 |
| Vrais moteurs mémoire/graphe/parsing/IA, reprise/sauvegarde hors hôte | D04 |
| Design Mycelium, profils, clavier/mobile/accessibilité | D05, D09, D13 |
| Projects/Today, listes/Kanban, Gantt/calendrier/récurrences/jalons/chemin critique | D06 |
| Documents/notes/whiteboard, sources/recherche, idées/décisions | D07 |
| Mindmap 2D, graphe 3D vivant, cohérence entre vues | D08–D09 |
| Assistant contextuel, Agents/Skills, approbations/activité/coûts | D10, D13 |
| Calendriers/contacts/email/messages/fichiers, OAuth/révocation | D11 |
| Attention/notifications, synchronisation/collaboration | D12 |
| IA locale, OpenAI/Claude/autres fournisseurs, BYOK, routing simple | D02, D04, D13, D21 |
| Desktop/présence/voix, permissions micro/écran/presse-papiers/fichiers | D14–D15 |
| Automatisations, browser/computer use, agent dev/maintenance | D16–D17 |
| Finance/Crypto, proposition/simulation/signature isolée | D18–D19 |
| Home Assistant, lieux/cartes, tableaux de bord | D20 |
| Multi-utilisateur, coût/capacité, licences/distribution/vie des données | D21–D22 |

Cette matrice couvre les besoins connus, pas toutes les demandes futures. Toute nouvelle demande
est rattachée à un lot ou motive un lot explicite ; elle ne fait pas dériver le lot actif.
Le [protocole de reprise](development-workflow.md) définit quoi enregistrer avant changement de conversation ou incident.
