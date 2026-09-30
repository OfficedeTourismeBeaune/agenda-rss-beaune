# Agenda RSS — Beaune & Pays Beaunois

Ce dépôt publie un **flux RSS hebdomadaire de 6 événements** destiné à Mailchimp.

## Fonctionnement actuel

La sélection est mise à jour chaque **mercredi à 9 h (Europe/Paris)**.

Le fonctionnement actuellement validé est le suivant :

1. sélectionner exactement 6 événements pour la semaine suivante, du lundi au dimanche ;
2. vérifier les dates, communes, titres, descriptions, liens et images ;
3. consulter `docs/history.json` pour éviter de reprendre trop souvent les mêmes événements ;
4. mettre à jour directement :
   - `docs/feed.xml`
   - `docs/index.html`
   - `docs/history.json`
5. laisser GitHub Pages publier les fichiers ;
6. créer ensuite manuellement la campagne Mailchimp.

Le script `generate_feed.py` n'est plus utilisé pour la génération hebdomadaire courante.

## Dépôt et connexion GitHub

Toujours utiliser la connexion GitHub de l'Office :

- compte : `OfficedeTourismeBeaune`
- dépôt : `OfficedeTourismeBeaune/agenda-rss-beaune`
- branche : `main`

Avant toute lecture ou écriture automatisée, vérifier que le dépôt apparaît bien dans la liste des dépôts accessibles avec ce compte.

Si un accès direct retourne une erreur 404 alors que le dépôt apparaît dans cette liste, considérer d'abord qu'il s'agit d'un problème ponctuel de connexion ou d'autorisation. Ne pas basculer automatiquement vers un autre compte GitHub.

## Règles de sélection

La sélection doit contenir exactement 6 événements :

- réellement programmés pendant la semaine cible ;
- plutôt ponctuels que très récurrents ;
- variés en thèmes et en communes ;
- non terminés ;
- sans doublons ;
- en évitant les événements déjà utilisés récemment, sauf intérêt éditorial particulier.

`docs/history.json` doit être consulté avant la sélection finale.

## Validation obligatoire des images

Chaque événement doit avoir une image valide avant publication.

Priorité aux images provenant directement de :

1. la fiche Beaune Tourisme ;
2. Tourinsoft / Cloudly ;
3. à défaut, une source officielle de l'organisateur.

### Avant publication

Pour chaque URL d'image :

- vérifier qu'elle se charge réellement ;
- vérifier qu'elle renvoie bien une image ;
- refuser toute URL qui renvoie une erreur, une page HTML, un cache miss ou une ressource inaccessible ;
- si l'image échoue, chercher une autre image valide de la même fiche ou une image officielle de remplacement.

**Ne jamais publier une carte avec une image cassée.**

Les 6 images doivent être validées avant toute écriture dans le dépôt.

## Format du flux

Le titre du canal doit être mis à jour chaque semaine :

`du [date de début] au [date de fin] [année]`

Exemple :

`du 5 au 11 octobre 2026`

La description suit le format :

`Retrouvez tous les événements de [mois] [année] sur`

Pour une semaine à cheval sur deux mois, utiliser le mois qui contient le plus de jours de la semaine cible. En cas d'égalité, utiliser le mois de la date de fin.

## Design Mailchimp

Le design validé des cartes doit être conservé :

- fond `#fbf8f5`
- border-radius : `8px`
- image à gauche : 36 %
- texte à droite : 64 %
- padding : 14px
- date / commune : 11px, `#8b7770`, uppercase
- titre : 17px, `#432f32`, bold
- corps : 13px, `#55504e`
- bouton : `#bd3d00`
- marge basse : 22px

## Contrôle après publication

Après chaque mise à jour :

1. relire `docs/feed.xml`, `docs/index.html` et `docs/history.json` depuis GitHub ;
2. vérifier que `feed.xml` contient exactement 6 `<item>` ;
3. vérifier que `index.html` affiche exactement 6 cartes ;
4. vérifier les 6 liens d'événements ;
5. revérifier les 6 images ;
6. vérifier la page GitHub Pages.

Page publique :

https://officedetourismebeaune.github.io/agenda-rss-beaune/

Flux RSS :

https://officedetourismebeaune.github.io/agenda-rss-beaune/feed.xml

## Mailchimp

Bloc utilisé dans Mailchimp :

```text
*|FEEDBLOCK:https://officedetourismebeaune.github.io/agenda-rss-beaune/feed.xml|*
*|FEEDITEMS:[$count=6]|*
*|FEEDITEM:CONTENT_FULL|*
*|END:FEEDITEMS|*
*|END:FEEDBLOCK|*
```

La campagne Mailchimp reste créée manuellement.
