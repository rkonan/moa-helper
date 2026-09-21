WITH

auto_controle AS
(
    SELECT
        'YES' AS auto_controle,
        'PRIIPS' AS type_reporting
    FROM dual
),

arrete AS -- date arrete
(
    SELECT
        '30/11/2025' AS date_arrete,
        'PRIIPS' AS type_reporting
    FROM dual
),

portefeuilles AS -- ensemble de portefeuilles à traiter
(
    SELECT *
    FROM
    (
        SELECT
            CODE_PORTEFEUILLE,
            CASE
                WHEN lmf.resultat_condition_fille IS NULL
                    THEN 'NO'
                ELSE 'YES'
            END AS a_date
        FROM descriptif_port_reporting dpr

        LEFT JOIN condition_complexe lmf
            -- pas forcement necessaire de recuperer le parametrage
            -- a date a ce niveau. On peut simplement travailler sur les tables details DP
            -- ou PP
            ON lmf.code_besoin = 'INV'
            AND lmf.nature_condition = 'SDGPTF'
            AND lmf.nature_condition_fille = 'SOCCGES'
            AND dpr.societe_gestion = lmf.resultat_condition_fille

        WHERE code_portefeuille IN ('053380')
        -- AND -- ,'059811','070057','073832','870040','870141','051292')
        AND societe_gestion IN
        (
            'SGS6',
            'SG07',
            'SG34',
            'SG73',
            'SG87',
            'SG435',
            'SG166',
            'SG435',
            'SG59',
            'SG613'
        )
    )
    -- WHERE CODE_PORTEFEUILLE = 'ESE17'
    -- WHERE CODE_PORTEFEUILLE IN ('306','050036')
),

parametrage_cumul_1 AS
-- On recupere le parametrage des balises
-- (CHG_INT, CHG_OTH, ENT_OTH, ENT_INT)
(
    SELECT
        cr.*,
        pcc.*,
        'PRIIPS' AS type_reporting_cr
    FROM cumul_reporting cr

    LEFT JOIN parametre_champ_condition pcc
        ON cr.identifiant_cumul = pcc.critere_saisie_3

    WHERE
        (
            (
                pcc.valeur_champ_ref IN ('OTHMOV', 'INIMOV')
                AND pcc.code_gestion = 'N'
            )
            OR
            (
                pcc.valeur_champ_ref IN ('INIMOR', 'OTPA')
                AND pcc.code_gestion = 'O'
            )
        )
        AND pcc.code_traitement = 'FCEL'
        AND cr.code_tableau = 'PRFEE3'
        AND cr.identifiant_cumul IN
        (
            'CHG_INT',
            'CHG_OTH',
            'ENT_OTH',
            'ENT_INT'
        )
),

-- select * from parametrage_cumul_1;

