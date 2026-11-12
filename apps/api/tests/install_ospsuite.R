# Install the pinned Open Systems Pharmacology R packages for the PK-Sim check (model kit M4).
# ospsuite 12.4.5 bundles PK-Sim core 12.3.173 (GPL-2.0) and needs a .NET 8 runtime on the machine.
# The two packages that matter most (ospsuite, rSharp) come from the project's GitHub release, checked against a
# sha256; the rest resolve from the OSP package universe and the dated CRAN snapshot of the R image. A newer
# release of a dependency in the universe fails the version check on purpose: bump the pins deliberately.
lib <- Sys.getenv("R_LIBS_USER")
if (!nzchar(lib)) stop("R_LIBS_USER must name the library directory")
dir.create(lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib, .libPaths()))
pins <- c(ospsuite = "12.4.5", rSharp = "1.2.3", ospsuite.utils = "1.11.1", tlf = "1.6.2", ospsuite.plots = "1.3.0")
assets <- list(
  rSharp = list(
    url = "https://github.com/Open-Systems-Pharmacology/rSharp/releases/download/v1.2.3/rSharp_1.2.3_R_x86_64-pc-linux-gnu.tar.gz",
    sha256 = "0bc455f7d04319330d92d859b092956ffe63e2fbb8fff68073aa935cb6e2895b"
  ),
  ospsuite = list(
    url = "https://github.com/Open-Systems-Pharmacology/OSPSuite-R/releases/download/v12.4.5/ospsuite_12.4.5_R_x86_64-pc-linux-gnu.tar.gz",
    sha256 = "53bcc3f95e80a4ba49bd3e5afe062f158542ce0d626ad1f459d41438f1187ccd"
  )
)
version_ok <- function(p) requireNamespace(p, quietly = TRUE) && as.character(packageVersion(p)) == pins[[p]]
if (!all(vapply(names(pins), version_ok, logical(1)))) {
  options(
    repos = c(OSP = "https://open-systems-pharmacology.r-universe.dev", CRAN = getOption("repos")[["CRAN"]]),
    Ncpus = 2
  )
  # dependencies (and the newest OSP packages) first, then the pinned release files over them
  install.packages(c("ospsuite", "jsonlite"))
  for (p in names(assets)) {
    f <- tempfile(fileext = ".tar.gz")
    download.file(assets[[p]]$url, f, mode = "wb", quiet = TRUE)
    got <- unname(tools::sha256sum(f))
    if (!identical(got, assets[[p]]$sha256)) stop(sprintf("sha256 of %s differs: %s", p, got))
    st <- system2("R", c("CMD", "INSTALL", "--no-test-load", "-l", lib, f))
    if (st != 0) stop(sprintf("installing %s failed", p))
  }
}
for (p in names(pins)) {
  v <- as.character(packageVersion(p))
  cat(p, v, "\n")
  if (v != pins[[p]]) stop(sprintf("%s is %s, pinned %s", p, v, pins[[p]]))
}
