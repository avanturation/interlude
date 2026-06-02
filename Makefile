SRCDIR   := $(abspath $(lastword $(MAKEFILE_LIST))/..)
VERSION  := $(shell cat version.txt)
DISTDIR  := build/InterCJK-$(VERSION)

INTER_VERSION      := 4.1
PRETENDARD_VERSION := 1.3.9
PRETENDARD_CSS     := build/pretendardvariable-jp-dynamic-subset.css

default: all

all: fonts web

# =================================================================================
# CORE: Variable font (single source of truth for everything else)
# =================================================================================

build/InterCJKVariable.ttf: build/inter-variable.ttf build/pretendard-variable.ttf misc/build-full.py | build
	python3 misc/build-full.py $< build/pretendard-variable.ttf $@

build/inter-variable.ttf: | build
	curl -L -o build/inter.zip \
		"https://github.com/rsms/inter/releases/download/v$(INTER_VERSION)/Inter-$(INTER_VERSION).zip"
	unzip -o build/inter.zip "InterVariable.ttf" -d build/
	mv build/InterVariable.ttf $@
	rm -f build/inter.zip

build/pretendard-variable.ttf: | build
	curl -L -o build/pretendard-jp.zip \
		"https://github.com/orioncactus/pretendard/releases/download/v$(PRETENDARD_VERSION)/PretendardJP-$(PRETENDARD_VERSION).zip"
	unzip -o build/pretendard-jp.zip "public/variable/PretendardJPVariable.ttf" -d build/
	mv build/public/variable/PretendardJPVariable.ttf $@
	rm -rf build/pretendard-jp.zip build/public

$(PRETENDARD_CSS): | build
	curl -L -o $@ \
		"https://raw.githubusercontent.com/orioncactus/pretendard/main/dist/web/variable/pretendardvariable-jp-dynamic-subset.css"

# =================================================================================
# FONTS: Inter 4.1-style release (Variable TTF, Static TTF/OTF, TTC)
# =================================================================================

fonts: $(DISTDIR)/InterCJKVariable.ttf $(DISTDIR)/extras/ttf/.ok $(DISTDIR)/InterCJK.ttc

$(DISTDIR)/InterCJKVariable.ttf: build/InterCJKVariable.ttf | $(DISTDIR)
	cp $< $@
	python3 -c "import asyncio; from pathlib import Path; import east_asian_spacing as chws; asyncio.run(chws.Builder(Path('$@')).build_and_save(Path('$@')))"

$(DISTDIR)/extras/ttf/.ok: build/InterCJKVariable.ttf misc/gen-static.py | $(DISTDIR)/extras/ttf
	python3 misc/gen-static.py $< $(DISTDIR)/extras/ttf
	touch $@

$(DISTDIR)/InterCJK.ttc: $(DISTDIR)/extras/ttf/.ok
	python3 -c "\
from fontTools.ttLib import TTFont; \
from fontTools.ttLib.ttCollection import TTCollection; \
import glob; \
fonts = [TTFont(f) for f in sorted(glob.glob('$(DISTDIR)/extras/ttf/InterCJK-*.ttf')) + sorted(glob.glob('$(DISTDIR)/extras/ttf/InterCJKDisplay-*.ttf'))]; \
ttc = TTCollection(); ttc.fonts = fonts; ttc.save('$@')"
	@echo "  InterCJK.ttc: $$(du -h $@ | cut -f1)"

# =================================================================================
# WEB: woff2, CSS, dynamic-subset (for npm/CDN)
# =================================================================================

web: $(DISTDIR)/web/.ok $(DISTDIR)/web/dynamic-subset/.ok $(DISTDIR)/web/dynamic-subset-static/.ok

