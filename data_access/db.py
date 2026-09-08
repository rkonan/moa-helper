import datetime
import gzip
import pickle

import streamlit as st
import pandas as pd
from datetime import date
from functools import lru_cache
import logging
from typing import Dict, Optional
import cx_Oracle
from utils.general_utils import dataclass_to_df
from data_access.db_config import DB_CONFIG
import time
from models.models import ActifReq, ContenuEnsemblePort, ContenuEnsembleVal, DescriptifEnsemblePort, Frais, HistoriqueVl, \
HedgeConfig, LatentHedge, ODFrais, OperationsR, Portefeuille, CompPortefeuille, GestionValo, HistoPass, \
HistoriqueVl, Position, PositionNV, RealiseHedge, RealiseHobi, TableBascule, TransactionLine, CoursTerme, HistoChange, FxForwardDescriptor


# === Logger ===
logger = logging.getLogger("RAGHybrid")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

MOCK_POSITIONS = [
    {
        "id": 1,
        "portfolio": "PE_PORTFOLIO_1",
        "instrument_type": "FX_FORWARD",
        "trade_id": "FXFWD_001",
        "ccy_buy": "USD",
        "ccy_sell": "EUR",
        "notional_buy": 1_000_000,
        "notional_sell": 920_000,
        "trade_date": date(2025, 1, 10),
        "start_date": date(2025, 1, 13),
        "maturity_date": date(2025, 7, 15),
        "gp_price": 0.9200,  # Prix terme GP (exemple)
        "gp_valuation": 10_000.0  # valeur actuelle GP (exemple)
    },
    {
        "id": 2,
        "portfolio": "PE_PORTFOLIO_1",
        "instrument_type": "FX_FORWARD",
        "trade_id": "FXFWD_002",
        "ccy_buy": "EUR",
        "ccy_sell": "USD",
        "notional_buy": 500_000,
        "notional_sell": 545_000,
        "trade_date": date(2025, 2, 1),
        "start_date": date(2025, 2, 3),
        "maturity_date": date(2025, 8, 3),
        "gp_price": 1.0900,
        "gp_valuation": -5_000.0,
    },
]


def row_to_dict(cursor,row):
    cols= [c[0].lower() for c in cursor.description]
    return dict(zip(cols,row))


def get_connection (env):
    logger.info(f"Db env actif {env}")
    cfg=DB_CONFIG[env]
    logger.info(cfg["host"])
    logger.info(cfg["port"])
    logger.info(cfg["service_name"])
    logger.info(cfg["user"])
    logger.info(cfg["password"])
    dsn=cx_Oracle.makedsn(cfg["host"],cfg["port"],cfg["service_name"])
    conn = cx_Oracle.connect(user=cfg["user"],password=cfg["password"],dsn=dsn,encoding="UTF-8")
    logger.info(f"Connexion établie avec la base de données pour l'environnement {env}")
    return conn


@st.cache_data
def get_portfolio_positions(env,code_portefeuille: str, date_valorisation: date) ->list[Position]:
    #date_str=date_valorisation.strftime("%Y-%m-%d")
    logger.info(f"env: {env}")
    logger.info(f"get_portfolio_positions - code_portefeuille: {code_portefeuille}, date_valorisation: {date_valorisation}")

    # sql ="""SELECT * FROM HISTORIQUE_INVENTAIRE WHERE CODE_PORTEFEUILLE= :code AND date_valorisation = :date_valo AND quantite_valo <> 0"""
    #sql ="""SELECT * FROM HISTORIQUE_INVENTAIRE WHERE CODE_PORTEFEUILLE= :code FETCH FIRST 5 ROWS ONLY """
    sql ="""
        SELECT
        hi.DATE_VALORISATION,hi.CODE_PORTEFEUILLE,hi.TYPE_STOCK,hi.CATEGORIE_VALEUR,hi.CODE_VALEUR,hi.STATUT_VALEUR,hi.STATUT_LIGNE,
        hi.CODE_CONTREP_LIGNE,hi.CODE_DEPOSITAIRE,hi.CODE_NON_FONGIBILITE,hi.CODE_LIGNE,hi.DATE_DERNIERE_MODIFICATION,hi.DEVISE_DERNIERE_VALO,
        hi.MONTANT_DERN_VALO,hi.MONTANT_DERN_VALO_DV,hi.QUANTITE_VALO,hi.PRIX_REVIENT_VALO,hi.PRIX_REVIENT_VALO_DV,hi.COUPON_COURU_VALO,
        hi.COUPON_COURU_VALO_DV,hi.COUPON_REVIENT_VALO,hi.COUPON_REVIENT_VALO_DV,hi.VA_REVIENT_VALO,hi.VA_REVIENT_VALO_DV,hi.VA_VALO,
        hi.VA_VALO_DV,hi.COURS_VALO,hi.DATE_COTATION,hi.COUPON_UNITAIRE_VALO,hi.NOMBRE_JOURS_INTERETS,hi.INDICATEUR_FORCAGE,
        hi.QUANTITE_ENTREE,hi.QUANTITE_SORTIE,hi.TRESORERIE_ENTREE,hi.TRESORERIE_SORTIE,hi.VIE_MOYENNE,hi.TAUX_RENDEMENT,
        hi.SENSIBILITE_TOT,hi.DURATION,hi.CONVEXITE,hi.PROBABILITE_EXERCICE,hi.CODE_GERANT,hi.INDICATEUR_FORCAGE_COUPON,
        hi.DEVISE_EXPRESSION_COURS,hi.DEVISE_EXPRESSION_MONTANT,hi.CODE_SERVEUR,hi.TAUX_ACTUEL,hi.TAUX_SIMPLE_PREMIER,
        hi.TAUX_SIMPLE_FINAL,hi.VOLATILITE,hi.CODE_GROUPE,hi.NOMBRE_JOURS_ECHEANCE,hi.DATE_PROCHAIN_COUPON,hi.COURS_DP_EN_DG,
        hi.TAUX_INTERET,hi.COEFF_INDEXATION,hi.PLACE_COTATION,hi.CODE_COURBE_TAUX,hi.SPREAD_COURBE_TAUX,hi.RAISON_FORCAGE,
        hi.DATE_DEBUT_FORCAGE,hi.DATE_FIN_FORCAGE,hi.MONTANT_GAIN,hi.ID_USERNAME,hi.DATE_MAJ_VL,hi.HEURE_MAJ_VL,
        hi.DATE_COURS_DEMANDE,hi.DATE_INTERETS_DEMANDE,hi.DATE_CHANGE_DEMANDE,hi.CODE_FIXING_DEMANDE,hi.PNET_REVIENT_VALO,
        hi.PNET_REVIENT_VALO_DV,hi.PNET_VALO,hi.PNET_VALO_DV,hi.PRU_VALO,hi.EXPRESSION_COURS,hi.CRITERE_NON_FONGIBILITE,hi.CODE_HEDGING,
        hi.CODE_CONTREPARTIE,hi.CODE_INTERM_NEGOCE_1,hi.CODE_INTERM_NEGOCE_2,hi.STRATEGIE_TRANSACTION,hi.NOTRE_DEPOT,
        CASE WHEN CATEGORIE_VALEUR = 'VMOB' THEN ett.CODE_TABLE_REF_RESUL
        ELSE CATEGORIE_VALEUR END AS CLASSE_ACTIF
        FROM
        historique_inventaire hi left join descriptif_valeur dv on hi.code_valeur= dv.code_valeur
        left join ensemble_table ett on ett.CODE_DETAIL =dv.TYPE_VALEUR
        and ett.CODE_TABLE='TYPVAL'
        WHERE
            code_portefeuille=:code
            AND DATE_VALORISATION=:date_valo
            AND quantite_valo <>0
            AND TYPE_STOCK='AD1'
    """
    conn=get_connection(env)
    cur =conn.cursor()
    logger.debug(sql)
    logger.debug(code_portefeuille)
    logger.debug(date_valorisation)
    cur.execute(sql,{"code":code_portefeuille,"date_valo":date_valorisation})
    rows=cur.fetchall()

    logger.info(f"Number of rows returned: {len(rows)}")
    positions =[Position(**row_to_dict(cur,row)) for row in rows]

    cur.close()
    conn.close()
    return positions




