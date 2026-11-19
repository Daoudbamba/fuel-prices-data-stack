-- Prix quotidiens enrichis des règles métier :
--   - age_prix_jours : ancienneté de la dernière mise à jour du prix ;
--   - est_recent : prix mis à jour depuis au plus N jours (variable du projet) ;
--   - ecart_mediane_departement : écart relatif à la médiane des prix récents du même
--     carburant, dans le même département, le même jour ;
--   - est_atypique : écart supérieur au seuil du projet (signalé, pas supprimé).
with prix as (

    select
        p.date_fichier,
        p.id_station,
        p.id_carburant,
        p.code_carburant,
        p.prix_litre,
        p.maj,
        p.charge_le,
        s.code_departement,
        p.date_fichier - (p.maj at time zone 'Europe/Paris')::date as age_prix_jours
    from {{ ref('stg_carburants__prix') }} as p
    inner join {{ ref('stg_carburants__stations') }} as s
        on s.date_fichier = p.date_fichier
        and s.id_station = p.id_station

),

qualifies as (

    select
        *,
        age_prix_jours <= {{ var('age_max_prix_recent_jours') }} as est_recent
    from prix

),

medianes as (

    select
        date_fichier,
        code_departement,
        id_carburant,
        percentile_cont(0.5) within group (order by prix_litre) as prix_median_departement
    from qualifies
    where est_recent
    group by 1, 2, 3

)

select
    q.*,
    m.prix_median_departement,
    round((q.prix_litre / nullif(m.prix_median_departement, 0) - 1)::numeric, 4)
        as ecart_mediane_departement,
    coalesce(
        abs(q.prix_litre / nullif(m.prix_median_departement, 0) - 1)
            > {{ var('ecart_max_mediane_departement') }},
        false
    ) as est_atypique
from qualifies as q
left join medianes as m
    on m.date_fichier = q.date_fichier
    and m.code_departement = q.code_departement
    and m.id_carburant = q.id_carburant