parametrage_cumul AS
-- on recupere pour chaque portefeuille ...
(
    SELECT
        pc1.*,
        gt1.type_reporting AS type_calcul,
        gt1.code_tableau AS level_fee_df,
        gt2.code_tableau AS level_fee_pf,
        gt3.code_tableau AS level_fee_dp_shc,
        gt4.code_tableau AS level_fee_pp_shc,
        SUBSTR(gt.code_tableau, 9, 2) AS code_part,
        gt.code_portefeuille,
        gt.date_arrete,
        ptf.a_date,
        CASE
            WHEN auto_controle.auto_controle IS NULL
                THEN 'NO'
            ELSE auto_controle.auto_controle
        END AS auto_controle

    FROM parametrage_cumul_1 pc1

    LEFT JOIN gestion_tableau gt
        ON gt.type_reporting = pc1.type_reporting_cr
        AND gt.type_reporting = 'PRIIPS'

    JOIN portefeuilles ptf
        ON gt.code_portefeuille = ptf.code_portefeuille

    JOIN arrete
        ON gt.date_arrete = arrete.date_arrete
        AND gt.type_reporting = arrete.type_reporting

    LEFT JOIN auto_controle
        ON auto_controle.auto_controle = 'YES'
        AND gt.type_reporting = auto_controle.type_reporting

    LEFT JOIN gestion_tableau gt1
        ON gt1.type_reporting = 'FIXFEE'
        AND gt1.date_arrete = arrete.date_arrete
        AND gt.code_portefeuille = gt1.code_portefeuille
        AND SUBSTR(gt1.code_tableau, 1, 6) = 'FEE-DP'

    LEFT JOIN gestion_tableau gt2
        ON gt2.type_reporting = 'FIXFEE'
        AND gt2.date_arrete = arrete.date_arrete
        AND gt.code_portefeuille = gt2.code_portefeuille
        AND SUBSTR(gt2.code_tableau, 1, 6) = 'FEE-PF'

    LEFT JOIN gestion_tableau gt3
        ON gt3.type_reporting = 'FIXFEE'
        AND gt3.date_arrete = arrete.date_arrete
        AND gt.code_portefeuille = gt3.code_portefeuille
        AND SUBSTR(gt3.code_tableau, 1, 6) = 'FEE-DP'
        AND SUBSTR(gt.code_tableau, 9, 2)
            = SUBSTR(gt3.code_tableau, 8, 2)

    LEFT JOIN gestion_tableau gt4
        ON gt4.type_reporting = 'FIXFEE'
        AND gt4.date_arrete = arrete.date_arrete
        AND gt.code_portefeuille = gt4.code_portefeuille
        AND SUBSTR(gt4.code_tableau, 1, 6) = 'FEE-PP'
        AND SUBSTR(gt.code_tableau, 9, 2)
            = SUBSTR(gt4.code_tableau, 8, 2)
),

-- select * from parametrage_cumul;