@st.cache_data
def get_portfolio_positions_no_valo(env,code_portefeuille: str, type_stock: str="AD1") ->pd.DataFrame:
    #date_str=date_valorisation.strftime("%Y-%m-%d")


    # sql ="""SELECT * FROM HISTORIQUE_INVENTAIRE WHERE CODE_PORTEFEUILLE= :code AND date_valorisation = :date_valo AND quantite_valo <>0"""
    #sql ="""SELECT * FROM HISTORIQUE_INVENTAIRE WHERE CODE_PORTEFEUILLE= :code FETCH FIRST 5 ROWS ONLY """
    sql ="""
        SELECT
        sp.CODE_PORTEFEUILLE,sp.TYPE_STOCK,sp.CATEGORIE_VALEUR,sp.CODE_VALEUR,sp.STATUT_VALEUR,sp.STATUT_LIGNE,sp.CODE_CONTREP_LIGNE,
        sp.CODE_DEPOSITAIRE,sp.CODE_NON_FONGIBILITE,sp.CODE_LIGNE,sp.CODE_GERANT,sp.PRIX_REVIENT_A_SOLDER_DV,sp.PRIX_REVIENT_A_SOLDER,
        sp.QUANTITE_A_SOLDER,sp.COUPON_REVIENT_A_SOLDER,sp.COUPON_REVIENT_A_SOLDER_DV,sp.VA_REVIENT_A_SOLDER,sp.VA_REVIENT_A_SOLDER_DV,
        sp.DATE_DERNIERE_MODIFICATION,sp.DEVISE_DERNIERE_VALO,sp.MONTANT_DERN_VALO,sp.MONTANT_DERN_VALO_DV,sp.QUANTITE_VALO,
        sp.PRIX_REVIENT_VALO,sp.PRIX_REVIENT_VALO_DV,sp.COUPON_REVIENT_VALO,sp.COUPON_REVIENT_VALO_DV,sp.VA_REVIENT_VALO,
        sp.VA_REVIENT_VALO_DV,sp.COUPON_COURU_VALO,sp.COUPON_COURU_VALO_DV,sp.VA_VALO,sp.VA_VALO_DV,sp.DEVISE_A_DERNIERE_VALO,
        sp.MONTANT_A_DERN_VALO,sp.QUANTITE_A_DERN_VALO,sp.PRIX_REV_A_DERN_VALO,sp.PRIX_REV_A_DERN_VALO_DV,sp.CP_COURU_A_DERN_VALO,
        sp.PNET_REVIENT_A_SOLDER,sp.PNET_REVIENT_A_SOLDER_DV,sp.CRITERE_NON_FONGIBILITE,sp.CODE_HEDGING,sp.CODE_CONTREPARTIE,
        sp.CODE_INTERM_NEGOCE_1,sp.CODE_INTERM_NEGOCE_2,sp.PLACE_COTATION,sp.STRATEGIE_TRANSACTION,sp.NOTRE_DEPOT,
        CASE WHEN CATEGORIE_VALEUR = 'VMOB' THEN ett.CODE_TABLE_REF_RESUL
        ELSE CATEGORIE_VALEUR END AS CLASSE_ACTIF
        FROM
        situation_portefeuille sp left join descriptif_valeur dv on sp.code_valeur= dv.code_valeur
        left join ensemble_table ett on ett.CODE_DETAIL =dv.TYPE_VALEUR
        and ett.CODE_TABLE='TYPVAL'
                WHERE
            sp.code_portefeuille=:code_portefeuille
            AND TYPE_STOCK='AD1'
    """
    conn=get_connection(env)
    cur =conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille})
    rows=cur.fetchall()

    positions = [PositionNV(**row_to_dict(cur,row)) for row in rows]
    logger.info(f"get_portfolio_positions_no_valo - nombre de positions récupérées : {len(positions)}")
    result = pd.DataFrame(positions)
    result["date_derniere_modification"] = pd.to_datetime(result["date_derniere_modification"])

    cur.close()
    conn.close()
    return result





def get_position_by_id(position_id: int):
    for p in MOCK_POSITIONS:
        if p["id"] == position_id:
            return p
    return None

@st.cache_data
def load_fx_forward_descriptor(env,code_ensemble_val,code_valeur)->Optional[FxForwardDescriptor]:
    sql ="""SELECT CODE_VALEUR, SOUS_CATEGORIE_VALEUR, LIB_CHANGE_A_TERME_C, DEVISE_COTATION, DEVISE_COTEE, NOMINAL,
    DATE_CREATION, DATE_ECHEANCE, COURS_SPOT,
    COURS_A_TERME, SENS_OPERATION, REMUNERATION_COTATION, REMUNERATION_COTE, CODE_CONTREPARTIE, CODE_INTERM_NEGOCE_1, DELTA_VALO_CAT, ID_USERNAME,
    DATE_SAISIE, HEURE_SAISIE, LIB_CHANGE_A_TERME_L, NATURE_CONTRAT FROM descriptif_change_a_terme WHERE code_valeur= :code_valeur """

    sql_comp = """ SELECT CODE_ENSEMBLE_VAL, CATEGORIE_VALEUR, CODE_VALEUR, RETENUE_SUR_COUPON, RETENUE_S_INT_COURU, INTERM_PAIEMENT_CP, CODE_FISCAL_VAL,
    CODE_COMPTABLE_VAL, CODE_GESTION, CRITERE_TRI_1, CRITERE_TRI_2, CRITERE_TRI_3, CRITERE_TRI_4, TRI_PERSONNEL_1, TRI_PERSONNEL_2, TRI_PERSONNEL_3,
    TRI_PERSONNEL_4, TRI_VALO, INDICE, TITRE_ADMIS, FLAG_A_BLOQUER, TYPE_GARANTIE_VALEUR, TIERS_GARANTI, TYPE_RISQUE, TRANSMISSION_EIS,
    VOLATILITE_THEORIQUE, CODE_METHODE_GEST_INST, TYPE_PRIME_REMBOURSEMENT, CODE_RATING, DATE_RATING, ID_USERNAME, DATE_SAISIE,
    HEURE_SAISIE, CODE_GESTION_RECU, CODE_GESTION_VERSE, TYPE_RESERVE, NUMERO_COMPTE_TRESO, TYPE_SURCOTE_DECOTE,
    FLAG_LIBEREE FROM contenu_ensemble_val WHERE code_ensemble_val=:code_ensemble_val and code_valeur= :code_valeur """

    conn=get_connection(env)
    cur=conn.cursor()
    logger.debug(f"code_ensemble_val {code_ensemble_val}")
    logger.debug(f"code_valeur {code_valeur}")
    cur.execute(sql_comp,{"code_ensemble_val":code_ensemble_val,"code_valeur":code_valeur})
    row_comp=cur.fetchone()
    contenuEnsval=ContenuEnsembleVal(**row_to_dict(cur,row_comp))
    cur.execute(sql,{"code_valeur":code_valeur})
    row_main=cur.fetchone()
    result = FxForwardDescriptor(**row_to_dict(cur,row_main))
    result.contenu_es_val=contenuEnsval

    cur.close()
    conn.close()
    return result

