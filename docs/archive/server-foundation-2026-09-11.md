# D04 — socle serveur privé validé le 11 septembre 2026

Ce rapport conserve le jalon opératoire vérifié avant l'installation de Docker. Il ne contient ni
adresse IP/MAC, identifiant fournisseur, compte d'administration, clé, empreinte de clé, secret ou
capture du panneau. Les valeurs propres à l'installation restent dans le registre d'exploitation privé.

## Cible et limites du jalon

- Netcup RS 4000 G12, Linux AMD64 virtualisé KVM, 12 vCPU, 32 Gio de RAM et disque d'environ 1 Tio.
- Debian 13 (trixie), noyau `6.12.107+deb13-amd64`, horloge UTC et synchronisation NTP active.
- Nom d'hôte court et FQDN cohérents ; résolution locale normalisée. Cloud-init est désactivé sur l'image
  fournisseur et ne réécrit pas ces valeurs.
- Ce jalon qualifie l'accès et le socle système. Il ne qualifie encore ni Docker, ni Nevolium, ni TLS,
  ni les moteurs, ni les sauvegardes applicatives.

## Accès administratif

- Compte non-root dédié, membre de `sudo`, avec authentification Ed25519 protégée par phrase secrète.
- Nouvelle session par clé vérifiée avant fermeture de l'accès initial et de nouveau après les deux
  pare-feu puis après un cycle d'arrêt/rallumage fournisseur.
- SSH effectif : root et mots de passe interdits, clé publique obligatoire, utilisateur autorisé borné,
  trois essais, cinq sessions, délai de connexion 30 secondes, X11/agent/tunnel interdits et transfert
  TCP limité au local.
- La console fournisseur reste la voie de récupération. La clé privée et sa phrase secrète ne résident
  ni dans Git, ni sur le serveur.

## Maintenance et journalisation

- `unattended-upgrades`, les deux timers APT, Fail2ban et nftables sont activés et persistants.
- Mises à jour automatiques quotidiennes, nettoyage hebdomadaire, noyaux inutilisés supprimables et
  redémarrage automatique interdit. Le dry-run s'est terminé avec le code 0.
- Journal systemd persistant, compressé et scellé, plafond 1 Gio, réserve disque 5 Gio, plafond runtime
  256 Mio et rétention maximale 30 jours.
- Fail2ban utilise le backend systemd et l'action nftables pour SSH : quatre échecs sur dix minutes,
  bannissement initial d'une heure, croissance jusqu'à une semaine. Configuration, socket et jail SSH
  ont été vérifiés après redémarrage.

## Défense réseau en profondeur

Le pare-feu hôte nftables possède une chaîne `input` à refus par défaut : loopback, états
`established,related`, ICMP/ICMPv6 et nouveaux flux TCP vers 22/80/443 sont acceptés ; états invalides
refusés. La sortie hôte reste autorisée. PostgreSQL, NATS, Neo4j, OpenBao, Ollama et les interfaces
d'administration ne doivent jamais être publiés.

Le pare-feu fournisseur applique avant ses règles implicites une politique personnalisée :

- entrées TCP 22, 80 et 443 autorisées ;
- ICMP et ICMPv6 autorisés ;
- réponses entrantes DNS TCP/UDP, HTTP/HTTPS TCP, NTP UDP et HTTPS UDP autorisées explicitement pour
  rester compatibles avec un filtrage fournisseur sans état documenté ;
- autres entrées TCP et UDP refusées ;
- blocage fournisseur par défaut des sorties SMTP 25/465/587 conservé.

Le pare-feu hôte avec suivi d'état reste l'autorité fine : une source distante utilisant un port source
autorisé par la couche fournisseur n'obtient pas pour autant l'accès à un port local arbitraire. Le
blocage SMTP empêche pour l'instant l'envoi direct via un relais SMTP, y compris Infomaniak ; choisir
et tester ultérieurement une API transactionnelle ou une exception de relais bornée.

## Preuves observées et reprise

- DNS, APT, ping IPv4/IPv6 et HTTPS IPv4/IPv6 réussis après application du pare-feu fournisseur.
- Arrêt propre puis rallumage exigé par le panneau Netcup effectué.
- Après cold boot : SSH par clé, nftables, Fail2ban et timers APT actifs ; règles nftables restaurées ;
  réponses HTTPS IPv4 et IPv6 `200`.
- Debian n'annonçait aucun redémarrage en attente et le noyau courant correspondait au noyau attendu.

Prochain point sûr : créer un snapshot fournisseur nommé sans secret, puis installer Docker Engine et
Compose depuis le dépôt officiel Debian de Docker. Le snapshot ne remplace pas le futur backup Restic
chiffré, indépendant du serveur et restauré sur volumes neufs.
