# Agenda RSS automatique — Beaune & Pays Beaunois

Ce projet génère automatiquement un **flux RSS de 6 événements** destiné à Mailchimp à partir du flux public :

`https://www.beaune-tourisme.fr/playlist/35902.rss`

## Ce qu'il fait automatiquement

Chaque jeudi à 07:15, heure de Paris :

1. récupération des événements du flux source ;
2. lecture des fiches pour récupérer si possible dates, commune, image et description ;
3. ciblage de la semaine suivante, du lundi au dimanche ;
4. sélection de 6 événements sans reprendre simplement les 6 premiers ;
5. diversification par commune et par thématique ;
6. priorité aux événements illustrés et ponctuels ;
7. pénalisation des événements utilisés au cours des 2 semaines précédentes ;
8. génération du RSS et d'une page d'aperçu ;
9. publication automatique sur GitHub Pages.

La sélection est stable pendant toute la semaine.

## Hébergement gratuit

La solution utilise un dépôt GitHub **public** avec GitHub Pages et GitHub Actions.

### Installation unique

1. créer un dépôt GitHub public, par exemple `agenda-rss-beaune` ;
2. déposer tous les fichiers de ce ZIP dans le dépôt ;
3. ouvrir **Settings → Pages** ;
4. dans **Build and deployment → Source**, choisir **GitHub Actions** ;
5. ouvrir l'onglet **Actions** et lancer une première fois :
   **Mettre à jour l'agenda RSS → Run workflow**.

Une fois le workflow terminé, GitHub Pages donnera l'URL publique du site.
Le flux sera disponible à :

`https://VOTRE-COMPTE.github.io/NOM-DU-DEPOT/feed.xml`

La racine du site affiche également un aperçu visuel des 6 événements choisis.

## Bloc Mailchimp

Dans le bloc RSS/Code Mailchimp :

```text
*|FEEDBLOCK:https://VOTRE-COMPTE.github.io/NOM-DU-DEPOT/feed.xml|*
*|FEEDITEMS:[$count=6]|*
*|FEEDITEM:CONTENT_FULL|*
*|END:FEEDITEMS|*
*|END:FEEDBLOCK|*
```

Le design validé des cartes est déjà intégré dans chaque élément du RSS via `content:encoded` :
- fond beige clair ;
- image à gauche ;
- date + commune ;
- titre prune ;
- texte court ;
- bouton terracotta « Découvrir ».

## Pourquoi ce système évite le problème actuel

Mailchimp ne choisit plus lui-même les 6 premiers événements du gros flux.
Il reçoit directement un flux qui **ne contient que les 6 événements sélectionnés** pour la semaine.

## Réglages

Dans `.github/workflows/update-feed.yml` :
- `COUNT: "6"` = nombre d'événements ;
- le cron = jour/heure de génération.

Dans `generate_feed.py` :
- `MAX_PER_CITY = 2`
- `MAX_PER_CATEGORY = 2`

## Important

Le système dépend du flux public Beaune Tourisme et de la structure des fiches événements. Si le site change fortement, le script pourra nécessiter une adaptation.