@st.cache_data
def get_historique_change(env, code_portefeuille: str, date_valorisation: date) ->list[HistoChange]:
    sql ="""select DATE_VALORISATION, CODE_PORTEFEUILLE, CODE_DEVISE, CODE_DEVISE_COT, COURS_CHANGE, QUOTITE_EXPRESSION, DATE_COTATION,
    INDICATEUR_FORCAGE from HISTORIQUE_CHANGE H where H.DATE_VALORISATION=:date_valorisation and H.CODE_PORTEFEUILLE=:code_portefeuille """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valorisation":date_valorisation})
    rows=cur.fetchall()
    histoChanges =[HistoChange(**row_to_dict(cur,row)) for row in rows]
    cur.close()
    conn.close()
    return histoChanges



@st.cache_data
def get_caract_portefeuille(env,code_portefeuille :str)->Portefeuille:
    sql_main = """select dp.CODE_PORTEFEUILLE,dp.LIBELLE_PORT_C,dp.LIBELLE_PORT_L,dp.CODE_PORTEFEUILLE_INTERNE,dp.DATE_CREATION,
    dp.CODE_TYPE_PORT,dp.NIVEAU_PORTEFEUILLE,dp.OBJECTIF_PORTEFEUILLE,dp.TYPE_OPC,dp.CODE_RATIO_LEGAL,dp.CODE_RATIO_GESTION,
    dp.TYPE_CONTROLE_LIMITE,dp.FLAG_OPC_COORDONNE,dp.CODE_ENSEMBLE_PORT_PARAM,dp.CODE_ENSEMBLE_VAL_PORT,dp.CODE_FIXING_PORT,
    dp.DEVISE_PORTEFEUILLE,dp.CODE_CLIENT,dp.AUTORISATION_DECOUVERT,dp.CODE_MULTI_DEPOT,dp.CODE_DEPOSITAIRE_FONDS,
    dp.TYPE_FISCALITE,dp.DATE_DERN_DISTRI,dp.DERN_PARITE_VL_MULTIPLE,dp.DATE_A_DERN_DISTRI,dp.DATE_DERN_PARITE_VL_MULTIPLE,
    dp.FLAG_CALCUL_FRAIS,dp.CODE_STATUT_REEVAL,dp.NOMINAL,dp.STATUT_DECIMALES,dp.TYPE_CAPITAL,dp.TYPE_SOUSCRIPTION_RACHAT,
    dp.TAUX_DROIT_SOUSCRIPTION,dp.TAUX_DROIT_SOUSCRIPTION_MAX,dp.TAUX_DROIT_RACHAT,dp.TAUX_DROIT_RACHAT_MAX,dp.NOMBRE_DECIMAL,
    dp.BASE_ARRONDIS,dp.TYPE_FREQUENCE_VALO,dp.TYPE_CALENDRIER_VALO,dp.FLAG_CALCUL_SOULTE,dp.MONTANT_PREM_SOUS_MINI,
    dp.MONTANT_SOUS_MINI,dp.QUANTITE_SOUS_MINI,dp.QUANTITE_STOCK_MINI,dp.CODE_COMPTE_TRESO_PAR,dp.NOM_TAUX_SOUS,
    dp.REF_CALCUL_TAUX_SOUS,dp.NOM_TAUX_RACHAT,dp.REF_CALCUL_TAUX_RACHAT,dp.CODE_INTERM_NEGOCE,dp.NOM_TAUX_RETRO,
    dp.DATE_ARCHIVAGE,dp.CODE_COMPTABLE,dp.CODE_GESTIONNAIRE,dp.CODE_COMMISSAIRE_FONDS,dp.DATE_FERMETURE,
    dp.MOTIF_FERMETURE,dp.DATE_AGREMENT_COB,dp.DUREE_VIE_STATUTAIRE,dp.DUREE_BLOCAGE,dp.TYPE_FONDS,
    dp.ORIENTATION_GESTION,dp.NOMBRE_MEMBRE_CONSEIL_ENT,dp.NOMBRE_MEMBRE_CONSEIL_SAL,dp.MESSAGE_ALERTE,
    dp.CODE_SICAV,dp.FLAG_ARRONDI_VL,dp.TYPE_REPARTITION_PASSIF,dp.FLAG_TVA_FONDS,dp.DATE_BASCULE_DEVISE,
    dp.DEVISE_PORT_PREC,dp.ID_USERNAME,dp.DATE_SAISIE,dp.HEURE_SAISIE,dp.TYPE_STOCK_PRINCIPAL,dp.TYPE_METIER,
    dp.FLAG_FONDS_DELEGUE,dp.SOCIETE_DELEGANTE,dp.SOCIETE_DELEGUEE,dp.SOCIETE_ADMINISTRATRICE,
    case when lt.CRITERE_TRI = 'O' then 'MTD_LUX' else 'MTD_STD' end METHODE,
    trim(dc1.valeur_zone) mode_allocation_actif,
    trim(dc2.valeur_zone) mode_eclatement_resultat
    from DESCRIPTIF_PORTEFEUILLE dp
    left join liste_tris lt on dp.code_portefeuille=lt.code_valeur
    and LT.CODE_ENSEMBLE_VAL='MAJPOE' and LT.CATEGORIE_VALEUR='PORT' and LT.TYPE_TRI='HDSL'
    left join donnees_complementaires_objet dc1 on dp.code_portefeuille=dc1.code_portefeuille
    and dc1.code_ensemble_val='.' and dc1.categorie_valeur_mere='FUND' and dc1.code_valeur='.'
    and dc1.code_zone='MDALAN'
    left join donnees_complementaires_objet dc2 on dp.code_portefeuille=dc2.code_portefeuille
    and dc2.code_ensemble_val='.' and dc2.categorie_valeur_mere='FUND' and dc2.code_valeur='.'
    and dc2.code_zone='MDALRS'
    where dp.CODE_PORTEFEUILLE=:code_portefeuille
    """

    sql_comp = """select CODE_PORTEFEUILLE, TRAITEMENT_CONVERTIBLES, DELTA_VALO_VMOB, DELTA_VALO_CRNE, DELTA_VALO_SWAT, DELTA_VALO_TRES,
    DELTA_VALO_CAT, DELTA_VALO_REME, DELTA_VALO_OPTI, FLAG_HORS_BILAN, FLAG_VALO_PRUDENTIELLE, FLAG_MULTI_GERANT, TYPE_PARAMETRAGE_ECRAN,
    ID_USERNAME, DATE_SAISIE, HEURE_SAISIE, FLAG_CHANGE_PRIX_REVIENT, FLAG_CHANGE_COUPON_COURU, FLAG_CHANGE_COUPON_DETACHE, TYPE_CALENDRIER_FERIE,
    TYPE_CALCUL_PRIX_PART, PERIODE_LINEARISATION, TYPE_FISCALITE_VALEUR_PORT, DEVISE_FISCALE, UNITE_PERIODICITE, FLAG_VALO_ECH_REME,
    FLAG_VALO_ECH_TRES, FLAG_POOL, FLAG_FEEDER, FLAG_CSA, FLAG_CLONE, FLAG_CSA_HEDGE, CODE_STRUCTURE, DELTA_VALO_DECR,
    DELTA_VALO_CAP_FLOOR, CUT_OFF_OPF_VALO, SENSIBILITE_MAX, DELTA_VALO_FRA, CODE_PORTEFEUILLE_MAITRE,
    CODE_VALEUR_MAITRE, SENSIBILITE_MIN_PORT, SENSIBILITE_MAX_PORT, FLAG_MARCHE_TERME, FLAG_GESTION_COLLATERAL,
    CODE_POOL_COLLATERAL, TYPE_JOUR_VIOLATION from DESCRIPTIF_COMP_PORTEFEUILLE WHERE CODE_PORTEFEUILLE=:code_portefeuille """

    conn=get_connection(env)
    cur=conn.cursor()

    cur.execute(sql_main,{"code_portefeuille":code_portefeuille})
    row_main=cur.fetchone()
    portefeuille =Portefeuille(**row_to_dict(cur,row_main))
    cur.execute(sql_comp,{"code_portefeuille":code_portefeuille})
    row_comp=cur.fetchone()
    portefeuille.complet=CompPortefeuille(**row_to_dict(cur,row_comp))

    cur.close()
    conn.close()

    return portefeuille

