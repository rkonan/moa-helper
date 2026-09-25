WITH
    auto_controle AS
    (
        SELECT
            'YES'    AS auto_controle,
            'PRIIPS' AS type_reporting
        FROM
            dual
    )
    ,
    arrete AS -- date arrete
    (
        SELECT
            '30/11/2025' AS date_arrete, -- TNR_DATE
            'PRIIPS'     AS type_reporting
        FROM
            dual
    )
    ,
    -- Coordonnees techniques des tableaux FIXFEE centralisees ici pour eviter
    -- les "nombres magiques" disperses dans les jointures.
    parametrage_coordonnees_fixfee AS
    (
        SELECT
            1 AS col_balise,
            2 AS col_code_poste_detail,
            6 AS decalage_montant_detail_standard,
            3 AS decalage_montant_detail_feedp,
            2 AS ligne_average_assets,
            7 AS ligne_last_management_fee_base,
            4 AS col_average_assets_12m,
            5 AS col_average_assets_36m,
            2 AS col_last_management_fee_base
        FROM dual
    )
    ,
    portefeuilles AS -- ensemble de portfeuilles à traiter
    (
        SELECT
            *
        FROM
            (
                SELECT
                    CODE_PORTEFEUILLE,
                    CASE
                        WHEN lmf.resultat_condition_fille IS NULL
                        THEN 'NO'
                        ELSE 'YES'
                    END AS a_date
                FROM
                    descriptif_port_reporting dpr
                LEFT JOIN
                    condition_complexe lmf -- pas forcement necessaire de recuperer le parametrage
                    -- a date a ce niveau. On peut simplement travailler sur les tables details DP
                    -- ou PP
                ON
                    lmf.code_besoin ='INV'
                AND lmf.nature_condition ='SDGPTF'
                AND lmf.nature_condition_fille ='SOCGES'
                AND dpr.societe_gestion = lmf.resultat_condition_fille
                WHERE
				--code_portefeuille in ('590027','051653','053391') and 
                   societe_gestion IN ('000738','004275','026528','005960','037166'))
            --where CODE_PORTEFEUILLE ='ES017'
       -- WHERE
           -- CODE_PORTEFEUILLE IN ('306','050036')
    )
    ,
    /* MOA - Perimetre fonctionnel des cumuls PRIIPS a restituer.
       FCEL relie le cumul de reporting (CHG/EMT) au parametrage qui permettra
       ensuite de retrouver les balises FIXFEE contribuant a ce cumul. */
    parametrage_cumul_1 AS
    (
        SELECT
            cr.*,
            pcc.*,
            'PRIIPS' AS type_reporting_gt
        FROM
            cumul_reporting cr
        LEFT JOIN
            parametre_champ_condition pcc
        ON
            cr.identifiant_cumul = pcc.critere_saisie_3
        WHERE
            ((
                    pcc.valeur_champ_ref IN ('OTHMOY',
                                             'INIMOY')
                AND pcc.code_gestion ='N')
            OR  (
                    pcc.valeur_champ_ref IN ('ININOR','OTPA')
                AND pcc.code_gestion ='O'))
        AND pcc.code_traitement ='FCEL'
        AND cr.code_tableau ='PRFEE3'
        AND cr.identifiant_cumul IN ('CHG_INI',
                                     'CHG_OTH',
                                     'EMT_OTH',
                                     'EMT_INI')
    )
    --select * from parametrage_cumul_1;
    ,
    /* MOA - Contexte de traitement.
       Une ligne represente un portefeuille / une part / une date d'arrete PRIIPS.
       Ce CTE constitue le point de depart fonctionnel avant de rechercher les
       tableaux de frais FIXFEE correspondants. */
    contexte_priips AS
    (
        SELECT
            gt.code_tableau,
            gt.code_portefeuille,
            gt.date_arrete,
            gt.type_reporting,
            SUBSTR(gt.code_tableau, 9, 2) AS code_part,
            ptf.a_date,
            CASE
                WHEN ac.auto_controle IS NULL THEN 'NO'
                ELSE ac.auto_controle
            END AS auto_controle
        FROM gestion_tableau gt
        JOIN portefeuilles ptf
            ON gt.code_portefeuille = ptf.code_portefeuille
        JOIN arrete a
            ON gt.date_arrete = a.date_arrete
            AND gt.type_reporting = a.type_reporting
        LEFT JOIN auto_controle ac
            ON ac.auto_controle = 'YES'
            AND gt.type_reporting = ac.type_reporting
        WHERE gt.type_reporting = 'PRIIPS'
    ),
    /* MOA - Inventaire des tables physiques FIXFEE disponibles pour le contexte PRIIPS.
       Les familles correspondent au niveau de calcul documente NeoXam :
         FEE-DF : frais en fin de periode - portefeuille
         FEE-PF : frais sur periodes       - portefeuille
         FEE-DP : frais en fin de periode - part
         FEE-PP : frais sur periodes       - part
       Les SUBSTR ci-dessous ne servent qu'a decoder la nomenclature GP des tables. */
    tables_fixfee AS
    (
        SELECT
            code_portefeuille,
            date_arrete,
            type_reporting,
            code_tableau,
            SUBSTR(code_tableau, 1, 6) AS famille_fixfee,
            SUBSTR(code_tableau, 8, 2) AS code_part_fixfee
        FROM gestion_tableau gt 
        WHERE type_reporting = 'FIXFEE' AND EXISTS (
            SELECT 1
            FROM contexte_priips cp
            WHERE cp.code_portefeuille = gt.code_portefeuille
            AND cp.date_arrete = gt.date_arrete
            
        )
    ),
    /* MOA - Choix des tables FIXFEE a utiliser pour chaque portefeuille/part.
       On rattache au contexte PRIIPS les quatre niveaux de calcul possibles.
       Les colonnes level_fee_* contiennent les vrais codes de tables GP a lire. */
    parametrage_cumul AS -- on recupere pour chaque portefeuille,
    (
        SELECT
            pcl.*,
            gt1.type_reporting          AS type_calcul,
            gt1.code_tableau            AS level_fee_df,
            gt2.code_tableau            AS level_fee_pf,
            gt3.code_tableau            AS level_fee_dp_shc,
            gt4.code_tableau            AS level_fee_pp_shc,
            cp.code_part,
            cp.code_portefeuille,
            cp.date_arrete,
            cp.a_date,
            cp.auto_controle
        FROM
            parametrage_cumul_1 pcl
        JOIN contexte_priips cp
        ON cp.type_reporting = pcl.type_reporting_gt
        
        LEFT JOIN
            tables_fixfee gt1
        ON gt1.code_portefeuille = cp.code_portefeuille
            AND gt1.date_arrete = cp.date_arrete
            AND gt1.famille_fixfee ='FEE-DF'
        LEFT JOIN
            tables_fixfee gt2
        ON
            gt2.type_reporting ='FIXFEE'
        AND gt2.date_arrete = cp.date_arrete
        AND cp.code_portefeuille = gt2.code_portefeuille
        AND gt2.famille_fixfee ='FEE-PF'
        LEFT JOIN
            tables_fixfee gt3
        ON
            gt3.type_reporting ='FIXFEE'
        AND gt3.date_arrete = cp.date_arrete
        AND cp.code_portefeuille = gt3.code_portefeuille
        AND gt3.famille_fixfee ='FEE-DP'
        AND cp.code_part = gt3.code_part_fixfee
        LEFT JOIN
            tables_fixfee gt4
        ON
            gt4.type_reporting ='FIXFEE'
        AND gt4.date_arrete = cp.date_arrete
        AND cp.code_portefeuille = gt4.code_portefeuille
        AND gt4.famille_fixfee ='FEE-PP'
        AND cp.code_part = gt4.code_part_fixfee
    )
    ,
    /* MOA - Interpretation du parametrage MAJCEL.
       PCC indique, pour chaque primitive/balise, dans quelle famille FIXFEE et
       dans quelle colonne se trouve le montant. On traduit ici la famille
       logique (FEE-PF, FEEDP*, FEEPP*) vers la table physique du portefeuille.
       SWING_COST est traite a part car il n'a pas de tableau de detail. */
    parametrage_majcel_config AS
    (
        SELECT
            pcc.code_traitement   AS code_traitement_1 ,
            pcc.code_ensemble_val AS code_ensemble_val_1 ,
            pcc.categorie_valeur  AS PRIMITIVE,
            pcc.critere_saisie_1  AS code_tableau_1,
            CASE
                WHEN pcc.critere_saisie_1 ='FEE-PF'
                AND pcc.critere_saisie_2 = 'SWING_COST' -- le swing cost n'a pas de detail
                THEN pc.level_fee_pf
                WHEN pcc.critere_saisie_1 IN ('FEEDP*',
                                              'FEEDP *')
                THEN pc.level_fee_dp_shc
                WHEN pcc.critere_saisie_1 IN ('FEEPP*',
                                              'FEEPP *')
                THEN pc.level_fee_pp_shc
                ELSE pcc.critere_saisie_1
            END                  AS choix_code_tableau ,
             CASE
                WHEN pcc.critere_saisie_1 ='FEE-PF'
                THEN pc.level_fee_pf
                 WHEN pcc.critere_saisie_1 ='FEE-DF'
                THEN pc.level_fee_df
                WHEN pcc.critere_saisie_1 IN ('FEEDP*',
                                              'FEEDP *')
                THEN pc.level_fee_dp_shc
                WHEN pcc.critere_saisie_1 IN ('FEEPP*',
                                              'FEEPP *')
                THEN pc.level_fee_pp_shc
                
            END                  AS choix_code_tableau_fix_fee ,
            pcc.critere_saisie_2 AS balise_fixfee ,
            CASE
                WHEN trim(db.libelle_balise) IS NULL
                THEN trim(db2.libelle_balise)
                ELSE trim(db.libelle_balise)
            END                  AS libelle_balise_fixfee,
            pcc.critere_saisie_3 AS choix_colonne_ct_fixfee ,
            pc.* -- /!\ a optimiser beaucoup de donnee redondante dans ce tableau
        FROM
            parametre_champ_condition pcc
        JOIN
            parametrage_cumul pc
        ON
            TRIM(pcc.categorie_valeur)=TRIM(pc.VALEUR_PAR_DEFAUT)
        AND pcc.code_traitement='MAJCEL'
        AND pcc.CODE_ENSEMBLE_VAL='FIXFEE'
        AND pcc.critere_saisie_2 IN ('MGTF_EXA',
                                     'DISF_EXA',
                                     'DISF_EXP',
                                     'MGTF_EXP',
                                     'NEG_INT',
                                     'OTH_EXP',
                                     'REV_ROPC',
                                     'SUB_FEES',
                                     'SWING_COST',
                                     'TRF_BRO',
                                     'TRF_COA',
                                     'TRF_RSCH',
                                     'TRF_TAX',
                                     'INDI_EXP',
                                     'TF_AFEES_8',
                                     'TF_AFEES_0',
                                     'CUST_EXP',
                                     'CUST_EXA')
        LEFT JOIN
            --tra_descriptif_balise db
            descriptif_balise db
        ON
            pcc.critere_saisie_2 = db.code_balise
        LEFT JOIN
            tra_descriptif_balise db2
        ON
            db.code_balise=db2.code_balise
        AND db2.langue_traduction='FRA'
        
    ),
    /* MOA - Localisation de la balise dans CONTENU_TABLEAU.
       La colonne 1 porte la balise ; sa ligne devient numero_ligne_ct.
       code_tableau_detail donne ensuite le niveau de detail a parcourir.
       niveau_calcul traduit les codes DET-* en libelles fonctionnels MOA. */
    parametrage_majcel AS
    (
        SELECT
            pmc.*,
            ct.numero_ligne AS numero_ligne_ct,
            CASE
                WHEN ct.code_tableau_detail IS NULL THEN 'NA'
                ELSE ct.code_tableau_detail
            END AS code_tableau_detail,
            dpa.CODE_VALEUR_MAJVAC,
            dp.DEVISE_PORTEFEUILLE ,
            CASE
                WHEN trim(ct.code_tableau_detail) ='DET-FEEDF'
                THEN 'Fee Data on Period End - By Portfolio'
                WHEN trim(ct.code_tableau_detail) ='DET-FEEDP'
                THEN 'Fee Data on Period End - By Shareclass'
                WHEN trim(ct.code_tableau_detail) ='DET-FEEPF'
                THEN 'Fee Data on Periods - By Portfolio'
                WHEN trim(ct.code_tableau_detail) IN ('DET-FEEP',
                                                      'DET-FEEPP')
                THEN 'Fee Data on Periods - By Shareclass'
                ELSE trim(dt.libelle_tableau)
            END AS niveau_calcul,
            CASE
                WHEN 
                EXTRACT(MONTH FROM TO_DATE(pmc.date_arrete)) = EXTRACT(MONTH FROM
                    dcp.date_cloture_exercice)
                THEN 'NO'
                ELSE 'YES'
            END AS CALCUL_ESTIME,
            dcp.date_cloture_exercice,
            dcp.date_ouverture_exercice
        FROM parametrage_majcel_config pmc
    CROSS JOIN parametrage_coordonnees_fixfee cfg
        LEFT JOIN contenu_tableau ct
            ON ct.type_reporting = pmc.type_calcul
            AND ct.numero_colonne = cfg.col_balise
            AND ct.date_arrete = pmc.date_arrete
            AND ct.code_portefeuille = pmc.code_portefeuille
            AND ct.code_tableau = pmc.choix_code_tableau_fix_fee
            AND ct.contenu_cellule = pmc.balise_fixfee
        LEFT JOIN
            descriptif_tableau dt
        ON
            ct.code_tableau_detail=dt.code_tableau
        LEFT JOIN
            descriptif_part dpa
        ON
            pmc.code_portefeuille = dpa.code_portefeuille
        AND trim(pmc.code_part) = trim(dpa.code_part)
        LEFT JOIN
            descriptif_portefeuille dp
        ON
            pmc.code_portefeuille = dp.code_portefeuille
        LEFT JOIN
            descriptif_comptabilite dcp
        ON
            pmc.code_portefeuille = dcp.code_comptabilite
        
    ),

    /* MOA - Lecture du montant global de la balise.
       A ce stade on connait la table, la ligne de la balise et la colonne du cumul.
       JUSTIFICATIF_TABLEAU fournit numero_ligne_detail, passerelle vers le detail. */
    balises_fixfee AS
    (
        SELECT
            pe.*,
            ct.forcage_cellule AS balise_forcage_cellule,
            ct.contenu_cellule AS balise_contenu_cellule,
            ct.numero_colonne AS balise_numero_colonne,
            jt.numero_ligne_detail
        FROM parametrage_majcel pe
        CROSS JOIN parametrage_coordonnees_fixfee cfg
        LEFT JOIN contenu_tableau ct
            ON pe.type_calcul = ct.type_reporting
            AND pe.date_arrete = ct.date_arrete
            AND pe.code_portefeuille = ct.code_portefeuille
            AND pe.choix_code_tableau = ct.code_tableau
            AND pe.numero_ligne_ct = ct.numero_ligne
            AND pe.choix_colonne_ct_fixfee = ct.numero_colonne
        LEFT JOIN justificatif_tableau jt
            ON pe.type_calcul = jt.type_reporting
            AND pe.date_arrete = jt.date_arrete
            AND pe.code_portefeuille = jt.code_portefeuille
            AND pe.choix_code_tableau = jt.code_tableau
            AND pe.numero_ligne_ct = jt.numero_ligne
            AND pe.choix_colonne_ct_fixfee = ct.numero_colonne
    ),

