python -c "p=r'sql/Amundi_Frais_detaille_GPC_refactor.sql'; b=open(p,'rb').read(); pos=1418; print('Ligne:', b[:pos].count(b'\n')+1); print('Contenu:', b.splitlines()[b[:pos].count(b'\n')].decode('cp1252'))"

# MOA Helper

Outils et requêtes MOA autour de GP / FIXFEE / PRIIPS.

## Requête FIXFEE refactorée

La requête `requete_refactor_balises.sql` produit le détail des frais PRIIPS d'un portefeuille / d'une part à une date d'arrêté à partir des tableaux techniques FIXFEE de GP.

### Vue synthétique

La chaîne fonctionnelle est la suivante :

```text
PRIIPS : portefeuille / part / date
              |
              v
Cumuls réglementaires
CHG_INI / CHG_OTH / EMT_INI / EMT_OTH
              |
              | paramétrage FCEL
              v
Balises contribuant au cumul
              |
              | paramétrage MAJCEL
              v
Tableau FIXFEE physique à lire
              |
              +-- FEE-DF : fin de période / portefeuille
              +-- FEE-DP : fin de période / part
              +-- FEE-PF : périodes / portefeuille
              +-- FEE-PP : périodes / part
              |
              v
CONTENU_TABLEAU
montant global de la balise
              |
              v
JUSTIFICATIF_TABLEAU
passerelle vers le détail
              |
              v
CONTENU_TABLEAU_DETAIL
lignes de frais
              |
              v
DESCRIPTIF_POSTE
identification du poste
              |
              v
Montant du poste + Average Assets
              |
              v
FEE_BALANCE / Average Assets
              |
              +-- CHG_* -> EX-ANTE
              +-- EMT_* -> EX-POST
              |
              v
Contrôle montant global / somme des détails
```

En une phrase : la requête transforme le paramétrage technique des tableaux FIXFEE de GP en une restitution métier PRIIPS des frais, ventilée par portefeuille, part, cumul, balise et poste de frais, calcule les taux ex-ante/ex-post puis contrôle la cohérence entre le montant global et son détail.

## Lecture détaillée des CTE

### 1. `auto_controle`

Active ou désactive le contrôle de cohérence final. Lorsque l'auto-contrôle est actif, certains écarts entre le montant global d'une balise et la somme de ses postes sont signalés.

### 2. `arrete`

Définit la date d'arrêté et le type de reporting PRIIPS. Le littéral de date porte le marqueur `TNR_DATE`, utilisé par le script de TNR pour rejouer la requête sur plusieurs arrêtés.

### 3. `parametrage_coordonnees_fixfee`

Centralise les coordonnées techniques utilisées dans les tableaux FIXFEE : colonne de balise, colonne d'identification du poste, décalages vers les montants de détail, lignes/colonnes d'Average Assets et de Last Management Fee Base.

Le but est d'éviter des « nombres magiques » dispersés dans la requête et de rendre les dépendances à la structure GP identifiables.

La documentation NeoXam permet notamment d'interpréter certaines coordonnées des périodes fixes : R12M est en colonne 4, R36M en colonne 5 et R60M en colonne 6.

### 4. `portefeuilles`

Détermine le périmètre des portefeuilles à traiter à partir du paramétrage GP.

### 5. `parametrage_cumul_1`

Détermine les cumuls PRIIPS à restituer et exploite le paramétrage FCEL pour les rattacher à leur configuration :

| Cumul | Signification | Restitution |
|---|---|---|
| `CHG_INI` | Initial transaction costs | EX-ANTE |
| `CHG_OTH` | Other ongoing costs | EX-ANTE |
| `EMT_INI` | Initial transaction costs ex post | EX-POST |
| `EMT_OTH` | Ongoing costs ex post | EX-POST |

La logique fonctionnelle est donc : **cumul réglementaire -> paramétrage FCEL -> balises FIXFEE**.

### 6. `contexte_priips`

Construit le contexte de travail à la granularité portefeuille / part / date d'arrêté / reporting PRIIPS. Le code part est extrait du code tableau GP.

### 7. `tables_fixfee`

Inventorie les tables FIXFEE disponibles pour le contexte PRIIPS.

Les quatre familles forment deux axes fonctionnels :

| | Portefeuille | Part / Share class |
|---|---|---|
| Fin de période | `FEE-DF` | `FEE-DP` |
| Sur périodes | `FEE-PF` | `FEE-PP` |

Les `SUBSTR` présents dans ce CTE décodent la nomenclature technique des codes de tables GP. Cette logique est volontairement concentrée ici.

### 8. `parametrage_cumul`

Rattache au contexte PRIIPS les tables FIXFEE physiques réellement disponibles. Les colonnes `level_fee_*` donnent le code de table GP à utiliser pour chacun des quatre niveaux de calcul.

### 9. `parametrage_majcel_config`

Interprète le paramétrage `MAJCEL / FIXFEE` de `PARAMETRE_CHAMP_CONDITION`.

Les critères permettent notamment d'identifier :

- la famille/table FIXFEE ;
- la balise ;
- la colonne portant le montant.

La famille logique est traduite en table physique du portefeuille à partir des `level_fee_*`. Des traitements particuliers existent notamment pour `SWING_COST`, `FEEDP*` et `FEEPP*`.

### 10. `parametrage_majcel`

Localise physiquement la balise dans `CONTENU_TABLEAU`.

La colonne de balise permet de récupérer `numero_ligne_ct`. Le `code_tableau_detail` indique ensuite quel tableau de détail doit être parcouru.

