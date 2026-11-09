# Time machine: httk PBPK runs (time-machine design §6.5, DP-T9). Offline; called by
# `python -m janus.timemachine.httk_job`. Writes CSV files to the output directory given as the
# first argument. Seeded. CPU only. No health data: inputs are chemical names and doses.
#
# Pearce et al. 2017, J Stat Softw 79(4), doi:10.18637/jss.v079.i04 (httk);
# Ring et al. 2017, Environ Int, doi:10.1016/j.envint.2017.06.004 (HTTK-Pop).

args <- commandArgs(trailingOnly = TRUE)
out <- args[[1]]
seed <- as.integer(args[[2]])
samples <- as.integer(args[[3]])
suppressMessages(library(httk))

pkgs <- c("httk", "deSolve", "data.table", "survey", "truncnorm", "stringr")
ver <- data.frame(
  package = c("R", pkgs),
  version = c(R.version.string, vapply(pkgs, function(p) as.character(packageVersion(p)), ""))
)
write.csv(ver, file.path(out, "versions.csv"), row.names = FALSE)

# Single oral doses for validation against published human PK (design §8.2). Doses in mg per
# person; httk's reference adult body weight is used to convert to mg/kg.
validation <- read.csv(file.path(out, "validation_input.csv"), stringsAsFactors = FALSE)
# Reference adult body weight from httk's own physiology table (not from one chemical).
bw <- as.numeric(physiology.data[physiology.data$Parameter == "Average BW", "Human"])
stopifnot(length(bw) == 1, is.finite(bw), bw > 0)
rows <- list()
for (i in seq_len(nrow(validation))) {
  v <- validation[i, ]
  times <- seq(0, v$days, by = 1 / 96)
  sol <- solve_pbtk(
    chem.name = v$chem, dose = v$dose_mg / bw, times = times, days = v$days,
    output.units = "mg/L", suppress.messages = TRUE
  )
  t_h <- sol[, "time"] * 24
  c_ng <- sol[, "Cplasma"] * 1000
  auc <- sum(diff(t_h) * (head(c_ng, -1) + tail(c_ng, -1)) / 2)
  rows[[i]] <- data.frame(
    chem = v$chem, dose_mg = v$dose_mg, bw_kg = bw, cmax_ng_ml = max(c_ng),
    tmax_h = t_h[which.max(c_ng)], auc_ng_h_ml = auc, days = v$days
  )
}
write.csv(do.call(rbind, rows), file.path(out, "validation.csv"), row.names = FALSE)

# HTTK-Pop: steady-state plasma concentration for 1 mg/kg/day, older (65-79, the oldest ages
# HTTK-Pop draws from NHANES) versus younger adults (20-50), and time to 90 % of steady state.
pop <- read.csv(file.path(out, "population_input.csv"), stringsAsFactors = FALSE)
q <- c(0.05, 0.5, 0.95)
rows <- list()
for (i in seq_len(nrow(pop))) {
  chem <- pop$chem[i]
  for (grp in list(c("older", 65, 79), c("younger", 20, 50))) {
    set.seed(seed)
    css <- calc_mc_css(
      chem.name = chem, which.quantile = q, samples = samples, model = "pbtk",
      output.units = "mg/L", daily.dose = 1, suppress.messages = TRUE,
      httkpop.generate.arg.list = list(
        method = "virtual individuals",
        agelim_years = c(as.numeric(grp[2]), as.numeric(grp[3]))
      )
    )
    rows[[length(rows) + 1]] <- data.frame(
      chem = chem, group = grp[1], age_low = as.numeric(grp[2]), age_high = as.numeric(grp[3]),
      css_p5_mg_l = css[1], css_p50_mg_l = css[2], css_p95_mg_l = css[3], samples = samples
    )
  }
}
write.csv(do.call(rbind, rows), file.path(out, "population.csv"), row.names = FALSE)

rows <- list()
for (chem in pop$chem) {
  r <- calc_css(
    chem.name = chem, daily.dose = 1, doses.per.day = 1, f = 0.1, model = "pbtk",
    output.units = "mg/L", suppress.messages = TRUE
  )
  rows[[length(rows) + 1]] <- data.frame(chem = chem, day_90pct_ss = r$the.day)
}
write.csv(do.call(rbind, rows), file.path(out, "steady_state.csv"), row.names = FALSE)
