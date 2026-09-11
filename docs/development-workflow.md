# KAIRO — développement, reprise et incidents

Le code et GitHub live priment. Ce protocole applique [AGENTS](../AGENTS.md) sans multiplier les
validations administratives. Il sert après changement de discussion, perte du workspace ou échec CI.

## Sources à lire dans cet ordre

1. `AGENTS.md`, puis `PROJECT_STATE.md` depuis le live vérifié.
2. Branche/PR active, diff contre `main`, derniers commits et checks réellement exécutés.
3. Section Dxx du `docs/implementation-plan.md`, code concerné et ADR applicables.
4. `docs/status.md` pour la maturité ; audit et archives seulement comme preuves historiques.

Ne pas repartir d'un SHA copié dans une conversation. Une branche retirée n'est pas un point de reprise.
Inspecter les réservoirs nommés avant de réinventer une implémentation, sans les fusionner en bloc.

## Contrat de travail d'un lot

- Annoncer son ID, résultat attendu et limite ; une branche normale active, fraîche depuis `main`.
- D'abord reproduire le problème ou fixer le scénario utilisateur ; chercher l'implémentation existante.
- Livrer le résultat complet du lot dans une PR cohérente par défaut. Les tâches techniques,
  checklists et commits restent des points de reprise internes, pas des sous-lots à multiplier.
  Fractionner seulement pour un obstacle ou risque distinct démontré, puis en noter la raison.
- Ne pas réécrire le modèle, ajouter une queue ou contourner la policy pour rendre un test vert.
  Adapter les fixtures au vrai contrat et nommer les mocks.
- Vérifier les cas de panne/concurrence réellement introduits ; conserver les checks requis.
- À chaque point de reprise, pousser le travail reviewable ou enregistrer le blocage exact ;
  une conversation ou un fichier scratch n'est jamais l'unique copie d'un résultat important.
- Avant merge, relire le diff, vérifier SHA final, checks et base/merge ref ; ne pas extrapoler un
  succès d'une ancienne tête. Après merge, vérifier `main`, actualiser checkpoint/status et retirer la branche.
- Les opérations externes suivent l'autorisation utilisateur existante ; ce protocole n'en ajoute
  aucune et n'impose pas de confirmation pour les choix techniques ordinaires.

## Contenu obligatoire du checkpoint actif

Un enregistrement compact et factuel :

| Champ | Contenu |
|---|---|
| Lot / objectif | Dxx et scénario à rendre vrai |
| Base vérifiée | SHA live et date de vérification |
| Branche / PR | Une seule active, lien et dernier head vérifié |
| Réalisé | Changements réellement committés/intégrés |
| Validation | Commandes/jobs, SHA concerné, réussi/échoué/non exécuté |
| Incertitudes | Limites, mocks, matériel ou clés absents |
| Prochaine action | Une action exécutable et son critère de réussite |
| Reprise/rollback | Données/migration concernées, stratégie réversible, effets déjà effectués |

Le checkpoint reste court. Les historiques longs vont dans `docs/archive/` avec renvoi,
sans effacer les preuves. Ne jamais remplacer « non exécuté » par « validé ».

## Si une vérification échoue

1. Relever commit, run/job, scénario, identités et chronologie ; récupérer le log utile.
2. Classer : bug produit, test mal synchronisé, fixture/composition, environnement ou inconnu.
3. Si infrastructure seule démontrée, relancer seulement les jobs en échec ; sinon corriger
   la cause et ajouter une régression comportementale ciblée. Pas de gros sleep ni d'assertion retirée.
4. Si le head a bougé, refaire les preuves affectées. Pas de merge sur un succès historique.
5. Si une migration ou un effet externe existe, préserver les données et examiner la récupération
   avant toute suppression. Ne pas nettoyer les volumes ou forcer des refs pour masquer l'incident.

Sans Docker/dépendances locales, compiler et vérifier ce qui est possible, puis utiliser la CI
de la même tête pour les intégrations. Si elle est inaccessible, laisser la PR et l'état en attente.

## Message de reprise à utiliser dans une nouvelle discussion

> Reprends KAIRO depuis https://github.com/fredbuhr/kairo. Vérifie le main live, lis AGENTS.md et
> PROJECT_STATE.md, inspecte la branche/PR active et ses checks. Continue uniquement le lot Dxx
> réellement actif du plan, à partir de la prochaine action enregistrée. Ne fais confiance ni au
> SHA de cette discussion ni aux anciens next action des archives. Préserve le scope, les preuves
> et les décisions existantes ; signale tout écart avant de changer de direction.

Le message volontairement ne fige pas de SHA ou de numéro de PR qui deviendrait périmé.