/* MOA - Lecture des lignes du tableau detaille.
   - contenu_poste : cellule permettant d'identifier le poste de frais ;
   - montant_detail_standard : montant du detail selon la structure standard ;
   - montant_detail_feedp : variante utilisee pour le cas DET-FEEDP.
   Les numeros/offsets de colonnes sont centralises dans le CTE de coordonnees. */
detail_balises_fixfee AS
    (
        SELECT
            bf.*,
            ctd.contenu_cellule AS contenu_poste,
            ctd2.contenu_cellule AS montant_detail_standard,
            ctd3.contenu_cellule AS montant_detail_feedp
        FROM balises_fixfee bf
        LEFT JOIN contenu_tableau_detail ctd
            ON bf.type_calcul = ctd.type_reporting
            AND bf.date_arrete = ctd.date_arrete
            AND bf.code_portefeuille = ctd.code_portefeuille
            AND bf.code_tableau_detail = ctd.code_tableau_detail
            AND bf.numero_ligne_detail = ctd.numero_ligne_detail
            AND ctd.numero_colonne_detail = bf.col_code_poste_detail
        LEFT JOIN contenu_tableau_detail ctd2
            ON bf.type_calcul = ctd2.type_reporting
            AND bf.date_arrete = ctd2.date_arrete
            AND bf.code_portefeuille = ctd2.code_portefeuille
            AND bf.code_tableau_detail = ctd2.code_tableau_detail
            AND bf.numero_ligne_detail = ctd2.numero_ligne_detail
            AND ctd2.numero_colonne_detail = bf.balise_numero_colonne + bf.decalage_montant_detail_standard
        LEFT JOIN contenu_tableau_detail ctd3
            ON bf.type_calcul = ctd3.type_reporting
            AND bf.date_arrete = ctd3.date_arrete
            AND bf.code_portefeuille = ctd3.code_portefeuille
            AND bf.code_tableau_detail = ctd3.code_tableau_detail
            AND bf.numero_ligne_detail = ctd3.numero_ligne_detail
            AND ctd3.numero_colonne_detail = bf.balise_numero_colonne + bf.decalage_montant_detail_feedp
    ),