parametrage_majcel_1 AS
(
    SELECT
        pcc.code_traitement AS code_traitement,
        pcc.code_ensemble_val AS code_ensemble_val_1,
        pcc.categorie_valeur AS PRIMITIVE,
        pcc.critere_saisie_1 AS code_tableau_1,

        CASE
            WHEN pcc.critere_saisie_1 = 'FEE-PF'
                 AND pcc.critere_saisie_2 = 'SWING_COST'
                THEN pc.level_fee_pf

            WHEN pcc.critere_saisie_1 IN ('FEEDP*', 'FEEDP *')
                THEN pc.level_fee_dp_shc

            WHEN pcc.critere_saisie_1 IN ('FEEPP*', 'FEEPP *')
                THEN pc.level_fee_pp_shc

            ELSE pcc.critere_saisie_1
        END AS choix_code_tableau,

        pcc.critere_saisie_2 AS balise_fixfee,

        CASE
            WHEN TRIM(db.libelle_balise) IS NULL
                THEN TRIM(db2.libelle_balise)
            ELSE TRIM(db.libelle_balise)
        END AS libelle_balise_fixfee,

        pcc.critere_saisie_3 AS choix_colonne_ct_fixfee,

        CASE
            WHEN pcc.critere_saisie_1 = 'FEE-PF'
                 AND pcc.critere_saisie_2 = 'SWING_COST'
                THEN ct2.numero_ligne

            WHEN pcc.critere_saisie_1 = 'FEE-DF'
                THEN ct.numero_ligne

            WHEN pcc.critere_saisie_1 = 'FEE-PF'
                THEN ct2.numero_ligne

            WHEN pcc.critere_saisie_1 IN ('FEEDP*', 'FEEDP *')
                THEN ct3.numero_ligne

            WHEN pcc.critere_saisie_1 IN ('FEEPP*', 'FEEPP *')
                THEN ct4.numero_ligne
        END AS numero_ligne_ct,

        CASE
            WHEN pcc.critere_saisie_1 = 'FEE-PF'
                 AND pcc.critere_saisie_2 = 'SWING_COST'
                THEN ct2.code_tableau_detail

            WHEN pcc.critere_saisie_1 = 'FEE-DF'
                THEN ct.code_tableau_detail

            WHEN pcc.critere_saisie_1 = 'FEE-PF'
                THEN ct2.code_tableau_detail

            WHEN pcc.critere_saisie_1 IN ('FEEDP*', 'FEEDP *')
                THEN ct3.code_tableau_detail

            WHEN pcc.critere_saisie_1 IN ('FEEPP*', 'FEEPP *')
                THEN ct4.code_tableau_detail

            ELSE 'NA'
        END AS code_tableau_detail,

        pc.*

    FROM parametre_champ_condition pcc

    JOIN parametrage_cumul pc
        ON TRIM(pcc.categorie_valeur) = TRIM(pc.VALEUR_PAR_DEFAUT)
        AND pcc.code_traitement='MAJCEL'
        AND pcc.CODE_ENSEMBLE_VAL='FIXFEE'
        AND pcc.critere_saisie_2 in ('MGTF_EXA',
                                     'DISF_EXA',
                                     'DISF_EXP',
                                     'NEG_INT', -- à complèter
                                      'MGTF_EXP')

    LEFT JOIN descriptif_balise db
        ON pcc.critere_saisie_2 = db.code_balise

    LEFT JOIN tra_descriptif_balise db2
        ON db.code_balise = db2.code_balise
        AND db2.langue_traduction = 'FRA'

    LEFT JOIN contenu_tableau ct
        ON ct.type_reporting = pc.type_calcul
        AND ct.numero_colonne = 1
        AND ct.date_arrete = pc.date_arrete
        AND ct.code_portefeuille = pc.code_portefeuille
        AND pc.level_fee_df = ct.code_tableau
        AND pcc.critere_saisie_2 = ct.contenu_cellule

    LEFT JOIN contenu_tableau ct2
        ON ct2.type_reporting = pc.type_calcul
        AND ct2.numero_colonne = 1
        AND pc.date_arrete = ct2.date_arrete
        AND pc.code_portefeuille = ct2.code_portefeuille
        AND pc.level_fee_pf = ct2.code_tableau
        AND pcc.critere_saisie_2 = ct2.contenu_cellule

    LEFT JOIN contenu_tableau ct3
        ON ct3.type_reporting = pc.type_calcul
        AND ct3.numero_colonne = 1
        AND pc.date_arrete = ct3.date_arrete
        AND pc.code_portefeuille = ct3.code_portefeuille
        AND pc.level_fee_dp_shc = ct3.code_tableau
        AND pcc.critere_saisie_2 = ct3.contenu_cellule

    LEFT JOIN contenu_tableau ct4
        ON ct4.type_reporting = pc.type_calcul
        AND ct4.numero_colonne = 1
        AND pc.date_arrete = ct4.date_arrete
        AND pc.code_portefeuille = ct4.code_portefeuille
        AND pc.level_fee_pp_shc = ct4.code_tableau
        AND pcc.critere_saisie_2 = ct4.contenu_cellule
),

-- select * from parametrage_majcel_1;

parametrage_majcel AS
(
    SELECT
        pe.*,
        NVL(CODE_VALEUR_MANANG, CODE_DEVISE_PORTEFEUILLE),
        CASE
            WHEN TRIM(pe.code_tableau_detail) = 'DET-FEEDF'
                THEN 'Fee Data on Period End - By Portfolio'

            WHEN TRIM(pe.code_tableau_detail) = 'DET-FEEPF'
                THEN 'Fee Data on Period End - By Shareclass'

            WHEN TRIM(pe.code_tableau_detail) IN
                 ('DET-FEEPP', 'DET-FEEPP')
                THEN 'Fee Data on Period - By Shareclass'

            ELSE TRIM(dt.libelle_tableau)
        END AS niveau_calcul,

        CASE
            WHEN EXTRACT(MONTH FROM TO_DATE(pe.date_arrete)) = EXTRACT(MONTH FROM dcp.date_cloture_exercice )
            THEN 'YES'
            ELSE 'NO'
        END AS CALCUL_ESTIME,

        dcp.date_cloture_exercice,
        dcp.date_ouverture_exercice

    FROM parametrage_majcel_1 pe

    LEFT JOIN descriptif_tableau dt
        ON pe.code_tableau_detail = dt.code_tableau

    LEFT JOIN descriptif_part dpa
        ON pe.code_portefeuille = dpa.code_portefeuille
        AND TRIM(pe.code_part) = TRIM(dpa.code_part)

    LEFT JOIN descriptif_portefeuille dp
        ON pe.code_portefeuille = dp.code_portefeuille

    LEFT JOIN descriptif_comptabilite dcp
        ON pe.code_portefeuille = dcp.code_comptabilite
),