@st.cache_data
def get_historique_passif(env, code_portefeuille: str, date_valorisation: date) ->pd.DataFrame:
    #sql ="""select * from historique_passif H where H.DATE_VALORISATION=:date_valorisation and H.CODE_PORTEFEUILLE=:code_portefeuille """
    sql="""
    select hp.DATE_VALORISATION,hp.CODE_PORTEFEUILLE,hp.TYPE_STOCK,hp.CATEGORIE_VALEUR,hp.CODE_VALEUR,hp.STATUT_VALEUR,hp.STATUT_LIGNE,
    hp.CODE_CONTREP_LIGNE,hp.CODE_DEPOSITAIRE,hp.PRIX_REVIENT_VALO,hp.MONTANT_DERN_VALO,dp.CODE_POSTE_PRINCIPAL,dp.CODE_PART_DEDIE,
    dp.KRONECKER_POSTE from historique_passif hp left join descriptif_poste dp on hp.code_valeur=dp.code_valeur
    and hp.categorie_valeur=dp.categorie_valeur
    where hp.code_portefeuille=:code_portefeuille and hp.DATE_VALORISATION=:date_valorisation
    """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valorisation":date_valorisation})
    rows=cur.fetchall()
    datas =[HistoPass(**row_to_dict(cur,row)) for row in rows]
    result = pd.DataFrame(datas)
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_gestion_valo(env, code_portefeuille: str) ->list[GestionValo]:
    sql ="""select CODE_PORTEFEUILLE, HISTO_DATE_VALORISATION, ACTIF_NET_TOT, FLAG_VL_VALIDE, FLAG_VL_FORCEE, FLAG_CALFLU,
    STATUT_REPORTING, DATE_COTATION, DATE_CHANGE, DATE_INTERETS, CODE_TRANS_VALO, CODE_TRANS_FRAIS, CODE_TRANS_FRAIS_VEILLE,
    CODE_TRANS_BASCULE, CODE_TRANS_LAT, TRANSMISSION_EIS, FLAG_DIFFUSION_INTERNE, FLAG_DIFFUSION_EXTERNE, FLAG_REMONTEE_HISTORIQUE,
    RAPPORT_VL, DIVERGENCE_PARITE, HEURE_MAJ_VL, DATE_MAJ_VL, ID_USERNAME, CODE_TRANS_EXCLU, STATUT_VL, NUMERO_VALORISATION,
    FLAG_COMPTA_VALIDE, FLAG_COMPLIANCE, TYPE_DATE_REMONTEE from gestion_valorisation where code_portefeuille=:code_portefeuille """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille})
    rows=cur.fetchall()
    result =[GestionValo(**row_to_dict(cur,row)) for row in rows]
    cur.close()
    conn.close()
    return result