/* MOA - Rattachement du detail au referentiel des postes de frais.
   Le contenu GP n'est pas stocke sous une cle directement exploitable : les REGEXP
   extraient le code valeur. dp2 ajoute la categorie pour lever les ambiguites
   lorsque le meme code valeur existe dans plusieurs categories. */
postes_fixfee AS
    (
        SELECT
            dbf.*,
            dp.code_valeur AS dp_code_valeur,
            dp.lib_poste_l AS dp_lib_poste,
            dp2.code_valeur AS dp2_code_valeur,
            dp2.lib_poste_l AS dp2_lib_poste
        FROM detail_balises_fixfee dbf
        LEFT JOIN descriptif_poste dp
            ON TRIM(REGEXP_SUBSTR(dbf.contenu_poste,'\s\w+\s')) = TRIM(dp.code_valeur)
        LEFT JOIN descriptif_poste dp2
            ON TRIM(REGEXP_SUBSTR(dbf.contenu_poste,'\s\w+\s')) = TRIM(dp2.code_valeur)
            AND TRIM(SUBSTR(dbf.contenu_poste,1,4)) = TRIM(dp2.categorie_valeur)
    ),

/* MOA - Construction du montant de frais et de la base de calcul.
   montant_balise_cumul = montant global porte par la balise dans le tableau principal.
   montant_poste        = montant d'une ligne de detail/poste de frais.
   average_assets       = assiette utilisee pour convertir le montant en taux.
   Les forcages GP sont prioritaires lorsqu'ils contiennent une valeur numerique.
   Pour FEE-PF/FEE-PP, la documentation NeoXam identifie notamment R12M en colonne 4
   et R36M en colonne 5 ; DET-FEEDP suit une regle specifique. */
