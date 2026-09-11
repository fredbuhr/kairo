# D04 — contrôle préalable de l'accès public, 11 septembre 2026

Complément dans la même [PR #88](https://github.com/fredbuhr/kairo/pull/88), sans nouveau lot.
D04/H5 reste ouvert ; aucun serveur privé n'a été fourni ni déployé.

## Problème et changement

Le générateur de charge comptait une réponse HTTP 200 comme une lecture réussie sans vérifier sa
forme. Un proxy renvoyant une page HTML ou le mauvais backend pouvait donc produire un résultat
trompeur. Le contrôle préalable n'écartait que l'accès anonyme.

`target.py preflight` vérifie désormais dix requêtes GET au maximum : accès anonyme et faux jeton,
trois lectures authentifiées avec formes JSON attendues, puis cinq chemins privés refusés par
l'ingress. Il réutilise le premier jeton fourni, n'écrit rien dans KAIRO et n'appelle aucun modèle.
`target.py load` exécute ce contrôle avant les paliers et valide aussi chacune des lectures mesurées.

TLS garde certificat/nom d'hôte vérifiés, CA privée explicite possible ; aucune option de désactivation.
Un rapport distingue vérification activée et handshake vérifié après succès du contrôle. Les
redirections et proxys ambiants ne sont pas utilisés. Les réponses sont limitées à 2 Mio et dix
secondes totales, avec timeout socket de cinq secondes et refus d'encodage compressé. Today conserve
une limite explicite de 20 par catégorie pendant la charge.

Le fichier de résultat ne contient ni jeton, ni corps de réponse. Un refus préalable préserve le
diagnostic (cas, statut, classe d'erreur/code fixe et durée) et empêche la charge. Les commandes et
conditions opérateur sont dans [qualification-d04](../qualification-d04.md).

## Validation

- Code `a5a61db38191a9f8f37551fba7fe44df06c8a3be`, arbre `c3ea2b7928bd11b45a607a22a9a6f9f0371a1179`.
- [Campagne CI](https://github.com/fredbuhr/kairo/actions/runs/34627509237), job
  [qualification-runner-contract / 103356071745](https://github.com/fredbuhr/kairo/actions/runs/34627509237/job/103356071745) réussi : **6 tests en 24,056 s**.
- Douze scénarios réseau répartis dans ces tests : deux parcours de charge HTTP ; accès TLS correct ;
  six erreurs d'accès/routage/taille ; CA non reconnue ; nom d'hôte incorrect ; réponse envoyée lentement.
- Les tests utilisent de vrais sockets HTTP/TLS en boucle locale, un certificat jetable et les
  dépendances verrouillées du Worker. Le serveur de test répond avec des fixtures : il ne s'agit pas
  d'une instance KAIRO ni d'un proxy de production. Aucun secret de production utilisé.
- La CA non reconnue et le mauvais nom d'hôte échouent avant toute requête HTTP. La redirection ne
  reçoit aucun jeton sur la destination ; une réponse lente expire au délai total malgré l'arrivée de données.
- Les 3333 lectures de charge restent distinctes des dix contrôles préalables et n'inventent pas
  1000 comptes à partir d'un seul sujet. La pression 429 arrête avant le palier suivant.
- Compilation, contrôles locaux des formes JSON/origines/contexte TLS et diff passent. HTTPX n'est
  pas installé dans le workspace ; les régressions réseau ont été exécutées en CI, pas revendiquées localement.
- **9/9 workflows et 5/5 jobs D04 réussis sur ce même head**, y compris moteurs réels et restauration.
  [IDs, résultats et identité du code conservés](d04-2026-09-11/access-validation.json).

## Portée et reprise

Les chemins privés ne sont sondés qu'en GET, avec refus 403/404 attendu ; un 405 révèle que la route
reste atteignable. Cette preuve ne certifie pas le filtrage de toutes les méthodes HTTP et ne remplace
pas la revue des règles d'ingress. Trois formes de réponse reconnues ne sont pas une preuve
cryptographique de l'identité de l'application ou de l'isolation de tous les comptes.

La prochaine action nécessite la cible serveur choisie : inventaire, configuration de production,
contrôle d'accès avec authentification réelle, puis scénario applicatif, charge mixte, upgrade/rollback
et récupération privée. Aucun nouveau produit D05 n'est commencé et la PR demeure draft.
Les [preuves des moteurs et de restauration](qualification-d04-2026-09-11.md) restent conservées avec
leurs versions, matériel et limites ; ce complément ne transforme pas la CI en qualification privée.
