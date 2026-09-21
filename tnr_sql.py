#!/usr/bin/env python3
"""TNR Oracle : compare requête originale et requête refactorée.

Les deux SQL doivent contenir le bind :date_arrete.
La connexion est celle de MOA Helper via data_access.db.get_connection.
"""
import argparse, csv, math, sys, time
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from data_access.db import get_connection

DEFAULT_ENV = "DEV"
DEFAULT_OLD_SQL = "sql/requete_originale.sql"
DEFAULT_NEW_SQL = "sql/requete_refactor.sql"
DEFAULT_OUTPUT = "tnr_results"
DEFAULT_DATES = ["30/11/2025", "28/02/2026", "31/05/2026"]
DEFAULT_TOLERANCE = 1e-6
NULL_TOKEN = "<NULL>"

def args():
    p = argparse.ArgumentParser(description="TNR Oracle OLD vs REFACTOR")
    p.add_argument("--env", "-e", default=DEFAULT_ENV)
    p.add_argument("--old", default=DEFAULT_OLD_SQL)
    p.add_argument("--new", default=DEFAULT_NEW_SQL)
    p.add_argument("--output", "-o", default=DEFAULT_OUTPUT)
    p.add_argument("--dates", nargs="+", default=DEFAULT_DATES)
    p.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    return p.parse_args()

def emit(s, report):
    print(s, flush=True); report.append(s)

def load_sql(path):
    p = Path(path)
    if not p.is_file(): raise FileNotFoundError(f"SQL introuvable : {p}")
    s = p.read_text(encoding="utf-8").strip()
    return s[:-1].rstrip() if s.endswith(";") else s

def execute(conn, sql, d):
    c = conn.cursor()
    try:
        c.execute(sql, date_arrete=d)
        return [x[0].upper() for x in c.description], c.fetchall()
    finally:
        c.close()

def canon(v, tol):
    if v is None: return NULL_TOKEN
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        x = float(v)
        if math.isnan(x): return ("NUM", "<NAN>")
        n = max(0, int(math.ceil(-math.log10(tol)))) if tol > 0 else 15
        return ("NUM", round(x, n))
    if isinstance(v, datetime): return ("DATE", v.isoformat())
    if isinstance(v, str): return ("STR", v.strip())
    return ("VAL", str(v))

def compare(oc, old, nc, new, tol):
    r = {"status":"PASS","old_only":[],"new_only":[],"old_only_count":0,
         "new_only_count":0,"column_break":oc != nc}
    if oc != nc:
        r["status"] = "FAIL"; return r
    a = Counter(tuple(canon(v,tol) for v in row) for row in old)
    b = Counter(tuple(canon(v,tol) for v in row) for row in new)
    r["old_only"] = list((a-b).items())
    r["new_only"] = list((b-a).items())
    r["old_only_count"] = sum(n for _,n in r["old_only"])
    r["new_only_count"] = sum(n for _,n in r["new_only"])
    if r["old_only_count"] or r["new_only_count"]: r["status"]="FAIL"
    return r

def cell(v):
    return str(v[1]) if isinstance(v,tuple) and len(v)==2 else ("" if v is None else str(v))

def write_break(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f,delimiter=";"); w.writerow(["OCCURRENCES"]+cols)
        for row,n in rows: w.writerow([n]+[cell(v) for v in row])

def main():
    a=args(); report=[]; summary=[]; out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    started=datetime.now()
    try:
        for d in a.dates: datetime.strptime(d,"%d/%m/%Y")
        old_sql,new_sql=load_sql(a.old),load_sql(a.new)
        emit("="*78,report); emit("TNR SQL - ORIGINAL vs REFACTOR",report); emit("="*78,report)
        emit(f"Début              : {started:%d/%m/%Y %H:%M:%S}",report)
        emit(f"Environnement      : {a.env}",report)
        emit(f"SQL original       : {Path(a.old).resolve()}",report)
        emit(f"SQL refactoré      : {Path(a.new).resolve()}",report)
        emit(f"Sortie              : {out.resolve()}",report)
        emit(f"Dates               : {', '.join(a.dates)}",report)
        emit(f"Tolérance numérique: {a.tolerance}",report)
        emit("Connexion...",report); conn=get_connection(a.env); emit("Connexion OK",report)
        try:
            for d in a.dates:
                emit("\n"+"-"*78,report); emit(f"DATE D'ARRÊTÉ : {d}",report)
                t=time.perf_counter(); oc,old=execute(conn,old_sql,d); ot=time.perf_counter()-t
                emit(f"ORIGINAL : {len(old):>8} lignes - {ot:.2f} s",report)
                t=time.perf_counter(); nc,new=execute(conn,new_sql,d); nt=time.perf_counter()-t
                emit(f"REFACTOR : {len(new):>8} lignes - {nt:.2f} s",report)
                r=compare(oc,old,nc,new,a.tolerance)
                if r["column_break"]:
                    emit("BREAK    : colonnes différentes",report)
                    emit(f"OLD : {oc}",report); emit(f"NEW : {nc}",report)
                else:
                    emit(f"OLD ONLY : {r['old_only_count']}",report)
                    emit(f"NEW ONLY : {r['new_only_count']}",report)
                emit(f"RESULTAT : {r['status']}",report)
                dd=out/d.replace("/","-")
                if r["old_only"]: write_break(dd/"old_only.csv",oc,r["old_only"])
                if r["new_only"]: write_break(dd/"new_only.csv",nc,r["new_only"])
                summary.append({"DATE_ARRETE":d,"STATUS":r["status"],"OLD_ROWS":len(old),
                    "NEW_ROWS":len(new),"DELTA_ROWS":len(new)-len(old),
                    "OLD_ONLY":r["old_only_count"],"NEW_ONLY":r["new_only_count"],
                    "OLD_SECONDS":round(ot,3),"NEW_SECONDS":round(nt,3)})
        finally: conn.close()

        fails=sum(x["STATUS"]=="FAIL" for x in summary)
        emit("\n"+"="*78,report); emit("SYNTHESE",report); emit("="*78,report)
        emit(f"{'DATE':<14} {'STATUT':<8} {'OLD':>9} {'NEW':>9} {'DELTA':>8} {'OLD ONLY':>10} {'NEW ONLY':>10}",report)
        for x in summary:
            emit(f"{x['DATE_ARRETE']:<14} {x['STATUS']:<8} {x['OLD_ROWS']:>9} {x['NEW_ROWS']:>9} "
                 f"{x['DELTA_ROWS']:>8} {x['OLD_ONLY']:>10} {x['NEW_ONLY']:>10}",report)
        emit(f"\nPASS : {len(summary)-fails} | FAIL : {fails}",report)
        emit(f"STATUT GLOBAL : {'PASS' if not fails else 'FAIL'}",report)
        with (out/"summary.csv").open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=list(summary[0].keys()),delimiter=";"); w.writeheader(); w.writerows(summary)
        (out/"rapport_tnr.txt").write_text("\n".join(report)+"\n",encoding="utf-8")
        return 0 if not fails else 1
    except Exception as e:
        emit(f"\nERREUR TECHNIQUE : {type(e).__name__}: {e}",report)
        (out/"rapport_tnr.txt").write_text("\n".join(report)+"\n",encoding="utf-8")
        return 2

if __name__=="__main__":
    sys.exit(main())
