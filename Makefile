SRCDIR   := $(abspath $(lastword $(MAKEFILE_LIST))/..)
VERSION  := $(shell cat version.txt)
DISTDIR  := build/Interlude-$(VERSION)

INTER_VERSION      := 4.1
PRETENDARD_VERSION := 1.3.9
PRETENDARD_CSS     := build/pretendardvariable-jp-dynamic-subset.css

# OS detection for font installation target
ifeq ($(OS),Windows_NT)
    FONT_INSTALL_DIR  := $(LOCALAPPDATA)/Microsoft/Windows/Fonts
    FONT_POST_INSTALL := echo "  Windows: 사용자 폰트 폴더에 복사 완료. 자동 등록 안 되면 .ttf 우클릭 > 설치하세요."
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        FONT_INSTALL_DIR  := $(HOME)/Library/Fonts
        FONT_POST_INSTALL := echo "  macOS: $(HOME)/Library/Fonts 에 설치 완료."
    else
        FONT_INSTALL_DIR  := $(HOME)/.local/share/fonts
        FONT_POST_INSTALL := fc-cache -f "$(HOME)/.local/share/fonts" && echo "  Linux: 폰트 캐시 갱신 완료."
    endif
endif

default: all

all: fonts web install

# =================================================================================
# CORE: Variable font (single source of truth for everything else)
# =================================================================================

build/InterludeVariable.ttf: build/InterludeVariable-base.ttf misc/add-wdth-axis.py misc/wdth_sfpro_cps.py | build
	python3 misc/add-wdth-axis.py $< $@

build/InterludeVariable-base.ttf: build/inter-variable.ttf build/pretendard-variable.ttf misc/build-full.py | build
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

fonts: $(DISTDIR)/InterludeVariable.ttf $(DISTDIR)/ttf/.ok $(DISTDIR)/otf/.ok $(DISTDIR)/Interlude.ttc

$(DISTDIR)/InterludeVariable.ttf: build/InterludeVariable.ttf | $(DISTDIR)
	cp $< $@
	python3 -c "import asyncio; from pathlib import Path; import east_asian_spacing as chws; asyncio.run(chws.Builder(Path('$@')).build_and_save(Path('$@')))"

$(DISTDIR)/ttf/.ok: build/InterludeVariable.ttf misc/gen-static.py | $(DISTDIR)/ttf
	python3 misc/gen-static.py $< $(DISTDIR)/ttf
	touch $@

$(DISTDIR)/otf/.ok: $(DISTDIR)/ttf/.ok misc/gen-otf.py | $(DISTDIR)/otf
	python3 misc/gen-otf.py $(DISTDIR)/ttf $(DISTDIR)/otf
	touch $@

$(DISTDIR)/Interlude.ttc: $(DISTDIR)/ttf/.ok
	python3 -c "\
from fontTools.ttLib import TTFont; \
from fontTools.ttLib.ttCollection import TTCollection; \
import glob; \
g = lambda p: sorted(glob.glob('$(DISTDIR)/ttf/' + p)); \
text = g('Interlude-*.ttf') + g('InterludeCondensed-*.ttf') + g('InterludeExpanded-*.ttf'); \
disp = g('InterludeDisplay-*.ttf') + g('InterludeDisplayCondensed-*.ttf') + g('InterludeDisplayExpanded-*.ttf'); \
fonts = [TTFont(f) for f in text + disp]; \
ttc = TTCollection(); ttc.fonts = fonts; ttc.save('$@')"
	@echo "  Interlude.ttc: $$(du -h $@ | cut -f1)"

# =================================================================================
# WEB: woff2, CSS, dynamic-subset (for npm/CDN)
# =================================================================================

web: $(DISTDIR)/woff2/.ok $(DISTDIR)/dynamic-subset/.ok