all_balises_fixfee AS
    (
        SELECT
            pe.*,
            CASE
                WHEN trim(pe.BALISE_FIXFEE) in ('TF_AFEES_8','TF_AFEES_0')
                THEN 'COUTS_INDUITS'
                WHEN trim(pe.BALISE_FIXFEE)='SWING_COST'
                THEN 'SWING_COST'
                WHEN pe.dp2_code_valeur IS NOT NULL
                THEN pe.dp2_code_valeur
                ELSE pe.dp_code_valeur
            END AS code_poste , ---
            CASE
                WHEN trim(pe.BALISE_FIXFEE) in ('TF_AFEES_8','TF_AFEES_0')
                THEN 'COUTS INDUITS'
                WHEN trim(pe.BALISE_FIXFEE)='SWING_COST'
                THEN 'SWING COST'
                WHEN pe.dp2_code_valeur IS NOT NULL
                THEN trim(pe.dp2_lib_poste)
                ELSE trim(pe.dp_lib_poste)
            END AS lib_poste ,
            CASE
                WHEN pe.balise_forcage_cellule != ' '
                AND LENGTH(trim(TRANSLATE(pe.balise_forcage_cellule,' +-.,1234567890',' '))) IS NULL
                THEN to_number(REPLACE(REPLACE(trim(pe.balise_forcage_cellule),',',NULL),'.',','))
                WHEN pe.balise_contenu_cellule IS NULL
                THEN 0
                ELSE to_number(REPLACE(REPLACE(trim(pe.balise_contenu_cellule),',',NULL),'.',','))
            END AS montant_balise_cumul, --- montant au niveau de la table cotenu_tableau. Il s'
            -- agit du cumul sur la sous balise. Ce montant devrait correspondre à la somme des
            -- montants des tableaux detaillés
            CASE
                WHEN pe.balise_fixfee = 'SWING_COST'
                AND pe.balise_forcage_cellule != ' '
                AND LENGTH(trim(TRANSLATE(pe.balise_forcage_cellule,' +-.,1234567890',' '))) IS NULL
                THEN to_number(REPLACE(REPLACE(trim(pe.balise_forcage_cellule),',',NULL),'.',','))
                WHEN pe.balise_fixfee = 'SWING_COST'
                AND pe.balise_forcage_cellule = ' '
                THEN to_number(REPLACE(REPLACE(trim(pe.balise_contenu_cellule),',',NULL),'.',','))
                WHEN pe.dp2_code_valeur IS NOT NULL
                AND pe.balise_contenu_cellule IS NULL
                THEN 0
                WHEN trim(pe.CODE_TABLEAU_DETAIL) ='DET-FEEDP' --- pour le cas a date il faut
                    -- recuperer le CHG_OTH/MGTF_EXA dans le tableau DET-FEEDP
                AND trim(pe.IDENTIFIANT_CUMUL)='CHG_OTH'
                AND trim(pe.BALISE_FIXFEE)='MGTF_EXA'
                AND pe.dp2_code_valeur IS NOT NULL
                AND pe.balise_contenu_cellule IS NOT NULL
                AND pe.montant_detail_feedp IS NOT NULL
                THEN to_number(REPLACE(REPLACE(trim(pe.montant_detail_feedp),',',NULL),'.',','))
                ELSE to_number(REPLACE(REPLACE(trim(pe.montant_detail_standard),',',NULL),'.',','))
            END montant_poste ,
            CASE
                WHEN aa.forcage_cellule != ' '
                AND LENGTH(trim(TRANSLATE(aa.forcage_cellule,' +-.,1234567890',' '))) IS NULL
                THEN to_number(REPLACE(REPLACE(trim(aa.forcage_cellule),',',NULL),'.',','))
                WHEN aa.contenu_cellule IS NULL
                THEN 0
                ELSE to_number(REPLACE(REPLACE(trim(aa.contenu_cellule),',',NULL),'.',','))
            END AS average_assets
        FROM postes_fixfee pe
        LEFT JOIN contenu_tableau aa
          ON aa.date_arrete = pe.date_arrete
         AND aa.code_portefeuille = pe.code_portefeuille
         AND aa.type_reporting = pe.type_calcul
         AND aa.numero_ligne =
             CASE
                 WHEN trim(pe.code_tableau_detail) = 'DET-FEEDP' THEN pe.ligne_last_management_fee_base
                 WHEN trim(pe.code_tableau_detail) IN ('DET-FEEPF','DET-FEEPP') THEN pe.ligne_average_assets
             END
         AND aa.numero_colonne =
             CASE
                 WHEN trim(pe.code_tableau_detail) = 'DET-FEEDP' THEN pe.col_last_management_fee_base
                 WHEN trim(pe.code_tableau_detail) IN ('DET-FEEPF','DET-FEEPP')
                  AND pe.identifiant_cumul = 'CHG_INI' THEN pe.col_average_assets_36m
                 WHEN trim(pe.code_tableau_detail) IN ('DET-FEEPF','DET-FEEPP')
                  AND pe.identifiant_cumul IN ('CHG_OTH','EMT_OTH','EMT_INI') THEN pe.col_average_assets_12m
             END
         AND aa.code_tableau =
             CASE
                 WHEN trim(pe.code_tableau_detail) = 'DET-FEEDP' THEN pe.level_fee_dp_shc
                 WHEN trim(pe.code_tableau_detail) = 'DET-FEEPF' THEN pe.level_fee_pf
                 WHEN trim(pe.code_tableau_detail) = 'DET-FEEPP' THEN pe.level_fee_pp_shc
             END
    )
    ,
    all_balises_fixfee_with_average_asset AS
    (
        SELECT
            apm.CODE_PORTEFEUILLE ,
            apm.CODE_PART ,
            apm.CODE_VALEUR_MAJVAC ,
            apm.DATE_ARRETE ,
            apm.CODE_POSTE ,
            apm.lib_poste ,
            apm.DEVISE_PORTEFEUILLE ,
            apm.IDENTIFIANT_CUMUL ,
            apm.libelle_cumul ,
            apm.BALISE_FIXFEE ,
            apm.libelle_balise_fixfee ,
            apm.niveau_calcul ,
            apm.montant_poste ,
            apm.MONTANT_BALISE_CUMUL ,
            apm.CALCUL_ESTIME,
            apm.auto_controle,
            apm.date_cloture_exercice,
            apm.date_ouverture_exercice,
            apm.average_assets
        FROM all_balises_fixfee apm
    )
    ,
    /* MOA - Agregation au niveau du poste de frais.
       Plusieurs lignes de detail peuvent contribuer au meme poste : elles sont
       sommees ici pour produire FEE_BALANCE. SUB_FEES est restitue avec signe inverse. */
    aa_poste_montant_fixfee AS
    (
        SELECT
            apm.CODE_PORTEFEUILLE ,
            apm.CODE_PART ,
            apm.CODE_VALEUR_MAJVAC ,
            apm.DATE_ARRETE ,
            apm.CODE_POSTE ,
            apm.lib_poste ,
            apm.DEVISE_PORTEFEUILLE ,
            apm.IDENTIFIANT_CUMUL ,
            apm.libelle_cumul ,
            apm.BALISE_FIXFEE ,
            apm.libelle_balise_fixfee ,
            apm.niveau_calcul ,
            apm.average_assets ,
            apm.MONTANT_BALISE_CUMUL ,
            apm.CALCUL_ESTIME,
            apm.auto_controle,
            apm.date_cloture_exercice,
            apm.date_ouverture_exercice,
            CASE
                WHEN SUM(apm.montant_poste) IS NULL
                THEN 0
                WHEN apm.BALISE_FIXFEE='SUB_FEES'
                THEN -ROUND(SUM(apm.montant_poste),6)
                ELSE ROUND(SUM(apm.montant_poste),6)
            END AS FEE_BALANCE
        FROM
            all_balises_fixfee_with_average_asset apm
        GROUP BY
            CODE_PORTEFEUILLE,
            CODE_PART,
            CODE_VALEUR_MAJVAC,
            DATE_ARRETE,
            CODE_POSTE,
            lib_poste,
            average_assets,
            DEVISE_PORTEFEUILLE,
            IDENTIFIANT_CUMUL,
            BALISE_FIXFEE,
            libelle_cumul,
            libelle_balise_fixfee,
            niveau_calcul,
            MONTANT_BALISE_CUMUL,
            CALCUL_ESTIME,
            date_cloture_exercice,
            date_ouverture_exercice,
            auto_controle
    )
    ,
    /* MOA - Mise en forme du fichier de restitution.
       EXPOST concerne EMT_OTH/EMT_INI ; EXANTE concerne CHG_INI/CHG_OTH.
       Le taux est FEE_BALANCE / average_assets * 100. */
    tableau_detail_fixfee_1 AS
    (
        SELECT
            -- Ne pas afficher NULL dans le fichier resultat
            apma.CODE_PORTEFEUILLE           AS SUBFUND_CODE ,
            NVL(apma.CODE_PART, ' ')         AS SHC_CODE ,
            NVL(apma.CODE_VALEUR_MAJVAC,' ') AS SHC_ISIN ,
            apma.DATE_ARRETE                 AS REPORTING_DATE ,
            apma.date_cloture_exercice,
            apma.date_ouverture_exercice,
            apma.CALCUL_ESTIME,
            apma.auto_controle,
            MONTANT_BALISE_CUMUL,
            NVL(apma.CODE_POSTE,' ') AS FEE_CODE ,
            NVL(apma.lib_poste,' ')  AS FEE_NAME ,
            apma.average_assets,
            apma.FEE_BALANCE,
            NVL(apma.DEVISE_PORTEFEUILLE,' ') AS SUBFUND_CURRENCY ,
            CASE
                WHEN (apma.FEE_BALANCE IS NOT NULL
                    AND apma.FEE_BALANCE <> 0)
                AND apma.IDENTIFIANT_CUMUL IN ('EMT_OTH',
                                               'EMT_INI')
                    --  AND CALCUL_ESTIME ='NO'
                AND (apma.average_assets <> 0
                    AND apma.average_assets IS NOT NULL)
                THEN TO_CHAR(ROUND(apma.FEE_BALANCE / apma.average_assets * 100,6),'FM9990.999999')
                ELSE ' '
            END AS EXPOST ,
            CASE
                WHEN (apma.FEE_BALANCE IS NOT NULL
                    AND apma.FEE_BALANCE <> 0)
                AND apma.IDENTIFIANT_CUMUL IN ('CHG_INI',
                                               'CHG_OTH')
                AND (apma.average_assets <> 0
                    AND apma.average_assets IS NOT NULL)
                THEN TO_CHAR(ROUND(apma.FEE_BALANCE / apma.average_assets * 100,6),'FM9990.999999')
                ELSE ' '
            END                                 AS EXANTE ,
            NVL(apma.IDENTIFIANT_CUMUL,' ')     AS FINAL_IDENTIFIER ,
            NVL(apma.libelle_cumul,' ')         AS FINAL_IDENTIFIER_NAME ,
            NVL(apma.BALISE_FIXFEE,' ')         AS INTERMEDIARY_IDENTIFIER ,
            NVL(apma.libelle_balise_fixfee,' ') AS INTER_IDENTIFIER_NAME ,
            NVL(apma.niveau_calcul,' ')         AS CALCULATION_LEVEL
        FROM
            aa_poste_montant_fixfee apma
        WHERE
            FEE_BALANCE <>0
        ORDER BY
            subfund_code,
            shc_code,
            final_identifier
    )