@st.cache_data
def get_historique_vl(env, code_portefeuille: str) ->pd.DataFrame:
    sql ="""
    SELECT
    hvl.CODE_PORTEFEUILLE,hvl.DATE_VALORISATION,hvl.CODE_PART,hvl.VL_PART,hvl.ACTIF_NET_PART,hvl.NB_PART_VALO,hvl.COEFFICIENT_PART,
    hvl.PRIX_SOUSCRIPTION,hvl.PRIX_RACHAT,hvl.MONTANT_SOUSCRIT,hvl.MONTANT_RACHETE,hvl.NB_PARTS_SOUS,hvl.NB_PARTS_RACH,hvl.VL_PART_AVANT_FRAIS,
    hvl.ACTIF_PART_AVANT_FRAIS,hvl.PRIX_APPLICABLE,hvl1.CODE_DEVISE as devise_part, hvl1.VALEUR_BOURSIERE_TOT as actif_net_part_dv
    FROM
    historique_vl hvl join historique_valorisation hvl1
    on hvl.code_portefeuille=hvl1.code_portefeuille
    and hvl1.TRI_VALO=hvl.CODE_PART
    and hvl.code_portefeuille =:code_portefeuille
    and TO_DATE('14091752','DDMMYYYY')-hvl.DATE_VALORISATION= histo_date_valorisation """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille})
    rows=cur.fetchall()
    data =[HistoriqueVl(**row_to_dict(cur,row)) for row in rows]
    result= pd.DataFrame(data)

    # result["date_valorisation"]= result["date_valorisation"].dt.date
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_cours_termes(env,devise_cotee,devise_cotation,histo_date,fixing)->pd.DataFrame:
    sql="""
    select b.CODE_DUREE, b.POINTS_CHANGE, b.COURS_A_TERME, b.DATE_EXTRACTION, b.CODE_DEVISE, b.CODE_DEVISE_COT from COURS_TERME_DEVISE b
    where b.CODE_ENSEMBLE_VAL='BVAL' and b.CODE_DEVISE_FIXING=:fixing and b.CODE_DEVISE=:devise_cotee and b.CODE_DEVISE_COT=:devise_cotation
    and b.HISTO_DATE_COTATION = (
    select min(a.HISTO_DATE_COTATION) from COURS_TERME_DEVISE a where
    a.CODE_ENSEMBLE_VAL=b.CODE_ENSEMBLE_VAL and
    a.CODE_DEVISE=b.CODE_DEVISE and
    a.CODE_DUREE=b.CODE_DUREE and
    a.CODE_DEVISE_FIXING = b.CODE_DEVISE_FIXING and
    a.CODE_DEVISE_COT = b.CODE_DEVISE_COT and
    a.HISTO_DATE_COTATION > :histo_date_inf and a.HISTO_DATE_COTATION < :histo_date_sup)
    order by b.CODE_DUREE
    """
    histo_date_inf=histo_date
    histo_date_sup=histo_date_inf +200

    logger.debug(histo_date_inf)
    logger.debug(histo_date_sup)
    logger.debug(devise_cotee)
    logger.debug(devise_cotation)
    logger.debug(fixing)

    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"devise_cotee":devise_cotee,"devise_cotation":devise_cotation,
                     "histo_date_inf":histo_date_inf,"histo_date_sup":histo_date_sup,"fixing":fixing})
    rows=cur.fetchall()

    data = [ CoursTerme(**row_to_dict(cur,row)) for row in rows]
    result= pd.DataFrame(data)
    #result =result.set_index("code_duree")
    #result.index=result.index.str.strip()
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_verlam(env,code_portefeuille,date_effet_min,date_effet_max)->pd.DataFrame:
    # sql="""
    # select * from transaction_ where
    # code_portefeuille=:code_portefeuille and TYPE_TRANSACTION='LAT' and CODE_VALEUR_SOURCE=' '
    # and DATE_EFFET>:date_effet_max and DATE_EFFET>=:date_effet_min
    # order by DATE_EFFET desc, code_transaction,code_externe
    # """

    sql="""
        select opd.CODE_PORTEFEUILLE,opd.TYPE_DATE,opd.DATE_,opd.CODE_TRANSACTION,opd.STATUT_EXTOURNE, tt.CODE_TRANSACTION,tt.CODE_EVENEMENT,
        tt.CODE_EXTERNE,tt.CODE_EXTERNE_ORIGINE,tt.LIB_TRANSACTION,tt.CODE_PORTEFEUILLE,tt.CODE_PORTEFEUILLE_PERE,tt.CODE_TYPE_PORT,
        tt.TYPE_CONTRAT,tt.TYPE_EVENEMENT,tt.TYPE_TRANSACTION,tt.TYPE_REGLEMENT,tt.CODE_VALEUR_SOURCE,tt.CODE_TYPE_PORT,
        tt.CODE_ACTIONNARIAT_SOURCE,tt.CODE_ACTIONNARIAT_RESUL,tt.DATE_EFFET,tt.ID_USERNAME,tt.DATE_SAISIE,tt.HEURE_SAISIE,
        tt.DATE_DE_VALEUR,tt.DATE_PROPRIETE,tt.DATE_LIVRAISON,tt.DATE_SYSTEME,tt.REGLEMENT,tt.PLACE_COTATION,tt.DATE_REALISATION,
        tt.TYPE_DATE_COMPTABLE,tt.DATE_COMPTABLE,tt.QUANTITE_EXERCICE,tt.QUANTITE_NOUVELLE,tt.QUANTITE_ANCIENNE,tt.CODE_DEVISE_NEGOCE,
        tt.CODE_DEVISE_REGL,tt.COURS_DR_EN_DN,tt.COURS_DC_EN_DN,tt.COURS_DV_EN_DN,tt.FORMAT_VAL_SOURCE_DN,
        tt.CP_COURU_SOURCE,tt.INTERETS_DN,tt.CALCUL_DUREE_INTERET,tt.NOMBRE_JOURS_INTERETS,tt.MONTANT_BRUT_DN,tt.TAUX_ACTUARIEL,
        tt.EXPOSANT_TAUX_ACTUARIEL,tt.CODE_COURTAGE,tt.FRAIS_COURTAGE_DN,tt.MONTANT_DONT_AVEC_DN,tt.MONTANT_IMPOT_DN,
        tt.MONTANT_IMPOT_DN,tt.MONTANT_TAXE_DN,tt.MONTANT_NET_DR,tt.CODE_DEVISE_FRAIS,tt.MONTANT_COMMISSION_DN,
        tt.MONTANT_IMPOT_DF,tt.MONTANT_TVA_DF,tt.MONTANT_NET_DP,tt.COMPTE_REGLEMENT_DP,tt.COMPTE_REGLEMENT_DR,
        tt.MONTANT_NET_ORIGINE_DC,tt.CODE_GERANT_SOURCE,tt.CODE_GERANT_RESUL,tt.CODE_INTERM_NEGOCE_1,tt.COMMISSION_2_DC,
        tt.CODE_INTERM_NEGOCE_2,tt.CODE_CONTREPARTIE,tt.LEUR_DEPOT,tt.LEUR_NOSTRO,tt.NOTRE_DEPOT,tt.NOTRE_NOSTRO,
        tt.FLAG_SITUATION_MESSAGERIE,tt.DEGRE_STOCK_MAX,tt.INTERETS_BRUT_DN,tt.OBJECTIF_TRANSACTION,tt.FISCALITE_TRANSACTION,
        tt.CODE_EXTERNE_INTERFACE,tt.HEURE_NEGOCIATION,tt.CODE_VALEUR_LIEN,tt.COURS_VALEUR_CI,tt.CODE_SOUS_PART,tt.CODE_HEDGING,
        tt.STRATEGIE_TRANSACTION,tt.OBJECTIF_TRANSACTION_2,tt.CODE_VALEUR_RESUL_2,tt.QUANTITE_ANCIENNE_2,tt.QUANTITE_NOUVELLE_2,
        tt.COMPTE_REGLEMENT_CASH,tt.COMPTE_REGLEMENT_PASSAGE,tt.COMPTE_REGLEMENT_CASH_2,tt.COMPTE_REGLEMENT_PASSAGE_2,
        tt.EXPRESSION_COURS from operation_par_date opd join transaction_ tt on opd.CODE_PORTEFEUILLE= tt.CODE_PORTEFEUILLE
        and opd.CODE_TRANSACTION= tt.CODE_TRANSACTION
        and opd.code_portefeuille=:code_portefeuille and opd.TYPE_DATE='VAL'
        and date_ <:date_effet_max and date_>:date_effet_min
        and tt.TYPE_TRANSACTION='LAT'
        order by date_ asc
    """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_effet_min":date_effet_min,
                     "date_effet_max":date_effet_max})
    rows=cur.fetchall()
    data = [ TransactionLine(**row_to_dict(cur,row)) for row in rows]
    result= pd.DataFrame(data)
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_ensemble_port(env)->pd.DataFrame:

    sql=""" select CODE_ENSEMBLE_PORT, LIB_ENSEMBLE_PORT_C, LIB_ENSEMBLE_PORT_L, CODE_DEVISE_FIXING, CODE_DEVISE_FIXING_TERME,
    MODE_COMPTABILITE, DELTA_JOUR, DELTA_TAUX, DELTA_VALO, DELAI_REMERE, PREAVIS_REMERE from DESCRIPTIF_ENSEMBLE_PORT ORDER BY CODE_ENSEMBLE_PORT"""
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql)
    rows=cur.fetchall()
    data =[ DescriptifEnsemblePort(**row_to_dict(cur,row)) for row in rows]
    result= pd.DataFrame(data)
    cur.close()
    conn.close()
    return result


