# D04 — campagne commune des moteurs réels et de l'exploitation

Lot actif, une branche/PR : `hardening/d04-real-engine-qualification`, [#88](https://github.com/fredbuhr/kairo/pull/88).
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
| OpenBao | Serveur persistant, token workload et policy de lecture | Lecture KAIRO autorisée ; écriture, autre namespace, liste et administration refusées |
| Sauvegarde hors hôte | Restic chiffré, second job sur autre boot de VM, volumes neufs | Vérification de tous les packs ; SQL, vrai message JetStream, objet filer et secret OpenBao relus |
| Charge légère cible | 1/10/100/1000 clients virtuels, 3 lectures chacun, concurrence ≤20 par défaut | Zéro erreur ; p95 ≤2 s ; arrêt dès échec, 180 s maximum par palier |

Les seuils sont des critères de qualification initiaux, pas une promesse commerciale. Le modèle 0.5B
sert à prouver le câblage et les pannes ; sa qualité ne sélectionne pas le modèle quotidien de KAIRO.
La couche texte PDF ne prouve pas à elle seule les scans/OCR, tableaux complexes et grands documents.
Les scopes Mem0/épisodes Graphiti sont des projections : aucune extraction générative ni mindmap produit
n'est déclarée livrée. La recherche dépend d'amonts publics et peut être limitée sur une IP de CI.

## Préparer les modèles une fois, exécuter sans téléchargement

Sur un environnement de développement isolé avec Docker et le dépôt courant :

```bash
cp .env.example .env
mkdir -p .kairo-qualification/models .kairo-qualification/evidence
# Donner à l'UID 10001 l'accès en écriture à ces deux répertoires de préparation/mesure.
docker compose -f compose.yaml -f compose.qualification.yaml build kairo-model-prepare kairo-qualification
docker compose -f compose.yaml -f compose.qualification.yaml run --rm --no-deps kairo-model-prepare
docker compose -f compose.yaml -f compose.qualification.yaml up -d postgres neo4j
docker compose -f compose.yaml -f compose.qualification.yaml run --rm --no-deps kairo-qualification
```

Ne pas superposer les overlays `qualification` et `production`. La CI conserve les JSON de mesure,
pas les clés ou documents. Un nouveau bundle possède son propre inventaire ; ne pas écraser un bundle
déjà enregistré pour cacher une modification. Le Worker inclut les bibliothèques système requises par OpenCV/RapidOCR ; leurs versions Debian
observées dans le job `103333822364` sont figées dans `services/worker/runtime-packages.txt`.
Une version retirée du miroir fait échouer le build au lieu de choisir une version différente ; conserver
les images construites avec leurs digests pour le rollback. La qualification courante cible Linux x86_64.
Les versions des packages, empreintes et fichiers de
métadonnées de téléchargement sont enregistrés avec les résultats. Les modèles Ollama possèdent leur
digest obtenu par `/api/tags`. La préparation a révélé une dépendance système OCR manquante ; le PDF réel passe désormais
sans réseau. Mem0 créait aussi son dossier SDK sous HOME en lecture seule : son dossier technique
est maintenant dans le TMPDIR de l’enfant, avec historique SQLite en mémoire et télémétrie désactivée.
Les modèles demeurent en lecture seule et les données canoniques restent dans PostgreSQL.
Le matériel, les quotas de conteneur et les pics RSS sont enregistrés ;
un maximum RSS du processus/des enfants est cumulatif, pas une mesure de toute la machine par scénario.

## Inventaire et charge sur la cible privée

La cible privée et son stockage de sauvegarde ne sont pas fournis dans cette session. Sans les inventer,
les commandes suivantes sont prêtes pour l'environnement qui sera réellement retenu :

```bash
python scripts/qualification/target.py inventory
# Après configuration production validée et authentification réelle :
uv run --locked --project services/worker python scripts/qualification/target.py load \
  --core https://api.example.org --tokens-file /chemin/prive/access-tokens.json \
  --output .kairo-qualification/evidence/target-load.json
```

Le fichier de tokens est un tableau JSON de jetons d'accès, jamais committé. Les jetons ne sont pas
imprimés. Le rapport distingue clients virtuels, comptes réellement utilisés, requêtes et concurrence :
1000 clients utilisant un compte ne deviennent pas 1000 utilisateurs authentifiés distincts. Cette
charge ne fait que lire ; elle ne mesure pas 1000 générations IA simultanées. Les tests D02 restent
la preuve des transactions d'admission et rafales synthétiques ; ne pas dupliquer ce simulateur ici.

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

- Le réservoir `feat/kairo-test-interface-v1` (`ed12d503…`) contient une policy OpenBao et son test textuel.
  Le principe de namespace est repris ; ses écritures/effacements liés au futur cycle de compte ne sont
  pas accordés au Core actuel, qui lit seulement les valeurs/statuts. La preuve D04 utilise le serveur réel.
- Le réservoir `consolidate/g49-research-durable-stages` (`57a1a217…`) possède le même adaptateur Mem0/Graphiti
  antérieur ; il n'apporte pas de preuve de modèles hors ligne ou de restauration sur deux hôtes.
- [Docling : modèles préchargés et options](https://docling-project.github.io/docling/usage/advanced_options/).
- [FastEmbed 0.8.0](https://github.com/qdrant/fastembed/tree/v0.8.0) et
  [adaptateur Mem0 2.0.20](https://github.com/mem0ai/mem0/blob/v2.0.20/mem0/embeddings/fastembed.py).
- [Modèle de qualification Ollama](https://ollama.com/library/qwen2.5:0.5b) et
  [API d'inventaire avec digest](https://docs.ollama.com/api/tags).
