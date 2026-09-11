# KAIRO — ordre des livraisons

Révision : 2026-09-11. Le [plan détaillé](implementation-plan.md) porte périmètres, dépendances
et critères de sortie. [PROJECT_STATE](../PROJECT_STATE.md) seul indique le lot actif et les preuves.
La table donne le séquencement ; elle ne déclare pas tous les lots livrés. D01 est intégré par #84,
D02 est la prochaine étape. Le détail opérationnel reste dans le checkpoint.

| Phase | Lots, dans l'ordre nominal | Résultat |
|---|---|---|
| A — fiabilité | D01 Worker borné → D02 admission/budgets/données → D03 déploiement/topologie → D04 preuves réelles H5 | Socle utilisable et récupérable, limites connues |
| B — produit visuel | D05 cockpit → D06 Gantt/calendrier → D07 connaissances → D08 mindmap 2D → D09 Mycelium 3D → D10 assistant contextuel | Un espace cohérent pour penser, planifier et agir |
| C — vie quotidienne | D11 connecteurs → D12 attention/synchronisation → D13 pilote personnel à deux | Première version utilisable chaque jour |
| D — présence/autonomie | D14 Desktop → D15 voix → D16 automatisations/browser → D17 agent dev | Assistant disponible sur les appareils, actions contrôlées |
| E — extensions/exploitation | D18 finance/crypto lecture → D19 simulations → D20 maison/cartes → D21 capacité/coûts → D22 distribution | Modules utiles puis lancement maîtrisé |

## Jalons

1. **Socle post-audit :** D04 terminé, tag H5 et rapport de vrais moteurs/récupération.
2. **Expérience graphique intégrée :** D10 terminé, données partagées entre Today, Gantt et mindmaps 2D/3D.
3. **Pilote personnel :** D13 terminé, deux comptes et parcours quotidien sur installation privée.
4. **Assistant étendu :** D17 terminé, appareils/voix/automatisations sous permissions.
5. **Offre distribuable :** D22 terminé pour un périmètre et une capacité explicitement validés.

Les dépendances précises du plan permettent de déplacer un module optionnel si l'utilisateur
le priorise, sans sauter ses prérequis ni laisser deux branches de développement actives.
La totalité des modules spécialisés n'est pas nécessaire au pilote D13. La 3D fait partie
du produit visé, mais une voie 2D accessible reste disponible.

## Passage depuis l'ancien plan

- R0–R7 : reset terminé. Ne plus le reprendre comme prochaine étape.
- H1–H3 : intégrés ; le P0 de dispatch H4 est corrigé par #83.
- H4 restant : D01–D03 ; H5 : D04. Aucune nouvelle fonction produit avant cette sortie.
- G51 : base de planification présente, reprise dans D06.
- Anciens blocs 0–2 : fondations présentes, intégrations optionnelles encore à finir.
- Ancien bloc 3 : D05–D13 ; bloc 4 : D11–D16 ; bloc 5 : D17–D20 ; bloc 6 : D01–D04/D21–D22.

Le registre des composants reste plus large que le runtime nécessaire. Déclarer un moteur
n'impose pas de le démarrer ni de lui fabriquer un consommateur. Les décisions KISS de l'audit
priment sur une conservation historique sans usage.
