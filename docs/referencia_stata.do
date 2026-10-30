* Stata reference, outside the pipeline. Extract Sumaria-2024.csv from the module 34 zip as sumaria2024.csv next to this file.
* Reference only, outside the pipeline: design-based poverty 2024 to contrast with brillo/enaho.py
clear all
set more off
log using ref_out.log, text replace
import delimited using "sumaria2024.csv", clear encoding("latin1") stringcols(_all)
destring pobreza factor07 mieperho, replace force
gen dep = substr("000000" + strtrim(ubigeo), -6, 2)
keep if !missing(pobreza) & !missing(factor07) & mieperho > 0
gen poor = pobreza <= 2
gen w = factor07 * mieperho
encode dep, gen(idep)
svyset conglome [pweight=w], strata(estrato) singleunit(certainty)
svy: mean poor
svy: mean poor, over(idep)
matrix b = e(b)
matrix V = e(V)
tempname out
file open `out' using "ref_dep.csv", write replace
file write `out' "dep,rate,se" _n
levelsof idep, local(levels)
local i = 1
foreach l of local levels {
    local name : label (idep) `l'
    file write `out' "`name'," (b[1,`i']) "," (sqrt(V[`i',`i'])) _n
    local ++i
}
file close `out'
log close
