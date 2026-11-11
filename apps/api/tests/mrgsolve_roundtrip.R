# Simulate an exported model.cpp with mrgsolve at the times of a reference curve (model kit M7).
# usage: Rscript mrgsolve_roundtrip.R DIR   (DIR holds model.cpp and ref.json; writes out.json)
args <- commandArgs(trailingOnly = TRUE)
suppressPackageStartupMessages({ library(mrgsolve); library(jsonlite) })
ref <- fromJSON(file.path(args[1], "ref.json"))
mod <- mread("model", args[1], quiet = TRUE)
ii <- if (is.null(ref$interval_h)) 0 else ref$interval_h
addl <- ref$doses - 1
e <- ev(amt = ref$dose, cmt = "GUT", ii = ii, addl = addl)
out <- as.data.frame(mrgsim_e(mod, e, end = -1, add = ref$times))
out <- out[!duplicated(out$time), ]
cp <- approx(out$time, out$CP, xout = ref$times)$y
write_json(list(cp = cp, mrgsolve = as.character(packageVersion("mrgsolve"))), file.path(args[1], "out.json"), digits = NA)