@st.cache_data
def get_contenu_ensemble_port(env,code_ensemble_port)->pd.DataFrame:

    sql=""" select * from CONTENU_ENSEMBLE_PORT WHERE CODE_ENSEMBLE_PORT=:code_ensemble_port """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_ensemble_port":code_ensemble_port})
    rows=cur.fetchall()
    data = [ ContenuEnsemblePort(**row_to_dict(cur,row)) for row in rows]
    result= pd.DataFrame(data)
    cur.close()
    conn.close()
    return result


@st.cache_data
def get_sr(env,code_portefeuille,date_valo)->pd.DataFrame:

    sql=""" select B.CODE_PORTEFEUILLE, rtrim(B.CODE_VALEUR) code_part,
        B.CODE_TRANSACTION, A.STATUT_EXTOURNE,B.TYPE_TRANSACTION, B.DATE_EFFET, B.VARIATION_PRIX_REVIENT, case when A.STATUT_EXTOURNE='XX'
        then -B.VARIATION_PRIX_REVIENT else B.VARIATION_PRIX_REVIENT end montant_sr ,rtrim(B.CATEGORIE_VALEUR) TYPE_STOCKAGE
        from
        OPERATION_PAR_DATE A, MOUVEMENT B , DESCRIPTIF_PORTEFEUILLE C
        where
        A.CODE_TRANSACTION=B.CODE_TRANSACTION
        and A.CODE_PORTEFEUILLE=B.CODE_PORTEFEUILLE
        and A.CODE_PORTEFEUILLE=C.CODE_PORTEFEUILLE
        and A.TYPE_DATE='NAV'
        and A.DATE_=:date_valo
        and B.TYPE_STOCK='HOBI'
        and A.CODE_PORTEFEUILLE=:code_portefeuille
        order by B.CODE_VALEUR"""
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo})
    rows=cur.fetchall()
    data = [ OperationsR(**row_to_dict(cur,row)) for row in rows]
    # result= pd.DataFrame(data)
    result = dataclass_to_df(data,OperationsR)
    if not result.empty:
        result["date_effet"]=pd.to_datetime(result["date_effet"]).dt.date
    cur.close()
    conn.close()
    return result


@st.cache_data
def get_tr(env,code_portefeuille,date_valo)->pd.DataFrame:

    sql=""" select B.CODE_PORTEFEUILLE, rtrim(B.CODE_VALEUR) code_part,
        B.CODE_TRANSACTION, A.STATUT_EXTOURNE,B.TYPE_TRANSACTION, B.DATE_EFFET, B.VARIATION_PRIX_REVIENT, case when A.STATUT_EXTOURNE='XX'
        then -B.VARIATION_PRIX_REVIENT else B.VARIATION_PRIX_REVIENT end montant_sr ,rtrim(B.CATEGORIE_VALEUR) TYPE_STOCKAGE
        from
        OPERATION_PAR_DATE A, MOUVEMENT B , DESCRIPTIF_PORTEFEUILLE C
        where
        A.CODE_TRANSACTION=B.CODE_TRANSACTION
        and A.CODE_PORTEFEUILLE=B.CODE_PORTEFEUILLE
        and A.CODE_PORTEFEUILLE=C.CODE_PORTEFEUILLE
        and A.TYPE_DATE='NAV'
        and A.DATE_=:date_valo
        and B.TYPE_STOCK='HOBI'
        and A.CODE_PORTEFEUILLE=:code_portefeuille
        order by B.CODE_VALEUR"""
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo})
    rows=cur.fetchall()
    data = [ OperationsR(**row_to_dict(cur,row)) for row in rows]
    # result= pd.DataFrame(data)
    result = dataclass_to_df(data,OperationsR)
    if not result.empty:
        result["date_effet"]=pd.to_datetime(result["date_effet"]).dt.date
    cur.close()
    conn.close()
    return result


