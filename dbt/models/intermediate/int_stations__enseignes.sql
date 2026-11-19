-- Enseigne normalisée de chaque station connue d'OpenStreetMap.
-- Les libellés OSM (« Total », « Total Energies », « Super U », « Système U »...) sont
-- regroupés par le référentiel seeds/correspondance_enseignes.csv. Une marque absente
-- du référentiel devient « Autre » ; une station sans marque dans OSM, « Inconnue ».
select
    o.id_station,
    o.marque_osm,
    o.est_marque_ambigue,
    case
        when c.enseigne is not null then c.enseigne
        when o.marque_osm is null then 'Inconnue'
        else 'Autre'
    end as enseigne,
    case
        when c.type_enseigne is not null then c.type_enseigne
        when o.marque_osm is null then 'inconnu'
        else 'autre'
    end as type_enseigne
from {{ ref('stg_osm__enseignes') }} as o
left join {{ ref('correspondance_enseignes') }} as c on c.marque_osm = o.marque_osm