-- select * from parametrage_majcel;


    all_balises_fixfee AS -- on recupere pour chaque balise le detail des ...
(
    SELECT
        pe.*,

        CASE
            WHEN TRIM(pe.BALISE_FIXFEE) IN ('TF_AFEES_8', 'TF_AFEES_0')
                THEN 'COUTS_INDUITS'
            WHEN TRIM(pe.BALISE_FIXFEE) = 'SWING_COST'
                THEN 'SWING_COST'
            WHEN dp2.code_valeur IS NOT NULL
                THEN dp2.code_valeur
            ELSE dp.code_valeur
        END AS code_poste,

        CASE
            WHEN TRIM(pe.BALISE_FIXFEE) IN ('TF_AFEES_8', 'TF_AFEES_0')
                THEN 'COUTS_INDUITS'
            WHEN TRIM(pe.BALISE_FIXFEE) = 'SWING_COST'
                THEN 'SWING_COST'
            WHEN dp2.code_valeur IS NOT NULL
                THEN TRIM(dp2.lib_poste)
            ELSE TRIM(dp.lib_poste)
        END AS lib_poste,

        CASE
            WHEN ct.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            ct.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ct.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )
            WHEN ct.contenu_cellule IS NULL
                THEN 0
            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(ct.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS montant_balise_cumul,

        -- montant au niveau de la table contenu_tableau
        -- agit du cumul sur la sous balise.
        -- Ce montant devrait correspondre à la somme des
        -- montants des tableaux détaillés

        CASE
            WHEN pe.balise_fixfee = 'SWING_COST'
             AND ct.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            ct.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ct.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )

            WHEN pe.balise_fixfee = 'SWING_COST'
             AND ct.forcage_cellule = ' '
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ct.contenu_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )

            WHEN dp2.code_valeur IS NOT NULL
             AND ct.contenu_cellule IS NULL
                THEN 0

            WHEN TRIM(pe.CODE_TABLEAU_DETAIL) = 'DET-FEEDP'
                 -- pour le cas a date il faut
                 -- recuperer le CHG_OTH/MGTF_EXA dans le tableau DET-FEEDP
             AND TRIM(pe.IDENTIFIANT_CUMUL) = 'CHG_OTH'
             AND TRIM(pe.BALISE_FIXFEE) = 'MGTF_EXA'
             AND dp2.code_valeur IS NOT NULL
             AND ct.contenu_cellule IS NOT NULL
             AND ctd3.contenu_cellule IS NOT NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ctd3.contenu_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )

            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(ctd2.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS montant_poste,

        CASE
            WHEN cta36.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            cta36.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(cta36.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )
            WHEN cta36.contenu_cellule IS NULL
                THEN 0
            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(cta36.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS fixfee_average_m36,

        CASE
            WHEN cta12.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            cta12.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(cta12.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )
            WHEN cta12.contenu_cellule IS NULL
                THEN 0
            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(cta12.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS fixfee_average_m12,

        -- Average niveau part

        CASE
            WHEN ctap60.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            ctap60.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ctap60.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )
            WHEN ctap60.contenu_cellule IS NULL
                THEN 0
            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(ctap60.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS fixfee_average_shc_m60,

        CASE
            WHEN ctap36.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            ctap36.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ctap36.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )
            WHEN ctap36.contenu_cellule IS NULL
                THEN 0
            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(ctap36.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS fixfee_average_shc_m36,

        CASE
            WHEN ctap12.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            ctap12.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ctap12.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )
            WHEN ctap12.contenu_cellule IS NULL
                THEN 0
            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(ctap12.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS fixfee_average_shc_m12,

        CASE
            WHEN ctap1.forcage_cellule != ' '
             AND LENGTH(
                    TRIM(
                        TRANSLATE(
                            ctap1.forcage_cellule,
                            '+-.,1234567890',
                            ' '
                        )
                    )
                 ) IS NULL
                THEN TO_NUMBER(
                    REPLACE(
                        REPLACE(TRIM(ctap1.forcage_cellule), ' ', NULL),
                        ',',
                        '.'
                    )
                )
            WHEN ctap1.contenu_cellule IS NULL
                THEN 0
            ELSE TO_NUMBER(
                REPLACE(
                    REPLACE(TRIM(ctap1.contenu_cellule), ' ', NULL),
                    ',',
                    '.'
                )
            )
        END AS fixfee_last_shc

    FROM parametrage_majcel pe

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

    LEFT JOIN
        contenu_tableau_detail ctd
        ON  pe.type_calcul = ctd.type_reporting
        AND pe.date_arrete = ctd.date_arrete
        AND pe.code_portefeuille = ctd.code_portefeuille
        AND pe.code_tableau_detail = ctd.code_tableau_detail
        AND jt.numero_ligne_detail = ctd.numero_ligne_detail
        AND ctd.numero_colonne_detail = 2

        -- Pour FEE-PP, FEE-PF
    LEFT JOIN
        contenu_tableau_detail ctd2
    ON
            pe.type_calcul = ctd2.type_reporting
        AND pe.date_arrete = ctd2.date_arrete
        AND pe.code_portefeuille = ctd2.code_portefeuille
        AND pe.code_tableau_detail = ctd2.code_tableau_detail
        AND pe.numero_ligne_detail = ctd2.numero_ligne_detail
        AND ctd2.numero_colonne_detail = ct.numero_colonne + 6
        --- dans les tableaux details FEEPP et
        -- FEE-DP

    LEFT JOIN
        contenu_tableau_detail ctd3
    ON
            pe.type_calcul = ctd3.type_reporting
        AND pe.date_arrete = ctd3.date_arrete
        AND pe.code_portefeuille = ctd3.code_portefeuille
        AND pe.code_tableau_detail = ctd3.code_tableau_detail
        AND jt.numero_ligne_detail = ctd3.numero_ligne_detail
        AND ctd3.numero_colonne_detail = ct.numero_colonne + 3

        -- montant est sur a colonne du contenu_tableau +3
        -- dans les tableaux details FEEDP le
        -- poste la recuperation du code poste est critique.
        -- la colonne code poste devrait
        -- être non null

    LEFT JOIN
        descriptif_poste dp
    ON
        --trim(SUBSTR(ctd.contenu_cellule,12,32)) = trim(dp.code_valeur)
        trim(REGEXP_SUBSTR(ctd.contenu_cellule, '\S\w+\S')) = trim(dp.code_valeur)

    LEFT JOIN
        descriptif_poste dp2
    ON
        trim(REGEXP_SUBSTR(ctd.contenu_cellule, '\S\w+\S')) = trim(dp2.code_valeur)
        -- le code valeur est le premier groupe de caracteres delimite par des espaces
        AND trim(SUBSTR(ctd.contenu_cellule,1,4)) = trim(dp2.categorie_valeur)

    LEFT JOIN
        descriptif_tableau dt
    ON
        pe.choix_code_tableau = dt.code_tableau

        --- averrage assets

    LEFT JOIN
        contenu_tableau cta36
        --- average asset niveau fond sur 36 mois annualise
    ON
            cta36.numero_colonne = 5
        AND cta36.numero_ligne = 2
        AND cta36.date_arrete = pe.date_arrete
        AND pe.code_portefeuille = cta36.code_portefeuille
        AND cta36.type_reporting = pe.type_calcul
        AND cta36.code_tableau = pe.level_fee_pf

    LEFT JOIN
        contenu_tableau cta12
        --- average asset niveau fond sur 12 mois annualise
    ON
            cta12.type_reporting = 'FIXFEE'
        AND cta12.numero_colonne = 4
        AND cta12.numero_ligne = 2
        AND cta12.date_arrete = pe.date_arrete
        AND pe.code_portefeuille = cta12.code_portefeuille
        AND cta12.type_reporting = pe.type_calcul
        AND cta12.code_tableau = pe.level_fee_pf

        --Compartiment
        --Part

    LEFT JOIN
        contenu_tableau ctap60
        --- average asset niveau part sur 60 mois annualise
    ON
            ctap60.numero_colonne = 6
        AND ctap60.numero_ligne = 2
        AND ctap60.date_arrete = pe.date_arrete
        AND pe.code_portefeuille = ctap60.code_portefeuille
        AND ctap60.type_reporting = pe.type_calcul
        AND ctap60.code_tableau = pe.level_fee_pp_shc

    LEFT JOIN
        contenu_tableau ctap36
        --- average asset niveau part sur 36 mois annualise
    ON
            ctap36.numero_colonne = 5
        AND ctap36.numero_ligne = 2
        AND ctap36.date_arrete = pe.date_arrete
        AND pe.code_portefeuille = ctap36.code_portefeuille
        AND ctap36.type_reporting = pe.type_calcul
        AND ctap36.code_tableau = pe.level_fee_pp_shc

    LEFT JOIN
        contenu_tableau ctap12
        --- average asset niveau part sur 12 mois annualise
    ON
            ctap12.numero_colonne = 4
        AND ctap12.numero_ligne = 2
        AND ctap12.date_arrete = pe.date_arrete
        AND pe.code_portefeuille = ctap12.code_portefeuille
        AND ctap12.type_reporting = pe.type_calcul
        AND ctap12.code_tableau = pe.level_fee_pp_shc

        --- Last Management Fees Base

    LEFT JOIN
        contenu_tableau ctap1
        --- average asset parametrage a date ou encore Last Management
        -- Fees Base
    ON
            ctap1.numero_colonne = 2
        AND ctap1.numero_ligne = 7
        AND ctap1.date_arrete = pe.date_arrete
        AND pe.code_portefeuille = ctap1.code_portefeuille
        AND ctap1.type_reporting = pe.type_calcul
        AND ctap1.code_tableau = pe.level_fee_dp_shc
)
,

all_balises_fixfee_with_average_asset AS
(
    SELECT
        apm.CODE_PORTEFEUILLE,
        apm.CODE_PART,
        apm.CODE_VALEUR_MAJVAC,
        apm.DATE_ARRETE,
        apm.CODE_POSTE,
        apm.lib_poste,
        apm.DEVISE_PORTEFEUILLE,
        apm.IDENTIFIANT_CUMUL,
        apm.libelle_cumul,
        apm.BALISE_FIXFEE,
        apm.libelle_balise_fixfee,
        apm.niveau_calcul,
        apm.montant_poste,
        apm.MONTANT_BALISE_CUMUL,
        apm.CALCUL_ESTIME,
        apm.auto_controle,
        apm.date_cloture_exercice,
        apm.date_ouverture_exercice,
        CASE
            WHEN trim(apm.code_tableau_detail) = 'DET-FEEDP'
                THEN apm.fixfee_last_shc

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPF'
                AND apm.identifiant_cumul = 'CHG_INI'
                THEN apm.fixfee_average_m36

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPF'
                AND apm.identifiant_cumul = 'CHG_OTH'
                THEN apm.fixfee_average_m12

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPF'
                AND apm.identifiant_cumul = 'EMT_OTH'
                THEN apm.fixfee_average_m12

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPF'
                AND apm.identifiant_cumul = 'EMT_INI'
                THEN apm.fixfee_average_m12

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPP'
                AND apm.identifiant_cumul = 'CHG_INI'
                THEN apm.fixfee_average_shc_m36

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPP'
                AND apm.identifiant_cumul = 'CHG_OTH'
                THEN apm.fixfee_average_shc_m12

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPP'
                AND apm.identifiant_cumul = 'EMT_OTH'
                THEN apm.fixfee_average_shc_m12

            WHEN trim(apm.code_tableau_detail) = 'DET-FEEPP'
                AND apm.identifiant_cumul = 'EMT_INI'
                THEN apm.fixfee_average_shc_m12

            ELSE 0
        END AS average_assets
    FROM
        all_balises_fixfee apm
)
,
aa_poste_montant_fixfee AS
(
    SELECT
        apm.CODE_PORTEFEUILLE,
        apm.CODE_PART,
        apm.CODE_VALEUR_MAJVAC,
        apm.DATE_ARRETE,
        apm.CODE_POSTE,
        apm.lib_poste,
        apm.DEVISE_PORTEFEUILLE,
        apm.IDENTIFIANT_CUMUL,
        apm.libelle_cumul,
        apm.BALISE_FIXFEE,
        apm.libelle_balise_fixfee,
        apm.niveau_calcul,
        apm.average_assets,
        apm.MONTANT_BALISE_CUMUL,
        apm.CALCUL_ESTIME,
        apm.auto_controle,
        apm.date_cloture_exercice,
        apm.date_ouverture_exercice,
        CASE
            WHEN SUM(apm.montant_poste) IS NULL
                THEN 0
            WHEN apm.BALISE_FIXFEE = 'SUB_FEES'
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
tableau_detail_fixfee_1 AS
(
    SELECT
        -- Ne pas afficher NULL dans le fichier resultat
        apma.CODE_PORTEFEUILLE                    AS SUBFUND_CODE,
        NVL(apma.CODE_PART, ' ')                  AS SHC_CODE,
        NVL(apma.CODE_VALEUR_MAJVAC, ' ')         AS SHC_ISIN,
        apma.DATE_ARRETE                          AS REPORTING_DATE,
        apma.date_cloture_exercice,
        apma.date_ouverture_exercice,
        apma.CALCUL_ESTIME,
        apma.auto_controle,
        MONTANT_BALISE_CUMUL,
        NVL(apma.CODE_POSTE, ' ')                  AS FEE_CODE,
        NVL(apma.lib_poste, ' ')                   AS FEE_NAME,
        apma.average_assets,
        apma.FEE_BALANCE,
        NVL(apma.DEVISE_PORTEFEUILLE, ' ')         AS SUBFUND_CURRENCY,
        CASE
            WHEN (apma.FEE_BALANCE IS NOT NULL
                  AND apma.FEE_BALANCE <> 0)
                 AND apma.IDENTIFIANT_CUMUL IN ('EMT_OTH',
                                                'EMT_INI')
                 -- AND CALCUL_ESTIME = 'NO'
                 AND (apma.average_assets <> 0
                      AND apma.average_assets IS NOT NULL)
            THEN TO_CHAR(
                     ROUND(
                         apma.FEE_BALANCE / apma.average_assets * 100,
                         6
                     ),
                     'FM9990.999999'
                 )
            ELSE ' '
        END AS EXPOST,

        CASE
            WHEN (apma.FEE_BALANCE IS NOT NULL
                  AND apma.FEE_BALANCE <> 0)
                 AND apma.IDENTIFIANT_CUMUL IN ('CHG_INI',
                                                'CHG_OTH')
                 AND (apma.average_assets <> 0
                      AND apma.average_assets IS NOT NULL)
            THEN TO_CHAR(
                     ROUND(
                         apma.FEE_BALANCE / apma.average_assets * 100,
                         6
                     ),
                     'FM9990.999999'
                 )
            ELSE ' '
        END                                      AS EXANTE,

        NVL(apma.IDENTIFIANT_CUMUL, ' ')          AS FINAL_IDENTIFIER,
        NVL(apma.libelle_cumul, ' ')              AS FINAL_IDENTIFIER_NAME,
        NVL(apma.BALISE_FIXFEE, ' ')              AS INTERMEDIARY_IDENTIFIER,
        NVL(apma.libelle_balise_fixfee, ' ')       AS INTER_IDENTIFIER_NAME,
        NVL(apma.niveau_calcul, ' ')               AS CALCULATION_LEVEL

    FROM
        aa_poste_montant_fixfee apma
    WHERE
        FEE_BALANCE <> 0
    ORDER BY
        subfund_code,
        shc_code,
        final_identifier
)
,
tableau_detail_fixfee AS
(
    SELECT
        *
    FROM
        tableau_detail_fixfee_1
    WHERE
        TRIM(FINAL_IDENTIFIER) IN ('EMT_OTH',
                                   'EMT_INI')
        AND CALCUL_ESTIME = 'NO'
        OR TRIM(FINAL_IDENTIFIER) IN ('CHG_OTH',
                                      'CHG_INI')
)
--select * from tableau_detail_fixfee ;
,
group_tab AS
(
    SELECT
        SUBFUND_CODE,
        SHC_CODE,
        FINAL_IDENTIFIER,
        INTERMEDIARY_IDENTIFIER,
        MONTANT_BALISE_CUMUL,
        auto_controle,
        SUM(FEE_BALANCE) AS SUM_FEE_BALANCE
        -- ABS(MONTANT_BALISE_CUMUL) -ABS(SUM(FEE_BALANCE)) as ecart,
        -- 2*ABS(MONTANT_BALISE_CUMUL) -ABS(SUM(FEE_BALANCE)) as ecart_2
    FROM
        tableau_detail_fixfee
    GROUP BY
        SUBFUND_CODE,
        SHC_CODE,
        FINAL_IDENTIFIER,
        INTERMEDIARY_IDENTIFIER,
        MONTANT_BALISE_CUMUL,
        auto_controle
)
--select * from group_tab; --where abs(ecart) >0.1 and montant_balise_cumul !=0 ; --and abs
-- (ecart_2) >0.1 and montant_balise_cumul !=0;
,
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
        tdf.FINAL_IDENTIFIER,
        tdf.FINAL_IDENTIFIER_NAME,
        tdf.INTERMEDIARY_IDENTIFIER,
        tdf.INTER_IDENTIFIER_NAME,
        tdf.CALCULATION_LEVEL,
        tdf.MONTANT_BALISE_CUMUL,
        gtb.SUM_FEE_BALANCE,
        CASE
            WHEN gtb.AUTO_CONTROLE = 'YES'
                AND TRIM(tdf.INTERMEDIARY_IDENTIFIER) IN ('NEG_INT',
                                                          'SUB_FEES')
                AND tdf.MONTANT_BALISE_CUMUL != 0
                AND ABS(
                    ABS(tdf.MONTANT_BALISE_CUMUL)
                    - ABS(gtb.SUM_FEE_BALANCE)
                ) > 0.1
            THEN 'ERR:MONTANT GLOBAL DIFFERENT SOMME DETAILS'
            ELSE ''
        END AS LOG_INFO
    FROM
        tableau_detail_fixfee tdf
    JOIN
        group_tab gtb
    ON
        tdf.SUBFUND_CODE = gtb.SUBFUND_CODE
        AND tdf.SHC_CODE = gtb.SHC_CODE
        AND tdf.FINAL_IDENTIFIER = gtb.FINAL_IDENTIFIER
        AND tdf.INTERMEDIARY_IDENTIFIER = gtb.INTERMEDIARY_IDENTIFIER
)
--select * from tableau_detail_fixfee_controle ;
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
    REGEXP_REPLACE(tdf.INTER_IDENTIFIER_NAME, '^\-', '') AS INTER_IDENTIFIER_NAME,
    tdf.CALCULATION_LEVEL
FROM
    tableau_detail_fixfee_controle tdf;
