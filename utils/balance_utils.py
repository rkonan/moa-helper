import pandas as pd
import logging

# === Logger ===
logger = logging.getLogger("RAGHybrid")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)


def nettoyage_df(COL_PTF, COL_IMPACT, COL_TRI_COMPTA, COL_STATUT_LIGNE, COL_STATUT_VALEUR, df, TOKENS_VIDE) -> pd.DataFrame:
    for c in [COL_PTF, COL_IMPACT, COL_TRI_COMPTA, COL_STATUT_LIGNE, COL_STATUT_VALEUR]:
        if c in df.columns:
            s = df[c]
            s=s.fillna("")
            s=s.astype(str).str.strip()
            s.replace(TOKENS_VIDE)
            df[c]=s
    return df

def format_balance(COL_PTF, COL_IMPACT, COL_SOLDE, COL_TRI_COMPTA, COL_STATUT_LIGNE, COL_STATUT_VALEUR, df_) -> pd.DataFrame:
    df_["solde"]=df_["Solde debit"]-df_["Solde credit"]
    df_["classe"]=df_["Numero compte"].astype(str).str[0]
    df_=df_.rename(columns={"Code valeur mere":"impact"})
    # Nettoyage minimal
    TOKENS_VIDE={"nan":"","none":"","<na>":"","nat":""}
    df_1=nettoyage_df(COL_PTF, COL_IMPACT, COL_TRI_COMPTA, COL_STATUT_LIGNE, COL_STATUT_VALEUR, df_, TOKENS_VIDE)

    if COL_SOLDE in df_1.columns:
        df_1[COL_SOLDE] = pd.to_numeric(df_1[COL_SOLDE], errors="coerce").fillna(0.0)

    return df_1

def load_balance_excel(uploaded_file, sheet_name: str | int | None = None) -> pd.DataFrame:
    if uploaded_file is None:

        return pd.DataFrame()

    # engine auto
    # df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
    df = pd.read_excel(uploaded_file)
    df.columns = [str(c).strip() for c in df.columns]
    return df



def enrichir_balance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Code comptabilite" in df.columns :
        df["Portefeuille"] = df["Code comptabilite"].fillna("").astype(str).str.strip()

    #on calcule le solde si besoin
    if "Solde debit" in df.columns and "Solde credit" in df.columns:
        df["solde"] = -df["Solde debit"] + df["Solde credit"]
    if "Numero compte" in df.columns and "classe" not in df.columns:
        df["classe"] = df["Numero compte"].astype(str).str[0]
    if "Code valeur mere" in df.columns and "Impact" not in df.columns:
        df["Impact"] = df["Code valeur mere"]
    return df

def enrichir_hispas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Port" in df.columns :
        df["Portefeuille"] = df["Port"].fillna("").astype(str).str.strip()


    if "Montant dern valo" in df.columns :
        df["solde"] = pd.to_numeric(df["Montant dern valo"], errors="coerce").fillna(0.0)

    if {"Code val","Code part"}.issubset(df.columns):
        df["Code val"] = df["Code val"].fillna("").astype(str).str.strip()
        df["Code part"] = df["Code part"].fillna("").astype(str).str.strip()
        df["Impact"]=df["Code val"]

        mask =(df["Code part"].ne("") &df.apply(lambda x: x["Code val"].endswith(x["Code part"]),axis=1))

        df.loc[mask, "Impact"] = df.loc[mask].apply(lambda x: x["Code val"][:-len(x["Code part"])],axis=1)

    return df

def normalize_balance(df: pd.DataFrame, axes: list[str], solde_col: str) -> pd.DataFrame:
    df = df.copy()


    # garde seulement les colonnes utiles si présentes
    keep_cols = [c for c in axes + [solde_col] if c in df.columns]
    df = df[keep_cols].copy()

    for c in axes:
        if c in df.columns:
            df[c] = _to_str_series(df[c])

    df[solde_col] = _to_float_series(df[solde_col])

    return df

def _to_str_series(s: pd.Series) -> pd.Series:
    s = s.astype("string")
    s = s.fillna("")
    s = s.str.strip()
    return s


def _to_float_series(s: pd.Series) -> pd.Series:
    if s.dtype == "object" or str(s.dtype).startswith("string"):
        # gère virgule décimale
        s = s.astype("string").str.replace("\u00A0", "", regex=False).str.replace(" ", "", regex=False)
        s = s.str.replace(",", ".", regex=False)
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    return s.astype("float64")
