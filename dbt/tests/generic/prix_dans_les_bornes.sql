{#
    Test métier : chaque prix doit rester dans les bornes plausibles de son carburant,
    définies dans le référentiel seeds/carburants.csv. Il vise les erreurs d'unité ou de
    saisie (2,086 € saisi 20,86 € ou 0,2086 €), pas les prix simplement élevés.
    Renvoie les lignes fautives, avec les bornes, pour faciliter l'analyse.
#}
{% test prix_dans_les_bornes(model, column_name, referentiel) %}

select
    m.*,
    r.prix_min_plausible,
    r.prix_max_plausible
from {{ model }} as m
inner join {{ referentiel }} as r on r.id_carburant = m.id_carburant
where m.{{ column_name }} not between r.prix_min_plausible and r.prix_max_plausible

{% endtest %}