--select * from  tableau_detail_fixfee_1;
    ,
    /* MOA - Filtre fonctionnel final.
       Les cumuls ex-post EMT ne sont restitues qu'en calcul non estime.
       Les cumuls ex-ante CHG restent restitues independamment de CALCUL_ESTIME. */
    tableau_detail_fixfee AS
    (
        SELECT
            *
        FROM
            tableau_detail_fixfee_1
        WHERE
            TRIM(FINAL_IDENTIFIER) IN ('EMT_OTH',
                                 'EMT_INI')
        AND CALCUL_ESTIME ='NO'
        OR  TRIM(FINAL_IDENTIFIER) IN ('CHG_OTH',
                                 'CHG_INI')
    )
--select * from   tableau_detail_fixfee ;
    ,
    /* MOA - Controle de coherence global/detail.
       La somme analytique conserve chaque ligne de poste tout en calculant la somme
       des details de la balise. Pour NEG_INT et SUB_FEES, si l'auto-controle est actif,
       un ecart > 0,1 entre montant global et somme des details est signale. */
    tableau_detail_fixfee_controle AS
    (
        SELECT
            tdf.SUBFUND_CODE,
            tdf.SHC_CODE,
            tdf.SHC_ISIN,
            tdf.REPORTING_DATE,
            tdf.date_ouverture_exercice,
            tdf.date_cloture_exercice,
            tdf.CALCUL_ESTIME,
            tdf.auto_controle,
            tdf.FEE_CODE,
            tdf.FEE_NAME,
            tdf.AVERAGE_ASSETS,
            tdf.FEE_BALANCE,
            tdf.SUBFUND_CURRENCY,
            tdf.EXPOST,
            tdf.EXANTE,
            tdf.FINAL_IDENTIFIER ,
            tdf.FINAL_IDENTIFIER_NAME,
            tdf.INTERMEDIARY_IDENTIFIER,
            CASE WHEN
            TRIM(tdf.INTER_IDENTIFIER_NAME) ='b)  Other external expenses'
            THEN 'Autres charges courantes'
            ELSE
                tdf.INTER_IDENTIFIER_NAME
             END AS INTER_IDENTIFIER_NAME,  
            tdf.CALCULATION_LEVEL,
            tdf.MONTANT_BALISE_CUMUL,
            SUM(tdf.FEE_BALANCE) OVER (
                PARTITION BY
                    tdf.SUBFUND_CODE,
                    tdf.SHC_CODE,
                    tdf.FINAL_IDENTIFIER,
                    tdf.INTERMEDIARY_IDENTIFIER,
                    tdf.MONTANT_BALISE_CUMUL,
                    tdf.auto_controle
            ) AS SUM_FEE_BALANCE,
            CASE
                WHEN tdf.AUTO_CONTROLE='YES'
                AND TRIM(tdf.INTERMEDIARY_IDENTIFIER) IN ('NEG_INT',
                                                          'SUB_FEES')
                AND tdf.MONTANT_BALISE_CUMUL !=0
                AND ABS(
                    ABS(tdf.MONTANT_BALISE_CUMUL)
                    - ABS(SUM(tdf.FEE_BALANCE) OVER (
                        PARTITION BY
                            tdf.SUBFUND_CODE,
                            tdf.SHC_CODE,
                            tdf.FINAL_IDENTIFIER,
                            tdf.INTERMEDIARY_IDENTIFIER,
                            tdf.MONTANT_BALISE_CUMUL,
                            tdf.auto_controle
                    ))
                ) > 0.1
                THEN 'ERR:MONTANT GLOBAL DIFFERENT SOMME DETAILS'
                ELSE ''
            END AS LOG_INFO
        FROM
            tableau_detail_fixfee tdf
    )
