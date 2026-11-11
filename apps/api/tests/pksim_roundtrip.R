# Load an exported PK-Sim snapshot with the Open Systems Pharmacology tools, export it again, and run a
# simulation of a completed copy (model kit M4).
# usage: Rscript pksim_roundtrip.R DIR
#   DIR holds export.json (the file as exported) and completed.json (the same compound completed with test-only
#   values, plus an individual, a protocol and a simulation). Writes DIR/proj, DIR/snap, DIR/sim and out.json.
args <- commandArgs(trailingOnly = TRUE)
dir <- args[1]
suppressPackageStartupMessages({ library(ospsuite); library(jsonlite) })
st <- ospsuite:::ospsuiteEnv
if (!isTRUE(st$initialized)) stop(paste("ospsuite .NET side not initialised:", st$loadError))
for (d in c("proj", "snap", "sim")) dir.create(file.path(dir, d), showWarnings = FALSE)
loadProjectFromSnapshot(file.path(dir, "export.json"), output = file.path(dir, "proj"))
projects <- list.files(file.path(dir, "proj"), pattern = "[.]pksim5$", full.names = TRUE)
exportProjectToSnapshot(projects, output = file.path(dir, "snap"))
runSimulationsFromSnapshot(file.path(dir, "completed.json"), output = file.path(dir, "sim"), exportCSV = TRUE)
write_json(list(
  ospsuite = as.character(packageVersion("ospsuite")),
  rsharp = as.character(packageVersion("rSharp")),
  projects = as.list(basename(projects)),
  snapshots = as.list(list.files(file.path(dir, "snap"))),
  results = as.list(list.files(file.path(dir, "sim"), pattern = "Results[.]csv$"))
), file.path(dir, "out.json"), auto_unbox = TRUE)