@st.cache_data
def get_actifs_req(env,code_portefeuille,date_valo,date_valo_prec)->pd.DataFrame:
    logger.info(f"date_valo : {date_valo} ;date_valo_prec : {date_valo_prec} ")
    sql=""" SELECT HV.CODE_PORTEFEUILLE, HV.DATE_VALORISATION DATE_VALORISATION, rtrim(HV.CODE_PART) CODE_PART,HV.ACTIF_NET_PART ACTIF_NET_PART,
        HV.COEFFICIENT_PART COEFFICIENT_PART,HV.NB_PART_VALO NB_PART_VALO, HV.VL_PART VL_PART,
        HV1.DATE_VALORISATION DATE_VALORISATION_V, HV1.ACTIF_NET_PART ACTIF_NET_PART_V, HV1.COEFFICIENT_PART COEFFICIENT_PART_V,
        HV1.NB_PART_VALO NB_PART_VALO_V,
        rtrim(DP.FLAG_ARRONDI_VL) FLAG_ARRONDI_VL,DP.CODE_DEVISE_REFERENCE,to_number(DP.DECIMALES_VL) decimales_vl from
        HISTORIQUE_VL HV
        left join HISTORIQUE_VL HV1 on HV.CODE_PORTEFEUILLE=HV1.CODE_PORTEFEUILLE and HV.CODE_PART=HV1.CODE_PART and HV1.DATE_VALORISATION=:date_valo_prec
        left join DESCRIPTIF_PART DP on HV.CODE_PORTEFEUILLE=DP.CODE_PORTEFEUILLE and HV.CODE_PART=DP.CODE_PART
        where HV.CODE_PORTEFEUILLE=:code_portefeuille and HV.DATE_VALORISATION=:date_valo
        order by HV.CODE_PART"""
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo,"date_valo_prec":date_valo_prec})
    rows=cur.fetchall()
    data = [ ActifReq(**row_to_dict(cur,row)) for row in rows]
    result = dataclass_to_df(data,ActifReq)
    if not result.empty:
        result["date_valorisation"]=pd.to_datetime(result["date_valorisation"]).dt.date
        result["date_valorisation_v"]=pd.to_datetime(result["date_valorisation_v"]).dt.date
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_frais(env,code_portefeuille,date_valo,date_valo_prec)->pd.DataFrame:

    sql="""
        select JF.CODE_PORTEFEUILLE, JF.DATE_VALORISATION, rtrim(DF.CODE_ACTIONNARIAT) CODE_PART, sum(JF.MONTANT_FRAIS_DP) MONTANT_FRAIS
        from JOURNALING_FRAIS JF, DESCRIPTIF_FRAIS DF
        where
        JF.CODE_PORTEFEUILLE=DF.CODE_PORTEFEUILLE and
        JF.TYPE_FRAIS=DF.TYPE_FRAIS and
        JF.CODE_PORTEFEUILLE=:code_portefeuille and JF.DATE_VALORISATION in (:date_valo_prec,:date_valo) and DF.TYPE_FRAIS not like 'FMAX%'
        group by JF.CODE_PORTEFEUILLE, JF.DATE_VALORISATION, DF.CODE_ACTIONNARIAT
        having sum(JF.MONTANT_FRAIS_DP)<>0
        """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo,"date_valo_prec":date_valo_prec})
    rows=cur.fetchall()
    data = [ Frais(**row_to_dict(cur,row)) for row in rows]
    result= dataclass_to_df(data,Frais)
    if not result.empty:
        result["date_valorisation"]=pd.to_datetime(result["date_valorisation"]).dt.date
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_od_frais(env,code_portefeuille,date_valo,date_valo_prec)->pd.DataFrame:

    sql="""
        select M.CODE_PORTEFEUILLE,M.TYPE_STOCK,M.CATEGORIE_VALEUR, rtrim(M.CODE_VALEUR) code_part, M.CODE_TRANSACTION,
        case when OPD.STATUT_EXTOURNE='XX' then -M.VARIATION_PRIX_REVIENT else M.VARIATION_PRIX_REVIENT end
        as VAR,
        M.TYPE_TRANSACTION,OPD.DATE_
        from MOUVEMENT M , OPERATION_PAR_DATE OPD
        where
        M.CODE_PORTEFEUILLE=:code_portefeuille
        and M.CODE_TRANSACTION=OPD.CODE_TRANSACTION
        and M.CODE_PORTEFEUILLE=OPD.CODE_PORTEFEUILLE
        and OPD.TYPE_DATE='NAV'
        and OPD.DATE_ in (:date_valo_prec,:date_valo)
        and M.TYPE_STOCK = 'HOBI'
        and M.CATEGORIE_VALEUR in ('FRAI','DROI')
        """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo,"date_valo_prec":date_valo_prec})
    rows=cur.fetchall()
    data = [ ODFrais(**row_to_dict(cur,row)) for row in rows]
    result= dataclass_to_df(data,ODFrais)
    if not result.empty:
        result["date_"]=pd.to_datetime(result["date_"]).dt.date
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_hedge_config(env,code_portefeuille)->pd.DataFrame:

    sql="""
        select CODE_PORTEFEUILLE,rtrim(STATUT_LIGNE) CODE_PART,rtrim(STATUT_VALEUR) groupe
        from
        SITUATION_DETENTION
        where
        CODE_ENSEMBLE_VAL='HEDGES' and CATEGORIE_VALEUR='PART'
        and CODE_PORTEFEUILLE=:code_portefeuille
        """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille})
    rows=cur.fetchall()
    data = [ HedgeConfig(**row_to_dict(cur,row)) for row in rows]

    result= dataclass_to_df(data,HedgeConfig)
    cur.close()
    conn.close()
    return result


@st.cache_data
def get_latent_hedge(env,code_portefeuille,date_valo,date_valo_prec)->pd.DataFrame:

    sql="""
        with h as (
        select A.DATE_VALORISATION,A.CODE_PORTEFEUILLE,rtrim(B.STATUT_LIGNE_PORT) groupe,A.CATEGORIE_VALEUR,A.CODE_VALEUR,
        sum (A.MONTANT_DERN_VALO-A.PRIX_REVIENT_VALO) MONTANT
        from
        HISTORIQUE_INVENTAIRE A, SITUATION_DETENTION B
        where
        A.CODE_PORTEFEUILLE=B.CODE_PORTEFEUILLE
        and A.CATEGORIE_VALEUR=B.CATEGORIE_VALEUR
        and A.CODE_VALEUR=B.CODE_VALEUR
        and A.TYPE_STOCK='AD1'
        and A.DATE_VALORISATION in (:date_valo,:date_valo_prec)
        and A.CODE_PORTEFEUILLE=:code_portefeuille
        and B.CODE_ENSEMBLE_VAL='HEDGES'
        group by A.DATE_VALORISATION,A.CODE_PORTEFEUILLE,B.STATUT_LIGNE_PORT ,A.CATEGORIE_VALEUR,A.CODE_VALEUR
        ),
        b as (
        select A.DATE_VALORISATION,A.CODE_PORTEFEUILLE,rtrim(A.CODE_HEDGING) groupe,A.CATEGORIE_VALEUR,A.CODE_VALEUR,
        sum (A.MONTANT_DERN_VALO-A.PRIX_REVIENT_VALO) Montant
        from
        HISTORIQUE_INVENTAIRE A
        where
        A.TYPE_STOCK='AD1'
        and A.DATE_VALORISATION in (:date_valo,:date_valo_prec)
        and A.CODE_PORTEFEUILLE=:code_portefeuille
        and A.CODE_HEDGING<>' '
        group by A.DATE_VALORISATION,A.CODE_PORTEFEUILLE,A.CODE_HEDGING,A.CATEGORIE_VALEUR,A.CODE_VALEUR
        )
        select DATE_VALORISATION, CODE_PORTEFEUILLE, GROUPE, CATEGORIE_VALEUR, CODE_VALEUR, MONTANT from h union select * from b
        order by DATE_VALORISATION DESC, GROUPE,CATEGORIE_VALEUR
        """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo,"date_valo_prec":date_valo_prec})
    rows=cur.fetchall()
    data = [ LatentHedge(**row_to_dict(cur,row)) for row in rows]
    result= dataclass_to_df(data,LatentHedge)
    if not result.empty:
        result["date_valorisation"]=pd.to_datetime(result["date_valorisation"]).dt.date
    cur.close()
    conn.close()
    return result


@st.cache_data
def get_realise_hedge(env,code_portefeuille,date_valo)->pd.DataFrame:

    sql="""

        select DISTINCT M.CODE_PORTEFEUILLE,M.TYPE_STOCK,M.CATEGORIE_VALEUR, M.CODE_VALEUR, M.CODE_TRANSACTION,
        case when OPD.STATUT_EXTOURNE='XX' then -M.VARIATION_PRIX_REVIENT else M.VARIATION_PRIX_REVIENT end as MONTANT,
        M.TYPE_TRANSACTION,OPD.DATE_, DP.CODE_PART_DEDIE, rtrim(SD.STATUT_VALEUR) groupe
        from MOUVEMENT M , OPERATION_PAR_DATE OPD, DESCRIPTIF_POSTE DP, SITUATION_DETENTION SD
        where
        M.CODE_TRANSACTION=OPD.CODE_TRANSACTION and M.CODE_PORTEFEUILLE=OPD.CODE_PORTEFEUILLE and
        M.CATEGORIE_VALEUR=DP.CATEGORIE_VALEUR and M.CODE_VALEUR=DP.CODE_VALEUR and
        M.CODE_PORTEFEUILLE=SD.CODE_PORTEFEUILLE and SD.STATUT_VALEUR=DP.CODE_PART_DEDIE and
        M.CODE_PORTEFEUILLE=:code_portefeuille and
        OPD.TYPE_DATE='NAV' and OPD.DATE_=:date_valo and M.TYPE_TRANSACTION !='BASC' and M.TYPE_STOCK='PSSF' and
        SD.CODE_ENSEMBLE_VAL='HEDGES' and SD.CATEGORIE_VALEUR='PART'
        """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo})
    rows=cur.fetchall()
    data = [ RealiseHedge(**row_to_dict(cur,row)) for row in rows]
    result= dataclass_to_df(data,RealiseHedge)
    if not result.empty:
        result["date_"]=pd.to_datetime(result["date_"]).dt.date
    cur.close()
    conn.close()
    return result