La requête traduit les codes techniques en niveaux de calcul lisibles :

- `DET-FEEDF` : Fee Data on Period End - By Portfolio ;
- `DET-FEEDP` : Fee Data on Period End - By Shareclass ;
- `DET-FEEPF` : Fee Data on Periods - By Portfolio ;
- `DET-FEEPP` : Fee Data on Periods - By Shareclass.

### 11. `balises_fixfee`

Lit le montant global de la balise dans `CONTENU_TABLEAU`.

`JUSTIFICATIF_TABLEAU` fournit `numero_ligne_detail`, qui constitue la passerelle entre le tableau principal et son tableau de détail.

### 12. `detail_balises_fixfee`

Descend dans `CONTENU_TABLEAU_DETAIL` pour retrouver les lignes composant la balise.

On y récupère notamment :

- le contenu permettant d'identifier le poste ;
- le montant de détail standard ;
- le montant spécifique utilisé dans le cas `DET-FEEDP`.

La structure des tableaux de détail est une structure générique GP par lignes et colonnes ; les coordonnées utiles sont donc explicitement paramétrées.

### 13. `postes_fixfee`

Rattache les cellules de détail à `DESCRIPTIF_POSTE`.

Le contenu GP n'étant pas une clé directement exploitable, des expressions régulières extraient le code valeur. Deux rattachements sont conservés :

- `dp` : recherche par code valeur ;
- `dp2` : recherche par code valeur + catégorie valeur afin de lever les ambiguïtés.

Cette double recherche est importante : un même code valeur peut exister dans plusieurs catégories.

### 14. `all_balises_fixfee`

Construit les principales mesures fonctionnelles.

**`MONTANT_BALISE_CUMUL`** est le montant global porté par la balise dans le tableau principal. Un forçage GP numérique est prioritaire sur le contenu standard.

**`MONTANT_POSTE`** est le montant d'une ligne détaillée de frais. Des règles particulières existent notamment pour `SWING_COST` et `DET-FEEDP`.

Le CTE prépare également les données nécessaires au choix de l'Average Asset / base de calcul.

### 15. `all_balises_fixfee_with_average_asset`

Sélectionne l'assiette pertinente en fonction du niveau de calcul et du cumul.

Selon le cas, la requête utilise notamment les valeurs R12M, R36M ou la Last Management Fee Base. Cette assiette servira au calcul du taux de frais.

### 16. `aa_poste_montant_fixfee`

Agrège les différentes lignes pouvant contribuer au même poste de frais.

La somme produit `FEE_BALANCE`. Le cas `SUB_FEES` fait l'objet d'une inversion de signe conformément à la logique existante.

### 17. `tableau_detail_fixfee_1`

Construit la restitution métier.

Le taux de frais est calculé selon :

```text
FEE_BALANCE
----------- x 100
AVERAGE_ASSETS
```

avec un arrondi à six décimales.

Les cumuls `CHG_INI` et `CHG_OTH` alimentent l'EX-ANTE ; les cumuls `EMT_INI` et `EMT_OTH` alimentent l'EX-POST.

### 18. `tableau_detail_fixfee`

Applique le filtre fonctionnel final. Les cumuls EMT ex-post ne sont retenus que lorsque le calcul n'est pas estimé (`CALCUL_ESTIME = 'NO'`). Les cumuls CHG sont conservés selon la règle existante.

### 19. `tableau_detail_fixfee_controle`

Effectue la réconciliation entre le montant global de la balise et la somme des postes détaillés.

Une fonction analytique :

```sql
SUM(FEE_BALANCE) OVER (PARTITION BY ...)
```

permet de calculer la somme des détails **sans perdre les lignes individuelles**, contrairement à un `GROUP BY`.

Pour les cas contrôlés, notamment `NEG_INT` et `SUB_FEES`, lorsque `AUTO_CONTROLE = 'YES'`, un écart supérieur à 0,1 entre le montant global et la somme des détails génère le message :

```text
ERR:MONTANT GLOBAL DIFFERENT SOMME DETAILS
```

## Grille de lecture MOA

Pour reprendre ou diagnostiquer la requête, suivre toujours cet ordre :

1. Quel portefeuille, quelle part et quelle date ?
2. Quel cumul PRIIPS doit être produit ?
3. Quel paramétrage FCEL porte ce cumul ?
4. Quelles balises MAJCEL contribuent au cumul ?
5. Quelle table FIXFEE physique doit être lue ?
6. Où se trouve la balise dans `CONTENU_TABLEAU` ?
7. Quel est son montant global ?
8. Quel `JUSTIFICATIF_TABLEAU` conduit au détail ?
9. Quels postes composent ce détail ?
10. Quel montant est affecté à chaque poste ?
11. Quelle Average Asset / base de calcul faut-il utiliser ?
12. Quel taux EX-ANTE ou EX-POST en résulte ?
13. Le montant global est-il cohérent avec la somme des détails ?

## TNR

Le script `utils/tnr_sql.py` compare la requête de référence et la requête refactorée sur plusieurs dates d'arrêté.

Il contrôle notamment :

- les colonnes retournées ;
- le nombre de lignes ;
- les lignes comme multiset ;
- les valeurs numériques avec tolérance.

Le mode cache permet de conserver les résultats de la requête de référence afin de ne relancer que la requête refactorée pendant les itérations de développement.

Exécution depuis la racine du repository :

```powershell
python -m utils.tnr_sql --cache
```

Le principe de refactoring est de conserver l'iso-fonctionnalité : une modification structurelle n'est considérée comme validée qu'après un TNR sans écart.