$(DISTDIR)/woff2/.ok: $(DISTDIR)/InterludeVariable.ttf $(DISTDIR)/ttf/.ok | $(DISTDIR)/woff2 $(DISTDIR)/css
	python3 -m fontTools ttLib.woff2 compress $(DISTDIR)/InterludeVariable.ttf \
		-o $(DISTDIR)/woff2/InterludeVariable.woff2
	@for f in $(DISTDIR)/ttf/Interlude-*.ttf $(DISTDIR)/ttf/InterludeDisplay-*.ttf; do \
		name=$$(basename "$$f" .ttf); \
		python3 -m fontTools ttLib.woff2 compress "$$f" -o "$(DISTDIR)/woff2/$$name.woff2"; \
	done
	cp misc/interlude.css $(DISTDIR)/css/interlude.css
	python3 -c "import re,sys;f=open(sys.argv[1]);c=f.read();f.close();m=re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/','',c);m=re.sub(r'\s+',' ',m).strip();open(sys.argv[1].replace('.css','.min.css'),'w').write(m)" $(DISTDIR)/css/interlude.css
	touch $@

$(DISTDIR)/dynamic-subset/.ok: $(DISTDIR)/InterludeVariable.ttf $(PRETENDARD_CSS) misc/gen-dynamic-subset.py | $(DISTDIR)/dynamic-subset
	python3 misc/gen-dynamic-subset.py \
		$(DISTDIR)/InterludeVariable.ttf \
		$(PRETENDARD_CSS) \
		$(DISTDIR)/dynamic-subset \
		"Interlude Variable" \
		"interlude-variable-dynamic-subset.css"
	touch $@


# =================================================================================
# DIST: npm publish-ready
# =================================================================================

dist: all
	rm -rf dist
	mkdir -p dist/variable dist/ttf dist/otf dist/woff2 dist/css dist/dynamic-subset dist/tailwind
	cp $(DISTDIR)/InterludeVariable.ttf dist/variable/
	cp $(DISTDIR)/Interlude.ttc dist/variable/
	cp $(DISTDIR)/ttf/*.ttf dist/ttf/
	cp $(DISTDIR)/otf/*.otf dist/otf/
	cp $(DISTDIR)/woff2/*.woff2 dist/woff2/
	cp $(DISTDIR)/css/*.css dist/css/
	cp -r $(DISTDIR)/dynamic-subset/* dist/dynamic-subset/
	cp misc/interlude-tailwind.css dist/tailwind/interlude.css
	cp LICENSE.txt dist/
	mkdir -p packages/next/dist/fonts
	cp dist/woff2/InterludeVariable.woff2 packages/next/dist/fonts/

# =================================================================================
# PACKAGE: zip for GitHub release
# =================================================================================

package: all $(DISTDIR)/LICENSE.txt
	cd build && zip -X -r Interlude-$(VERSION)-ttf.zip \
		Interlude-$(VERSION)/Interlude.ttc \
		Interlude-$(VERSION)/ttf/ \
		Interlude-$(VERSION)/LICENSE.txt
	cd build && zip -X -r Interlude-$(VERSION)-otf.zip \
		Interlude-$(VERSION)/otf/ \
		Interlude-$(VERSION)/LICENSE.txt
	cd build && zip -X -r Interlude-$(VERSION)-web.zip \
		Interlude-$(VERSION)/woff2/ \
		Interlude-$(VERSION)/css/ \
		Interlude-$(VERSION)/dynamic-subset/ \
		Interlude-$(VERSION)/LICENSE.txt

$(DISTDIR)/LICENSE.txt: LICENSE.txt | $(DISTDIR)
	cp $< $@

# =================================================================================
# INSTALL: 운영체제별 폰트 폴더에 설치 (macOS/Windows/Linux 자동 감지)
# =================================================================================

install: $(DISTDIR)/InterludeVariable.ttf
	@mkdir -p "$(FONT_INSTALL_DIR)"
	cp "$(DISTDIR)/InterludeVariable.ttf" "$(FONT_INSTALL_DIR)/InterludeVariable.ttf"
	@$(FONT_POST_INSTALL)

# =================================================================================
# CHECK: QA validation
# =================================================================================

check: $(DISTDIR)/InterludeVariable.ttf
	python3 misc/check-font.py $<

# =================================================================================
# SETUP / CLEAN
# =================================================================================

setup:
	pip install -r requirements.txt

build:
	mkdir -p $@

$(DISTDIR):
	mkdir -p $@

$(DISTDIR)/ttf:
	mkdir -p $@

$(DISTDIR)/otf:
	mkdir -p $@

$(DISTDIR)/woff2:
	mkdir -p $@

$(DISTDIR)/css:
	mkdir -p $@

$(DISTDIR)/dynamic-subset:
	mkdir -p $@

clean:
	rm -rf build dist

.PHONY: default all fonts web dist package check setup clean install
