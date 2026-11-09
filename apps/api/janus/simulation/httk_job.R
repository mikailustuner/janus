# On-demand httk runs of the simulation service (simulation-service design §5, DP-S6). Called
# only by `janus.simulation.execute` with arguments built from the allow-list; every argument is
# checked again here. Owner decision 2026-11-09: only virtual populations, never one person, so
# the only run is HTTK-Pop's steady-state plasma concentration distribution at 1 mg/kg/day for
# the two predefined age ranges of virtual individuals (younger first), for their comparison (as
# in httk_run.R, time-machine DP-T9, DP-T10). No file is read or written; output goes to stdout
# as `V,<R>,<httk>`, `Q,<p5>,<p50>,<p95>` (mg/L) per age range and `H,<half-life h>`.
#
# Pearce et al. 2017, J Stat Softw 79(4), doi:10.18637/jss.v079.i04 (httk);
# Ring et al. 2017, Environ Int, doi:10.1016/j.envint.2017.06.004 (HTTK-Pop).

args <- commandArgs(trailingOnly = TRUE)
allowed <- c("Risperidone", "Metoclopramide", "Haloperidol")
num <- function(x, lo, hi) {
  v <- suppressWarnings(as.integer(x))
  if (length(v) != 1 || is.na(v) || v < lo || v > hi) stop("argument out of range")
  v
}
if (length(args) != 7) stop("usage: chem samples seed young_low young_high old_low old_high")
chem <- args[[1]]
if (!(chem %in% allowed)) stop("compound not allowed")
n <- num(args[[2]], 100, 1000)
seed <- num(args[[3]], 0, 2147483647)
ages <- list(
  c(num(args[[4]], 20, 79), num(args[[5]], 20, 79)),
  c(num(args[[6]], 20, 79), num(args[[7]], 20, 79))
)
for (a in ages) if (a[1] > a[2]) stop("age range")
suppressMessages(library(httk))
cat("V,", R.version.string, ",", as.character(packageVersion("httk")), "\n", sep = "")
for (a in ages) {
  set.seed(seed)
  css <- calc_mc_css(
    chem.name = chem, which.quantile = c(0.05, 0.5, 0.95), samples = n, model = "pbtk",
    output.units = "mg/L", daily.dose = 1, suppress.messages = TRUE,
    httkpop.generate.arg.list = list(method = "virtual individuals", agelim_years = a)
  )
  cat(sprintf("Q,%.6g,%.6g,%.6g\n", css[1], css[2], css[3]))
}
# The model's half-life of the drug (hours; package default model), shown with its error measured
# against Obach 2008 and a calibrated interval (data/simulation/calibration.json).
cat(sprintf("H,%.6g\n", calc_half_life(chem.name = chem, suppress.messages = TRUE)))
