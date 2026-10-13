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

Les six images proviennent exclusivement des fiches Beaune Tourisme exactes : image Event JSON-LD, sinon og:image, sinon image principale de la fiche. Aucune image de remplacement externe ou générique.

Le workflow unique `.github/workflows/sync-event-images.yml` contrôle la cohérence des trois fichiers, télécharge les images en JPEG, valide les six fichiers locaux, puis publie et vérifie les fichiers publics. Une erreur bloque le déploiement et préserve la dernière édition publiée.

Les trois fichiers éditoriaux doivent être écrits dans **un seul commit atomique**, avec vérification du SHA courant de main. Ne pas effectuer trois commits séparés. Le workflow se déclenche sur toute modification du flux, de la page, de l’historique ou des scripts. Les exécutions Pages sont sérialisées.

Le traitement des images remplace chaque visuel dans sa propre carte, même si plusieurs cartes utilisaient initialement la même URL. Les téléchargements sont préparés avant modification des fichiers éditoriaux.

L’automatisation ChatGPT effectue la sélection éditoriale le mercredi à 9 h Europe/Paris ; le contrôle de secours reste à 13 h. GitHub Actions assure ensuite les images, les validations et la publication. Aucun envoi Mailchimp automatique.

## Vérification technique

```sh
python scripts/validate_agenda.py
python scripts/sync_event_images.py
python scripts/validate_agenda.py --local-images
# Après déploiement seulement :
python scripts/validate_agenda.py --published
```

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