$(DISTDIR)/web/.ok: $(DISTDIR)/InterCJKVariable.ttf $(DISTDIR)/extras/ttf/.ok | $(DISTDIR)/web
	python3 -m fontTools ttLib.woff2 compress $(DISTDIR)/InterCJKVariable.ttf \
		-o $(DISTDIR)/web/InterCJKVariable.woff2
	@for f in $(DISTDIR)/extras/ttf/*.ttf; do \
		name=$$(basename "$$f" .ttf); \
		python3 -m fontTools ttLib.woff2 compress "$$f" -o "$(DISTDIR)/web/$$name.woff2"; \
	done
	cp misc/inter-cjk.css $(DISTDIR)/web/inter-cjk.css
	python3 -c "import re,sys;f=open(sys.argv[1]);c=f.read();f.close();m=re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/','',c);m=re.sub(r'\s+',' ',m).strip();open(sys.argv[1].replace('.css','.min.css'),'w').write(m)" $(DISTDIR)/web/inter-cjk.css
	touch $@

$(DISTDIR)/web/dynamic-subset/.ok: $(DISTDIR)/InterCJKVariable.ttf $(PRETENDARD_CSS) misc/gen-dynamic-subset.py | $(DISTDIR)/web/dynamic-subset
	python3 misc/gen-dynamic-subset.py \
		$(DISTDIR)/InterCJKVariable.ttf \
		$(PRETENDARD_CSS) \
		$(DISTDIR)/web/dynamic-subset \
		"Inter CJK Variable" \
		"inter-cjk-variable-dynamic-subset.css"
	touch $@

$(DISTDIR)/web/dynamic-subset-static/.ok: $(DISTDIR)/extras/ttf/.ok $(PRETENDARD_CSS) misc/gen-dynamic-subset-static.py | $(DISTDIR)/web/dynamic-subset-static
	python3 misc/gen-dynamic-subset-static.py \
		$(DISTDIR)/extras/ttf \
		$(PRETENDARD_CSS) \
		$(DISTDIR)/web/dynamic-subset-static
	touch $@

# =================================================================================
# DIST: npm publish-ready
# =================================================================================

dist: all
	rm -rf dist
	mkdir -p dist/variable dist/static/ttf dist/web/dynamic-subset dist/web/dynamic-subset-static dist/tailwind
	cp $(DISTDIR)/InterCJKVariable.ttf dist/variable/
	cp $(DISTDIR)/InterCJK.ttc dist/variable/
	cp $(DISTDIR)/extras/ttf/*.ttf dist/static/ttf/
	cp $(DISTDIR)/web/*.woff2 dist/web/
	cp $(DISTDIR)/web/*.css dist/web/
	cp -r $(DISTDIR)/web/dynamic-subset/* dist/web/dynamic-subset/
	cp -r $(DISTDIR)/web/dynamic-subset-static/* dist/web/dynamic-subset-static/
	cp misc/inter-cjk-tailwind.css dist/tailwind/inter-cjk.css
	cp LICENSE.txt dist/
	mkdir -p packages/next/dist/fonts
	cp dist/web/InterCJKVariable.woff2 packages/next/dist/fonts/

# =================================================================================
# PACKAGE: zip for GitHub release
# =================================================================================

package: all $(DISTDIR)/LICENSE.txt $(DISTDIR)/help.txt
	cd build && zip -r InterCJK-$(VERSION).zip InterCJK-$(VERSION)/

$(DISTDIR)/LICENSE.txt: LICENSE.txt | $(DISTDIR)
	cp $< $@

$(DISTDIR)/help.txt: misc/help.txt | $(DISTDIR)
	cp $< $@

# =================================================================================
# CHECK: QA validation
# =================================================================================

check: $(DISTDIR)/InterCJKVariable.ttf
	python3 misc/check-font.py $<
	python3 -m fontbakery check-universal $< --no-progress --succinct 2>&1 | tail -5

# =================================================================================
# SETUP / CLEAN
# =================================================================================

setup:
	pip install -r requirements.txt

build:
	mkdir -p $@

$(DISTDIR):
	mkdir -p $@

$(DISTDIR)/extras/ttf:
	mkdir -p $@

$(DISTDIR)/web:
	mkdir -p $@

$(DISTDIR)/web/dynamic-subset:
	mkdir -p $@

$(DISTDIR)/web/dynamic-subset-static:
	mkdir -p $@

clean:
	rm -rf build dist

.PHONY: default all fonts web dist package check setup clean