@st.cache_data
def get_realise_hobi(env,code_portefeuille,date_valo,date_valo_prec)->pd.DataFrame:

    sql="""

        select CODE_PORTEFEUILLE, CATEGORIE_VALEUR, rtrim(CODE_VALEUR) CODE_VALEUR,'GROUPE' TYPE, MONTANT_DERN_VALO,PRIX_REVIENT_VALO,DATE_VALORISATION
        from HISTORIQUE_PASSIF where TYPE_STOCK='HOBI' and CATEGORIE_VALEUR='HEDG' and CODE_VALEUR in (
        select STATUT_VALEUR from SITUATION_DETENTION where CODE_PORTEFEUILLE=:code_portefeuille and CODE_ENSEMBLE_VAL='HEDGES' and CATEGORIE_VALEUR='PART') and
        CODE_PORTEFEUILLE=:code_portefeuille and DATE_VALORISATION in (:date_valo,:date_valo_prec)
        UNION
        select CODE_PORTEFEUILLE, CATEGORIE_VALEUR, rtrim(CODE_VALEUR) CODE_VALEUR ,'PART' TYPE, MONTANT_DERN_VALO,PRIX_REVIENT_VALO,DATE_VALORISATION
        from HISTORIQUE_PASSIF where TYPE_STOCK='HOBI' and CATEGORIE_VALEUR='HEDG' and CODE_VALEUR not in (
        select STATUT_VALEUR from SITUATION_DETENTION where CODE_PORTEFEUILLE=:code_portefeuille and CODE_ENSEMBLE_VAL='HEDGES' and CATEGORIE_VALEUR='PART') and
        CODE_PORTEFEUILLE=:code_portefeuille and DATE_VALORISATION in (:date_valo,:date_valo_prec)
        UNION
        select CODE_PORTEFEUILLE, CATEGORIE_VALEUR, rtrim(CODE_VALEUR) CODE_VALEUR, 'PART' TYPE, MONTANT_DERN_VALO,PRIX_REVIENT_VALO,DATE_VALORISATION
        from HISTORIQUE_PASSIF where TYPE_STOCK='HOBI' and CATEGORIE_VALEUR='HEDV' and
        CODE_PORTEFEUILLE=:code_portefeuille and DATE_VALORISATION in (:date_valo,:date_valo_prec)

        order by DATE_VALORISATION DESC,CODE_VALEUR

        """
    conn=get_connection(env)
    cur=conn.cursor()
    cur.execute(sql,{"code_portefeuille":code_portefeuille,"date_valo":date_valo,"date_valo_prec":date_valo_prec})
    rows=cur.fetchall()
    data = [ RealiseHobi(**row_to_dict(cur,row)) for row in rows]
    result= dataclass_to_df(data,RealiseHobi)
    if not result.empty:
        result["date_valorisation"]=pd.to_datetime(result["date_valorisation"]).dt.date
    cur.close()
    conn.close()
    return result

@st.cache_data
def get_cloture_mapping(env,code_bascule,code_comptabilite)->pd.DataFrame:
    # version simplifié on ne récupère que le CO
    # sql="""
    #     SELECT
    #       CODE_BASCULE,CODE_COMPTABILITE_SOURCE,NUMERO_COMPTE_SOURCE,NUMERO_COMPTE_CR NUMERO_COMPTE_DEST
    #     FROM
    #       table_bascule
    #     WHERE
    #       code_bascule=:code_bascule
    # AND CODE_COMPTABILITE_SOURCE=:code_comptabilite
    # AND SENS_SOLDE='CO'
    #     """

    sql="""
        SELECT
        CODE_BASCULE,CODE_COMPTABILITE_SOURCE,TRIM(NUMERO_COMPTE_SOURCE) NUMERO_COMPTE_SOURCE ,TRIM(NUMERO_COMPTE_CR) NUMERO_COMPTE_DEST
        FROM
        table_bascule
        WHERE
        code_bascule='CLODIV'
        AND CODE_COMPTABILITE_SOURCE='PCN'
        AND SENS_SOLDE='CO'
        """

    conn=get_connection(env)
    cur=conn.cursor()
    logger.info(f"get_cloture_mapping-code_bascule: {code_bascule}")
    logger.info(f"get_cloture_mapping-code_comptabilite: {code_comptabilite}")
    # cur.execute(sql,{"code_bascule":code_bascule,"code_comptabilite":code_comptabilite})
    cur.execute(sql)
    rows=cur.fetchall()
    logger.info(f"get_cloture_mapping-nombre de mapping: {len(rows)}")
    data = [ TableBascule(**row_to_dict(cur,row)) for row in rows]
    result= dataclass_to_df(data,TableBascule)

    cur.close()
    conn.close()
    return result


def read_sql_df(conn, query: str, params: Optional[dict] = None) -> pd.DataFrame:
    return pd.read_sql(query, conn, params=params)


@st.cache_data(show_spinner=False)
def load_metadata_cache() -> dict:
    with gzip.open('metadata_cache.pkl.gz', 'rb') as f:
        dict_metadata = pickle.load(f)
        logger.debug(f"load_metadata_cache: loaded metadata cache with {len(dict_metadata)} tables")
        return dict_metadata


@st.cache_data(show_spinner=False)
def get_metadas(table:str,key:str) ->pd.DataFrame:
    dict_metadata= load_metadata_cache()
    logger.info(f"get_metadas-table: {table} - key: {key}")
    logger.debug(f"get_metadas-result: {dict_metadata.get(table,{}).get(key,{})}")
    return pd.DataFrame(dict_metadata.get(table,{}).get(key,{}))

_last_db_check = 0
__cached__status_db = False
TTL=60*10

def base_disponible(env):
    global _last_db_check, __cached__status_db
    now = time.time()
    if now - _last_db_check < TTL:
        return __cached__status_db
    try:
        conn=get_connection(env)
        cur=conn.cursor()
        cur.execute("""SELECT 1 FROM DUAL""")
        cur.fetchone()
        cur.close()
        conn.close()
        __cached__status_db = True
    except Exception :
        logger.info(f"base indisponible mode offline")
        __cached__status_db = False

    _last_db_check = now
    return __cached__status_db