--select * from   tableau_detail_fixfee_controle ;
,
    /* MOA - Controle bloquant de la restitution.
       S'il existe au moins une anomalie LOG_INFO, aucune donnee metier n'est
       restituee. Une seule ligne d'erreur est emise dans le format attendu. */
    anomalies_autocontrole AS
    (
        SELECT COUNT(*) AS nb_anomalies
        FROM tableau_detail_fixfee_controle
        WHERE LOG_INFO IS NOT NULL
          AND TRIM(LOG_INFO) <> ''
    )
SELECT
    tdf.SUBFUND_CODE,
    tdf.SHC_CODE,
    tdf.SHC_ISIN,
    tdf.REPORTING_DATE,
    tdf.FEE_CODE,
    tdf.FEE_NAME,
    tdf.AVERAGE_ASSETS,
    tdf.FEE_BALANCE,
    tdf.SUBFUND_CURRENCY,
    tdf.EXPOST,
    tdf.EXANTE,
    tdf.FINAL_IDENTIFIER,
    tdf.FINAL_IDENTIFIER_NAME,
    tdf.INTERMEDIARY_IDENTIFIER,
    REGEXP_REPLACE(tdf.INTER_IDENTIFIER_NAME,'^\\-','') AS INTER_IDENTIFIER_NAME,
    tdf.CALCULATION_LEVEL
