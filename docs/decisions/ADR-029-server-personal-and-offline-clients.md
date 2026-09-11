# ADR-029 — Serveur prioritaire, installation personnelle et clients hors ligne

Date : 2026-09-11. Orientation retenue à la demande de l'utilisateur pendant D04.
Statut : décision de conception ; les capacités futures ci-dessous ne sont pas livrées par cette ADR.
Le lot actif reste D04 / PR #88. Aucun nouveau lot, aucune fusion de code ni activation de production.

## Objectif et état observé

Nevolium doit être accessible depuis PC, téléphone et tablette, avec hébergement serveur prioritaire.
Une installation complète sur portable/bureau doit aussi permettre l'usage personnel sans location
de serveur. Une coupure Internet ne doit pas empêcher tout travail.

Le dépôt possède déjà Web React, Three/React Three Fiber, React Flow, Gantt, un squelette Tauri et
des frontières Core/Worker/stockages canoniques. Le code inspecté ne livre pas de service worker,
de cache IndexedDB propriétaire ni de synchronisation de mutations hors ligne. Yjs/Hocuspocus est
une cible de collaboration, pas une preuve d'édition hors ligne ni une autorité métier alternative.

## Une application, deux lieux d'hébergement

| Mode | Autorité des données | Clients | Limite structurante |
|---|---|---|---|
| Serveur, priorité produit | Une instance Nevolium sur serveur Linux | Web/PWA sur PC, smartphone et tablette ; Desktop ultérieur | Les tâches serveur continuent si le client se déconnecte ; les services externes exigent leur propre connectivité |
| Personnel autonome | Le même Core et ses stockages, sur le PC allumé | Interface locale ; clients LAN si configurés | Veille/arrêt du PC suspend le service ; accès distant et sauvegarde indépendante restent à configurer |

Chaque espace de travail possède une seule instance faisant autorité. Les caches des clients sont
des copies partielles ; pas de réplication bidirectionnelle de deux serveurs Nevolium autonomes dans le
premier périmètre. Déplacer une installation personnelle vers un serveur passe par une migration
contrôlée avec arrêt des écritures, transfert/restauration et changement explicite de destination.

Conserver le même modèle métier, les identités, API, politiques et formats d'export dans les deux
modes. Utiliser les profils utiles et des limites de concurrence différentes ; ne pas lancer tous
les moteurs du registre. L'installation personnelle n'autorise ni SQLite comme seconde vérité,
ni la suppression silencieuse de l'identité, des permissions ou de l'audit.

## Interfaces et graphisme

Le Web adaptatif/PWA est le client principal commun. Tauri reste une enveloppe Desktop pour les
permissions et intégrations locales, pas une seconde application métier et pas, à lui seul, un
installateur du serveur complet. Pas d'applications iOS/Android natives distinctes avant un besoin
matériel ou une limite de PWA démontrée. Smartphone/tablette n'hébergent pas le backend complet.

| Appareil | Expérience cible |
|---|---|
| Bureau / portable | Cockpit à panneaux, clavier/souris, Gantt complet, cartes 2D et Mycelium 3D |
| Tablette | Un ou deux espaces selon largeur/orientation, Gantt et mindmap tactiles ; stylet optionnel |
| Smartphone | Today, capture, notes, tâches, recherche, assistant et approbations ; Gantt en agenda/liste et carte centrée sur une branche |

La 3D est calculée sur le client, pas diffusée comme une vidéo depuis un GPU serveur. Les données
restent les mêmes entre vues. Prévoir niveaux de qualité, détail progressif, sous-graphes chargés à
la demande, plafonds de labels/effets/résolution, suspension quand masqué et mode économique.
2D/listes restent fonctionnelles sans WebGL ; perte du contexte graphique sans perte du travail.
La 3D mobile est une exploration optionnelle si les mesures la permettent, pas une condition d'usage.
Les actions tactiles possèdent une alternative au survol, au clic droit et au glisser précis.
Les préférences visuelles sont adaptées par appareil ; synchroniser le contenu ne doit pas imposer
le layout du bureau à un téléphone. Ne pas exiger WebGPU pour les fonctions de base.

## Contrat hors ligne borné

« Sans Internet » et « sans accès à l'instance Nevolium » sont deux situations différentes. Un PC
hébergeant Nevolium peut conserver Core, recherche locale et IA locale préchargée sans Internet ; un
téléphone sur son LAN peut aussi joindre ce PC. Un client isolé de son serveur ne dispose que des
données et fonctions préparées sur cet appareil. Aucun cache ne rend un service externe disponible.

| Fonction | Client isolé du serveur : premier périmètre D12–D13 |
|---|---|
| Interface | Ouverture après installation/préparation en ligne ; état de connexion et dernière synchronisation visibles |
| Notes et tâches | Capture/brouillons et édition simple sur données préparées ; état « enregistré sur cet appareil », validation serveur à la reprise |
| Documents | Lecture des pièces explicitement téléchargées ; recherche limitée au contenu local |
| Gantt et mindmaps 2D/3D | Consultation/navigation des périmètres préparés ; création de notes/idées en brouillon ; replanification et éditions structurelles en ligne dans ce premier périmètre |
| Assistant | Historique préparé et brouillon de demande ; aucune réponse IA serveur/cloud promise sans liaison |
| Messages, achats, finance, automatisations, permissions | Pas d'exécution ni d'approbation définitive hors ligne ; nouvelle validation avec état frais avant effet externe |

Pour une installation personnelle joignable, les fonctions du backend local restent utilisables
selon les moteurs disponibles. Une IA locale est optionnelle et doit être téléchargée/testée avant
la coupure ; recherches Web, cours en direct et API distantes restent indisponibles sans Internet.

