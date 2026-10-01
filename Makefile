# Glyphs is the source compiler. Make validates and packages its native exports.
PYTHON ?= python3
.DEFAULT_GOAL := help

help:
	@echo "Edit src/Interlude.glyphspackage and Export Variable TrueType TTF + WOFF2 to fonts/."
	@echo "make record-export   Validate and record a fresh Glyphs export"
	@echo "make check           Verify version, source/export hashes and font regressions"
	@echo "make dist / all      Generate web subsets, static web fonts and npm files"
	@echo "make fonts           Generate 54 static TTFs and the TTC"
	@echo "make package         Build desktop + web release ZIPs (version.txt)"
	@echo "make test            Run packaging tests and native-font checks"

all: dist

record-export:
	$(PYTHON) tools/check.py --record

check:
	$(PYTHON) tools/check.py

web: check
	$(PYTHON) tools/release.py web

static: check
	$(PYTHON) tools/static_fonts.py fonts/InterludeVariable.ttf build/static

fonts: static
	$(PYTHON) tools/release.py ttc

dist: web
	$(PYTHON) tools/release.py dist

# Keep this serial: web and desktop share the same static-instance cache.
package: dist
	$(MAKE) fonts PYTHON="$(PYTHON)"
	$(PYTHON) tools/release.py package

test: check
	$(PYTHON) -m unittest discover -s tests -v

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('build', 'dist', 'packages/next/dist/fonts')]"

.PHONY: help all record-export check web static fonts dist package test clean