FROM tableau_detail_fixfee_controle tdf
CROSS JOIN anomalies_autocontrole ac
WHERE ac.nb_anomalies = 0

UNION ALL

SELECT
    'ERROR'                                       AS SUBFUND_CODE,
    ' '                                           AS SHC_CODE,
    ' '                                           AS SHC_ISIN,
    arrete.date_arrete                            AS REPORTING_DATE,
    ' '                                           AS FEE_CODE,
    'AUTOCONTROLE KO - VERIFIER LES INCOHERENCES' AS FEE_NAME,
    0                                             AS AVERAGE_ASSETS,
    0                                             AS FEE_BALANCE,
    ' '                                           AS SUBFUND_CURRENCY,
    ' '                                           AS EXPOST,
    ' '                                           AS EXANTE,
    'ERROR'                                       AS FINAL_IDENTIFIER,
    'RESTITUTION BLOQUEE'                         AS FINAL_IDENTIFIER_NAME,
    'AUTOCONTROLE'                                AS INTERMEDIARY_IDENTIFIER,
    'MONTANT GLOBAL DIFFERENT SOMME DETAILS'      AS INTER_IDENTIFIER_NAME,
    ' '                                           AS CALCULATION_LEVEL
FROM arrete
CROSS JOIN anomalies_autocontrole ac
WHERE ac.nb_anomalies > 0;
