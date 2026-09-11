# KAIRO — reproductibilité

État D03 : baseline v9, fondée sur les pins H3/D02, sans nouveau digest inventé.
Le checkpoint contient le SHA effectivement validé ; la [politique G50](archive/reproducibility-g50-before-d03.md)
est archivée et n'est plus l'état courant.

- `pnpm-lock.yaml` et `uv.lock` à la racine sont les graphes canoniques ; `pnpm@10.15.1` et `uv==0.12.13` sont fixés.
- Tous les builds utilisent frozen/locked. D03 retire les dépendances directes Worker browser-use/Playwright
  sans changer les versions des moteurs conservés. Les entrées transitives déjà verrouillées ne prouvent pas un consommateur.
- Les images Compose et toutes les bases Docker sont digérées. Le contrôle inclut chaque FROM,
  les COPY --from externes, les images de services CI et les conteneurs lancés par docker run en CI.
  Un nom de stage local n'est pas une image externe. Le stand-in Python de CI réutilise la base Python
  déjà digérée, au lieu d'un tag mobile. Les quatre images applicatives sont multi-stage et non root.
- Les neuf workflows gardent leurs gates sur chaque PR concernée et sur main. Les branches ne déclenchent
  plus une seconde série identique par push. Les filtres de chemins existants sont conservés.
- Les conteneurs générés par OpenHands ne sont pas couverts par le pin du serveur : l'image enfant reste
  UNCONFIGURED jusqu'à fourniture d'un tag+digest vérifié. Production bloque cette intégration non livrée.
- Les modèles téléchargés n'héritent pas du digest de leur conteneur. Un bundle local documente ses
  sources/révisions/licences et tous ses SHA-256 ; le Worker de production le vérifie avant démarrage,
  le lit sans écriture et utilise les modes hors ligne. Son exécution réelle reste à prouver en D04.

Mise à jour : modifier explicitement références, déclarations et lockfiles avec les outils requis,
mettre à jour la baseline dans la même PR, vérifier les scénarios affectés puis le head final.
Ne pas réduire une assertion pour rendre une mise à jour verte ; ne pas promouvoir un succès de stub
en preuve de vrai moteur. Conserver image et bundle précédents avec le backup pour le rollback.
Le [guide de déploiement](deployment.md) donne les profils, identités SQL et procédures de modèles.

Les scans SBOM/vulnérabilités/licences complets et les upgrades/rollbacks sur matériel réel ne sont pas
prouvés par le simple pin d'une image. Les API de fournisseurs externes peuvent évoluer derrière leur
nom de modèle. Ces limites restent explicites dans les preuves D04 puis la distribution D21/D22.
