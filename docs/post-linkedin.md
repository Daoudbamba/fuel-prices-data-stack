# Post LinkedIn : « Pourquoi j'ai remplacé mes scripts SQL par dbt »

Brouillon à relire et à publier soi-même. Tous les chiffres viennent des mesures du projet
(novembre 2026, voir le README).

## Angle

Pas un tutoriel dbt. L'histoire d'un **moment précis** : une donnée fausse (un prix multiplié
par 10) qui, avec des scripts SQL enchaînés, serait allée droit au tableau de bord, et qu'un test
dbt arrête. Le message : dbt ne m'a pas fait écrire un autre SQL, il a changé **ce qui se passe
quand la donnée est fausse**.

Trois idées à faire passer, pas plus :

1. Des scripts SQL exécutent ; dbt **refuse** (un test en échec bloque les modèles en aval).
2. Le graphe de dépendances et la documentation sortent du code, gratuitement.
3. Les tests ont trouvé de vraies anomalies dans un flux officiel : ce n'est pas de la théorie.

Public visé : recruteurs et Data Engineers. Ton : concret, chiffré, sans superlatifs.

## Brouillon

> Pourquoi j'ai remplacé mes scripts SQL par dbt.
>
> Sur mon dernier projet, j'ingère chaque matin les prix officiels des carburants : ≈ 9 950 stations,
> 35 jours, 1 million de prix.
>
> J'ai fait un test simple : multiplier un vrai prix de gazole par 10. 2,069 € devient 20,69 €.
> La virgule décalée, l'erreur la plus banale qui soit.
>
> Avec une suite de scripts SQL, cette ligne passe. Elle fausse la moyenne du département et
> arrive dans le tableau de bord.
>
> Avec dbt, le test métier « prix dans les bornes plausibles » échoue, et les 12 tables en aval ne
> sont pas reconstruites. Le tableau de bord garde les derniers chiffres justes. La ligne fautive
> reste consultable dans un schéma d'audit. Je rejoue la journée, tout repasse au vert.
>
> Ce que dbt m'a apporté, concrètement :
> → 76 tests qui bloquent au lieu de laisser passer
> → l'ordre d'exécution et le graphe de dépendances déduits du code
> → une table de faits incrémentale (on ne recalcule que le jour chargé)
> → une documentation générée, toujours à jour
>
> Et les tests ont trouvé de vraies anomalies dans le flux officiel : 38 doublons, une station de
> test au code postal 99999, des prix figés depuis 2009.
>
> Au passage, ce que disent les données : le gazole est 9,8 centimes moins cher en grande
> distribution que chez les pétroliers (18/11/2026).
>
> Stack : Airflow, PostgreSQL, dbt, Metabase, Docker, GitHub Actions.
> Le code et la démo sont sur GitHub : [lien du dépôt]
>
> Je cherche une alternance en Data Engineering : si votre équipe fait du dbt, parlons-en.
>
> #dbt #DataEngineering #AnalyticsEngineering #Airflow #OpenData #Alternance

## Visuels proposés

1. Capture de la sortie de la démo (`docs/demo_donnee_cassee.txt`) : le `FAIL 1` puis le
   `PASS=91 … ERROR=0`. C'est le cœur du post.
2. Le graphe de dépendances dbt (`docs/images/dbt-graphe-dependances.png`).
3. Le tableau de bord Metabase (`docs/images/metabase-tableau-de-bord.png`).

## Avant de publier

- Remplacer `[lien du dépôt]` une fois le dépôt poussé sur GitHub.
- Vérifier que la CI est verte sur GitHub (elle n'a été rejouée qu'en local).
- Citer les sources si une capture du tableau de bord est jointe : prix-carburants.gouv.fr,
  © contributeurs OpenStreetMap (ODbL). L'attribution figure déjà dans le tableau de bord.
