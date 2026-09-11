from datetime import date, datetime, timedelta
from typing import Iterable, Union
import pandas as pd
from dateutil.relativedelta import relativedelta


DateLike = Union[str,date,datetime]

def calcul_echeance(code_duree:str,d:DateLike,jours_feries: Iterable[DateLike] | None=None ) ->pd.Timestamp:
        dec_j,dec_m=decode_duree(code_duree)
        d_ts=to_timestamp(d)
        if dec_m>0:
                date_repere=mois_decaler(d_ts,dec_m)-timedelta(days=1)

        else:
                date_repere=d_ts+timedelta(days=dec_j-1)

        result=serie_jour_ouvre(date_repere,1,jours_feries)

        return result




def decode_duree(code_duree:str):
        decalage_mois=0
        decalage_jour=0
        unite=code_duree[0]
        valeur= int(code_duree[1:])

        if code_duree[0]=="D":
                decalage_jour=valeur

        elif code_duree[0]=="M":

                decalage_mois=valeur
        elif code_duree[0]=="Y":
                decalage_mois=12*int(code_duree[1:-2])

        return decalage_jour,decalage_mois


def date_to_histo(d:date) -> int:
        return (date(1752,9,14)-d).days

def histo_to_date(h:int) -> date:
        origine=date(1752,9,14)
        h_int=int(h)
        return origine-timedelta(days=h_int)

def to_timestamp(d:DateLike)->pd.Timestamp:
        return pd.to_datetime(d)


def mois_decaler(d:DateLike,nb_mois:int)-> pd.Timestamp:

        d_ts = to_timestamp(d)

        return d_ts+relativedelta(months=nb_mois)

def serie_jour_ouvre(d:DateLike, decalage_jour_ouvre: int, jours_feries: Iterable[DateLike] | None=None ,)->pd.Timestamp:
        d_ts=to_timestamp(d)

        if jours_feries:
                jours_feries_ts=pd.to_datetime(list(jours_feries))
                offset=pd.offsets.CustomBusinessDay(holidays=jours_feries_ts)
        else:
                offset=pd.offsets.BDay()

        if decalage_jour_ouvre>=0:
                return d_ts+decalage_jour_ouvre*offset
        else:
                return d_ts+decalage_jour_ouvre*offset

date_source="2025-06-30"
date_plus_1_mois = mois_decaler(date_source,1)
jours_feries_fance=[]

jours_ouvres=serie_jour_ouvre(date_plus_1_mois,3,jours_feries_fance)
print(f"date_source :{date_source}")
print(f"date_plus_1_mois :{date_plus_1_mois}")
print(f"jours_ouvres : {jours_ouvres}")
