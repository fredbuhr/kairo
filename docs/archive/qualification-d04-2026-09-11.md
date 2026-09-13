# D04 — rapport de qualification, 11 septembre 2026

**D04/H5 reste ouvert.** Une seule livraison : [PR #88](https://github.com/fredbuhr/nevolium/pull/88),
branche `hardening/d04-real-engine-qualification`, draft non fusionnée. Le code canonique reste D03.
Ce rapport conserve les preuves de la campagne CI et les conditions du scénario privé encore absent.

## Identité et méthode

- Base main vérifiée : `0e2d22d8b49d1ddda6f2c0432de8dfe991b3ee0a` ; D03 intégré par #87.
- Head de code : `10cb57c27e8018ea55b738dbf02495a3eff44aff`, arbre `bfd2bdd857da639d2792428d7659e246d11abaf6`.
- Les commits suivants du rapport/checkpoint sont documentaires ; contrôler leur diff depuis ce head.
- [Campagne commune](https://github.com/fredbuhr/nevolium/actions/runs/34623761553) : cinq jobs,
  dont quatre emploient de vrais moteurs ; le cinquième vérifie seulement le générateur de charge avec un serveur HTTP de test.
- Les seuils sont fixés dans le [protocole](../qualification-d04.md) avant la mesure.
- Données originales jetables ; aucun document privé ni fournisseur payant configuré. Aucun déploiement utilisateur exécuté.
- [Résultats JSON conservés](d04-2026-09-11/evidence.json) : versions, matériel, quotas, durées,
  SHA-256 de chaque fichier des modèles, révisions amont et empreintes des deux hôtes de restauration.
  Ces résultats sont conservés dans Git ; la disparition des artefacts temporaires CI ne supprime pas le checkpoint.

## Résultats mesurés

| Groupe / cas réel | Durée mesurée (s) | Seuil (s) | Résultat |
|---|---:|---:|---|
| Docling / mémoire — `offline-readonly-boundary` | 0.916 | 15 | Réussi |
| Docling / mémoire — `pdf-docling-owned-child` | 23.051 | 210 | Réussi |
| Docling / mémoire — `real-memory-owned-child-and-replay` | 19.638 | 240 | Réussi |
| Docling / mémoire — `real-vector-search-and-graph-readback` | 5.868 | 120 | Réussi |
| Docling / mémoire — `missing-model-fails-closed` | 3.895 | 45 | Réussi |
| Docling / mémoire — `model-bundle-unchanged` | 1.014 | 30 | Réussi |
| Modèle / recherche — `gateway-local-inference-and-accounting` | 1.963 | 115 | Réussi |
| Modèle / recherche — `engine-loss-known-replay-and-unknown-outcome` | 16.254 | 90 | Réussi |
| Modèle / recherche — `local-engine-restart` | 1.844 | 115 | Réussi |
| Modèle / recherche — `searxng-live-worker-search` | 1.382 | 65 | Réussi |
| Sauvegarde source — `seed-real-durable-state-and-openbao-policy` | 2.098 | 90 | Réussi |
| Sauvegarde source — `quiesced-encrypted-restic-backup` | 32.137 | 300 | Réussi |
| Restauration destination — `off-host-restic-full-check` | 6.127 | 300 | Réussi |
| Restauration destination — `off-host-volume-restore` | 5.826 | 300 | Réussi |
| Restauration destination — `off-host-real-service-readback` | 4.043 | 90 | Réussi |

| Hôte du groupe | CPU annoncé / vCPU visibles | RAM hôte (Kio) | Limite du conteneur de preuve |
|---|---|---:|---|
| Docling / mémoire | AMD EPYC 7763 64-Core Processor / 4 | 16373452 | 2 CPU, 4 Gio, 256 PIDs |
| Modèle / recherche | AMD EPYC 9V74 80-Core Processor / 4 | 16373452 | Runner ; plafonds des services dans Compose |
| Sauvegarde source | Intel(R) Xeon(R) 6973P-C / 4 | 16372436 | Runner ; plafonds des services dans Compose |
| Restauration destination | INTEL(R) XEON(R) PLATINUM 8573C / 4 | 16372436 | Runner ; plafonds des services dans Compose |

Versions du moteur : docling 2.126.0, docling-core 2.96.0, fastembed 0.8.0, graphiti-core 0.29.3, mem0ai 2.0.20, onnxruntime 1.30.0.
Le PDF réel prend 23,051 s ; pic RSS enfant mesuré 1691512 Kio (environ 1,61 Gio).
Le bundle contient 97 fichiers inventoriés ; empreinte du manifeste : `f283ed965269eedaa2500926f33cc642e42731e396e94a8c87e53a732cfc1617`.
[Manifeste original conservé](d04-2026-09-11/model-manifest.json), SHA-256 vérifié après archivage.
Ollama 0.33.3, modèle `qwen2.5:0.5b` ; digest `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67`.
Ces nombres décrivent ce passage CI CPU ; ils ne préjugent pas des mesures sur la cible privée.

Les limites CPU/RAM/PIDs ne sont pas des recommandations matérielles. Le pic RSS est celui du
processus ou le maximum cumulatif de ses enfants, pas la consommation simultanée de tous les moteurs.
Le modèle local de qualification ne mesure ni la qualité d'un modèle quotidien plus grand ni son besoin de GPU.

## Régressions et corrections coordonnées

| Observation réelle | Correction dans la même PR | Portée |
|---|---|---|
| Import OCR/OpenCV impossible, `libxcb.so.1` absent | Bibliothèques natives dans l'image Worker ; 42 versions Debian observées puis figées | Image complète Linux x86_64 ; conserver les images construites pour rollback si les miroirs retirent une version |
| Mem0 tente de créer son dossier SDK sous HOME en lecture seule | MEM0_DIR sous TMPDIR avant l'import, historique SQLite en mémoire, télémétrie désactivée | Stockage technique dérivé ; données canoniques/projections durables inchangées |
| OpenBao reçoit deux fois sa configuration et refuse l'option mlock supprimée | Laisser l'entrypoint charger la configuration une fois ; retirer l'option et la capacité IPC_LOCK devenues inutiles | Version OpenBao épinglée ; politique mémoire/swap de l'hôte à contrôler en exploitation |
| Une racine HTTP SeaweedFS répond avant la disponibilité des volumes restaurés | Relecture des octets avant backup puis attente bornée après restauration ; conserver statut, durée et hash | L'essai `1698dc9…` a observé 500 puis 200 au deuxième essai ; aucune perte de métadonnées démontrée, aucune modification spéculative du stockage |
| Droits de fichiers créés par Docker/tar empêchent d'écrire les rapports de destination | Créer le staging comme opérateur et extraire sans reprendre les propriétaires de l'hôte source | Fixture de transfert CI ; ne pas élargir les permissions des données privées |

Les modèles sont préparés explicitement avec réseau, puis les adaptateurs réels tournent sur un
réseau Docker interne, avec bundle en lecture seule. Deux connexions IP publiques sont refusées ;
un cache absent échoue ; l'inventaire des fichiers est identique après exécution. Mem0 effectue une
vraie recherche vectorielle ; Graphiti conserve un épisode et son scope. Aucune extraction générative
ou mindmap produit n'est déduite de ces preuves d'adaptateurs.

Le modèle Qwen2.5 0.5B passe par Ollama, LiteLLM et les transactions d'admission/comptabilisation Nevolium.
Un résultat connu reste relisible moteur arrêté, un dispatch incertain ne repart pas aveuglément,
puis une nouvelle inférence réussit après redémarrage. `cost_reported=false` conserve l'incertitude :
le montant numérique nul retourné n'est pas une preuve de coût fournisseur connu.

La récupération transfère le seul dépôt Restic chiffré vers une autre VM, vérifie tous les packs et
restaure des volumes neufs. La relecture vise un enregistrement SQL, le premier message JetStream,
les octets originaux de l'objet filer et un secret OpenBao après déscellement. La policy autorise la
lecture Nevolium et refuse écriture, autre namespace, liste et administration. Les clés/phrase de passe
publiques du test restent des fixtures ; en exploitation, les clés de récupération sont séparées du backup.
Deux boots distincts ne prouvent pas une séparation géographique ou une procédure de clés utilisateur.

## Validation du code

**9/9 workflows réussis sur le même head de code** ; les cinq jobs de D04 sont réussis.

| Workflow | Exécution | Résultat |
|---|---|---|
| Code quality validation | [34623761514](https://github.com/fredbuhr/nevolium/actions/runs/34623761514) | Réussi |
| Baseline reproducibility validation | [34623761436](https://github.com/fredbuhr/nevolium/actions/runs/34623761436) | Réussi |
| Document ingestion validation | [34623761506](https://github.com/fredbuhr/nevolium/actions/runs/34623761506) | Réussi |
| MCP tool registry validation | [34623761476](https://github.com/fredbuhr/nevolium/actions/runs/34623761476) | Réussi |
| UI workspace validation | [34623761441](https://github.com/fredbuhr/nevolium/actions/runs/34623761441) | Réussi |
| Multi-user isolation validation | [34623761365](https://github.com/fredbuhr/nevolium/actions/runs/34623761365) | Réussi |
| Foundation validation | [34623761351](https://github.com/fredbuhr/nevolium/actions/runs/34623761351) | Réussi |
| D04 real engine qualification | [34623761553](https://github.com/fredbuhr/nevolium/actions/runs/34623761553) | Réussi |
| Autonomous research validation | [34623761364](https://github.com/fredbuhr/nevolium/actions/runs/34623761364) | Réussi |

Jobs D04 : [real-local-services / 103343843282](https://github.com/fredbuhr/nevolium/actions/runs/34623761553/job/103343843282), [qualification-runner-contract / 103343843568](https://github.com/fredbuhr/nevolium/actions/runs/34623761553/job/103343843568), [real-document-memory / 103343843598](https://github.com/fredbuhr/nevolium/actions/runs/34623761553/job/103343843598), [recovery-source / 103343843613](https://github.com/fredbuhr/nevolium/actions/runs/34623761553/job/103343843613), [recovery-target / 103344292044](https://github.com/fredbuhr/nevolium/actions/runs/34623761553/job/103344292044).
Les gates existantes restent présentes. Le workflow News possède son filtre de chemins propre ; il ne constitue pas un dixième passage séparé sur ce head.

La compilation locale des nouveaux scripts et `git diff --check` passent. Le workspace ne possède ni
Docker, ni GPU ni bundle de modèles : aucune exécution réelle locale n'est prétendue. Les moteurs
ont été exécutés par les jobs CI identifiés ci-dessus. Le contrat HTTP exerce 3333 lectures réparties
sur 1/10/100/1000 clients virtuels, avec un seul sujet de test ; un retour 429 arrête avant le palier
suivant. Ce résultat qualifie l'outil de mesure, pas la capacité de Nevolium ni 1000 comptes distincts.

## Ce qui reste dans D04

1. Identifier la machine réellement retenue, son OS/CPU/RAM/GPU/disque et la destination indépendante de backup.
   Lancer `python scripts/qualification/target.py inventory` sur cette cible ; conserver le JSON sans secrets.
2. Configurer les profils utiles, modèles choisis et authentification de production selon deployment.md.
   Exécuter le parcours canonique complet PDF, mémoire, recherche, modèle et résultat vérifié par l'utilisateur.
3. Mesurer lectures, latences, files et usage mixte sur cette cible, avec les nombres de comptes et la concurrence
   effectivement utilisés. Le runner prêt refuse l'accès anonyme, limite la pression et s'arrête au premier palier défaillant.
4. Vérifier proxy TLS, refus des routes internes, droits SQL/réseau, récupération indépendante des clés,
   restauration applicative et upgrade/rollback compatible, sans effacer les états/dépenses inconnus.
5. Reporter ces résultats et limites, lever les éventuels P0/P1, puis valider/merger **cette même PR** et le jalon H5.
   D05 et l'interface quotidienne attendent cette sortie ; ne pas créer un sous-lot pour déplacer le travail restant.

Un fournisseur externe reste facultatif. Aucun achat ou appel payant n'est nécessaire pour reprendre
le lot. Les scans complexes/OCR, grands documents, GPU, modèle quotidien et charge mixte privée ne
sont pas qualifiés par le petit PDF à couche texte et le petit modèle de CI.

## Continuité et récupération sélective

Le point de reprise fait autorité dans [PROJECT_STATE](../../PROJECT_STATE.md), après vérification
des refs live. Le [plan D01–D22](../implementation-plan.md) reste la séquence de livraison, et
status/component-matrix distinguent explicitement les preuves de branche des acquis de main.

Réservoir d'interface historique inspecté à `ed12d503aa500a6e7700e9ac82d823e0e815f33d`
et `consolidate/g49-research-durable-stages` à `57a1a217f466c56446d84d863f4b9b09855e4c4e`.
Le principe de namespace de la policy prototype est repris après revue ; ses droits futurs
d'écriture/effacement ne sont pas nécessaires au Core actuel. Aucun équivalent de cette campagne
réelle hors ligne/hors hôte trouvé ; aucune branche prototype fusionnée en bloc.

Les références primaires Docling, FastEmbed, Mem0, Ollama et les règles d'exploitation sont liées
dans le protocole. Pour le diagnostic SeaweedFS : [configuration du filer dans l'image 4.46](https://github.com/seaweedfs/seaweedfs/blob/4.46/docker/filer.toml)
et [initialisation serveur](https://github.com/seaweedfs/seaweedfs/blob/4.46/weed/command/server.go).