Implémentation cible : service worker pour les fichiers de l'application, IndexedDB pour les données
choisies et les opérations locales. Partitionner par instance/compte/espace ; jamais de cache générique
des réponses authentifiées ou des secrets/API keys. L'accès hors ligne est opt-in sur appareil de
confiance, après authentification en ligne, avec durée/périmètre et verrouillage définis en D12.
Traiter expiration de session, changement de compte, révocation et purge ; une révocation distante
ne peut pas effacer instantanément une copie sur un appareil isolé. Ne pas promettre cet effacement.

Chaque mutation admissible possède un identifiant stable, une version de base, un statut et un reçu.
À la reprise : réauthentifier, revérifier les droits et la politique, dédupliquer, appliquer ou exposer
le conflit, puis acquitter. Conserver les deux versions d'une note conflictuelle ; ne pas appliquer
un « dernier arrivé gagne » silencieux aux dépendances, suppressions, dates ou rôles. Une capture
hors ligne ne lance pas automatiquement une Task/IA et ne vaut pas autorisation d'un effet externe.
Yjs peut servir les documents collaboratifs en D12 ; il ne remplace pas les commandes métier Core.

Reprendre la synchronisation à l'ouverture et au retour au premier plan ; la synchronisation en
arrière-plan n'est qu'une optimisation selon le navigateur. Gérer quotas/échec d'écriture/éviction,
demande de stockage persistant, indicateur d'opérations non synchronisées et export de secours.
Un cache navigateur n'est pas une sauvegarde garantie ; prévenir avant une purge de travail local
non acquitté et proposer un export quand la politique le permet. Pas de garantie de conservation
après effacement manuel des données du navigateur.

## Matériel et exploitation

Distinguer le coût du rendu 3D, celui du backend et celui des modèles IA. Un PC client n'a pas à
faire tourner l'IA du serveur. Pour le PC hébergeant tout Nevolium, CPU/RAM/SSD et éventuellement GPU
dépendent des profils, documents, modèles, contexte et concurrence. Le nombre d'utilisateurs inscrits
ne mesure pas la charge simultanée des moteurs.

Repères de qualification proposés, **pas des minima garantis ni une recommandation d'achat** :
client PC 8 Go avec GPU intégré à tester ; backend personnel sans gros modèle sur 16 et 32 Go,
en privilégiant 32 Go comme première cible de confort à mesurer. Ne pas promettre le runtime
complet sur 8 Go. Choisir RAM/VRAM du modèle local après mesure ; une grande IA n'est pas un prérequis
au Gantt, aux notes ou à Mycelium. Les mesures CPU D04 portent des scénarios isolés, pas toute la
plateforme simultanément et ne qualifient pas ces configurations complètes.

Référence de déploiement initiale : serveur Linux x86_64. D13 pilote une installation personnelle
administrée ; D22 livre le packaging et une matrice réellement testée Windows/macOS/Linux/architectures.
Les environnements VM/conteneur de ces OS consomment aussi des ressources ; compatibilité ARM/GPU
et licences des outils de distribution à vérifier avant d'annoncer le support. Un PC peut héberger
sans abonnement serveur, mais garde ses coûts d'énergie, stockage, sauvegarde et éventuelles API.

Pour l'offre hébergée : conserver Core/Worker séparés, admissions/quotas par propriétaire et globaux,
files bornées, séparation des pools d'inférence et traitements documentaires selon les mesures.
Isoler données/caches/objets par propriétaire/espace. D21 valide les frontières multi-tenant de
l'offre et le débit, pas seulement la présence d'un champ utilisateur. Réutiliser la topologie
actuelle ; pas de Kubernetes ni de base par utilisateur imposés avant un goulot ou besoin d'isolation
mesuré. Les clients ne téléchargent pas tout le graphe ni toutes les pièces jointes d'un compte.

## Intégration dans les lots existants et acceptation

- D04 : cible serveur prioritaire, mesurer les ressources ; H5 ne devient pas une certification de tous les OS/appareils.
- D05 : shell Web adaptatif/installable, navigation tactile et états de connexion ; aucun faux mode offline de données.
- D06–D09 : vues sur identités communes, chargement borné, parcours tactiles et qualité graphique mesurée.
- D12 : cache choisi, notes/tâches hors ligne bornées, reçus/conflits, reprise et collaboration authentifiée.
- D13 : pilote PC + téléphone + tablette et backend personnel administré ; coupure/reprise vérifiée.
- D14 : permissions et enveloppe Desktop réutilisant le Web ; pas de fork de données.
- D21–D22 : capacité hébergée, packaging personnel et compatibilité/distribution prouvés.

Critères transversaux : mode avion après préparation puis réouverture ; création/édition, reconnexion
sans doublon ; deux appareils modifiant le même objet ; suppression concurrente et droits révoqués ;
quota saturé et perte du cache ; interruption pendant l'acquittement ; mise à jour du schéma local ;
rotation tablette, petit écran et navigateur sans WebGL ; chauffe/batterie et gros graphe sur matériel
identifié. Si le périmètre préparé manque, le dire plutôt que montrer une donnée inventée ou prétendre
qu'une écriture locale est déjà synchronisée.

## Sources primaires consultées

- [MDN — Offline and background operation](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation)
- [MDN — Storage quotas and eviction criteria](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- [MDN — WebGL best practices](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices)
- [Ollama — FAQ, concurrence et mémoire](https://docs.ollama.com/faq)

Ces sources décrivent les capacités/contraintes des briques ; elles ne prouvent pas leur intégration Nevolium.
