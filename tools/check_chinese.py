"""Validate regional native exports against the source and Interlude Latin."""
from pathlib import Path
import argparse,itertools,json,hashlib,sys
import openstep_plist as plist
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.ufoLib.filenames import userNameToFileName
from source_state import ROOT, source_hash, file_hash
from versioning import RELEASE, MAJOR, FONT_MINOR, FONT_REVISION, FONT_VERSION

BASE = ROOT
REGIONS = ['SC', 'TC', 'HK']

def cjk(c):
    return any(a <= c <= b for a,b in [(0x2E80,0x303F),(0x3100,0x312F),(0x3190,0x31EF),(0x3200,0x33FF),(0x3400,0x9FFF),(0xF900,0xFAFF),(0xFE10,0xFE1F),(0xFE30,0xFE4F),(0xFF01,0xFFEF),(0x20000,0x323AF)]) and not (0xFF61 <= c <= 0xFF9F or 0xFFA0 <= c <= 0xFFDC)

def korean_kana(c):
    return any(a <= c <= b for a,b in [(0x1100,0x11FF),(0x3040,0x30FF),(0x3130,0x318F),(0x31F0,0x31FF),(0xA960,0xA97F),(0xAC00,0xD7FF),(0x1AFF0,0x1AFFF),(0x1B000,0x1B16F)]) or 0xFF61 <= c <= 0xFFDC

def han(c):
    return 0x3400 <= c <= 0x9FFF or 0xF900 <= c <= 0xFAFF or 0x20000 <= c <= 0x3347F


AXES=[('opsz',14,14,32),('wght',100,400,900)]
ALIASES=json.loads((ROOT/'docs/qa/chinese/native-name-aliases.json').read_text())

def shaper(path):
    tt=TTFont(path);font=hb.Font(hb.Face(path.read_bytes()));order=tt.getGlyphOrder()
    def shape(text,loc=None,features=None,language='en',direction=None):
        font.set_variations(loc or {'opsz':14,'wght':400})
        b=hb.Buffer();b.add_str(text);b.guess_segment_properties();b.language=language
        if direction:b.direction=direction
        hb.shape(font,b,features or {})
        return [[ALIASES.get(order[i.codepoint],order[i.codepoint]),i.cluster,p.x_advance,p.y_advance,p.x_offset,p.y_offset] for i,p in zip(b.glyph_infos,b.glyph_positions)]
    return tt,shape

def source_draw(g,mid,pen):
    l=next(l for l in g['layers'] if l['layerId']==mid);pp=PointToSegmentPen(pen)
    for s in l.get('shapes',[]):
        pp.beginPath()
        for x,y,k in s['nodes']:pp.addPoint((float(x),float(y)),segmentType={'l':'line','q':'qcurve','o':None}[k])
        pp.endPath()
    return float(l['width'])

def verify(region):
    path=ROOT/'fonts'/('Interlude'+region+'Variable.ttf');font,shape=shaper(path)
    names=font['name'];family='Interlude '+region+' Variable'
    assert names.getDebugName(1)==family,(1,names.getDebugName(1))
    assert names.getDebugName(2)=='Regular'
    assert names.getDebugName(6)=='Interlude'+region+'-Variable'
    assert abs(font['head'].fontRevision-FONT_REVISION)<.00002
    assert names.getDebugName(5).startswith(FONT_VERSION)
    assert [(a.axisTag,a.minValue,a.defaultValue,a.maxValue) for a in font['fvar'].axes]==AXES
    assert 'wdth' not in [axis.AxisTag for axis in font['STAT'].table.DesignAxisRecord.Axis]
    assert all('wdth' not in instance.coordinates for instance in font['fvar'].instances)
    assert font['OS/2'].usWeightClass==400,font['OS/2'].usWeightClass
    assert font['OS/2'].usWidthClass==5,font['OS/2'].usWidthClass
    assert (font['hhea'].ascent,font['hhea'].descent)==(2024,-532)
    src=ROOT/'src'/('Interlude'+region+'.glyphspackage')
    info=plist.loads((src/'fontinfo.plist').read_text());order=plist.loads((src/'order.plist').read_text())
    assert (int(info['versionMajor']),int(info['versionMinor'])) == (MAJOR,FONT_MINOR)
    assert not info.get('userData',{}).get('com.interlude.completeExport')
    assert int(info.get('userData',{}).get('com.interlude.nativeRefinements',0)) == 1
    assert [a['tag'] for a in info['axes']]==['opsz','wght']
    assert len(info['fontMaster']) == 6
    assert all(len(m['axesValues'])==2 for m in info['fontMaster'])
    assert all('wdth:' not in f.get('code','') for f in info.get('features',[])+info.get('featurePrefixes',[]))
    masters={m['id'] for m in info['fontMaster']}
    cmap={}
    for n in order:
        g=plist.loads((src/'glyphs'/(userNameToFileName(n)+'.glyph')).read_text());us=g.get('unicode',[])
        assert {layer['layerId'] for layer in g['layers']} == masters,n
        for c in us if isinstance(us,list) else [us]:
            assert int(c) not in cmap,('Duplicate Unicode',c,n,cmap.get(int(c)))
            cmap[int(c)]=n
        if any(han(int(c)) for c in (us if isinstance(us,list) else [us])):
            topology={tuple(tuple(str(x[2]) for x in shape.get('nodes',[])) if 'nodes' in shape else ('component',shape.get('ref')) for shape in layer.get('shapes',[])) for layer in g['layers']}
            assert len(topology) == 1,('Incompatible Chinese masters',n)
    actual=font.getBestCmap();assert set(actual)==set(cmap),{'missing':sorted(set(cmap)-set(actual)),'extra':sorted(set(actual)-set(cmap))}
    assert not any(korean_kana(c) for c in actual)
    required={'calt','rlig','case','ccmp','kern','mark','mkmk','frac','tnum','pnum','numr','dnom','zero','vert','vrt2','halt','palt','vhal','vpal'}
    tags={r.FeatureTag for t in ['GSUB','GPOS'] for r in font[t].table.FeatureList.FeatureRecord}
    assert required<=tags,required-tags
    baseline,base_shape=shaper(BASE/'fonts/InterludeVariable.ttf')
    assert ('MVAR' in font)==('MVAR' in baseline),'Decoration metrics differ from the native baseline'
    cases=json.loads((BASE/'tests/expected-font.json').read_text())['shaping']
    latin_cases=0;max_position_error=0
    for case in cases:
        if case['location'].get('wdth',100)!=100:continue
        text=case['text']
        if any(cjk(ord(c)) or korean_kana(ord(c)) or ord(c) not in actual for c in text):continue
        a=base_shape(text,case['location'],case['features'],case['language']);b=shape(text,{k:v for k,v in case['location'].items() if k!='wdth'},case['features'],case['language'])
        assert len(a)==len(b),(text,a,b)
        for aa,bb in zip(a,b):
            assert aa[:2]==bb[:2],(text,aa,bb)
            e=max(abs(x-y) for x,y in zip(aa[2:],bb[2:]));max_position_error=max(max_position_error,e)
            assert e<=1,(text,case['location'],case['features'],aa,bb)
        latin_cases+=1
    outline_cases=0;max_bounds_error=0;max_area_error=0
    sample='一中口日木国國骨直令述返里字体體与與测试測試开发開發软件軟體时间時間臺灣香港澳門廣東話鬱龘𠮷'
    for m in info['fontMaster']:
        loc=dict(zip(['opsz','wght'],map(float,m['axesValues'])));gs=font.getGlyphSet(location=loc)
        for c in sample:
            cp=ord(c)
            if cp not in cmap:continue
            g=plist.loads((src/'glyphs'/(userNameToFileName(cmap[cp])+'.glyph')).read_text())
            expected=BoundsPen(None);width=source_draw(g,m['id'],expected)
            got=BoundsPen(gs);glyph=gs[actual[cp]];glyph.draw(got)
            assert abs(glyph.width-width)<=1,(c,loc,glyph.width,width)
            e=max(abs(x-y) for x,y in zip(expected.bounds,got.bounds));max_bounds_error=max(max_bounds_error,e)
            assert e<=1.1,(c,loc,expected.bounds,got.bounds)
            area_a=AreaPen(None);source_draw(g,m['id'],area_a);area_b=AreaPen(gs);gs[actual[cp]].draw(area_b)
            e=abs(abs(area_a.value)-abs(area_b.value))/max(1,abs(area_a.value));max_area_error=max(max_area_error,e)
            assert e<.004,(c,loc,e)
            outline_cases+=1
    for o,w in itertools.product([14,32],range(100,901,100)):
        loc={'opsz':o,'wght':w}
        for text in ['1:29','12:34','00:59','123:456']:
            result=shape(text,loc,{'calt':False})
            assert any('colon.case' in row[0] for row in result),(text,loc,result)
        expected=1920
        assert abs(shape('中',loc,language='zh')[0][2]-expected)<=1,(loc,shape('中',loc,language='zh'))
    for text in ['字體與介面','臺灣香港澳門','ㄅㄆㄇㄈ','ㄅ\u0301ㄆ\u0300ㄇ\u030c','中文，。「」（）']:
        for direction in ['ltr','ttb']:
            r=shape(text,language='zh',direction=direction)
            assert all(x[0]!='.notdef' for x in r),(text,direction,r)
    if info.get('userData',{}).get('com.interlude.nativeRefinements'):
        for o,w in itertools.product([14,32],range(100,901,100)):
            loc={'opsz':o,'wght':w}
            a=shape('）。',loc,{'chws':False,'kern':False},language='zh-TW');b=shape('）。',loc,{'chws':True,'kern':False},language='zh-TW')
            assert sum(x[2] for x in b)-sum(x[2] for x in a)==-960,(loc,a,b)
            vertical=shape('中',loc,language='zh-TW',direction='ttb')
            assert vertical[0][3]==-2048 and vertical[0][5]==-1761,vertical
            for text in ['ㄧˊ','ㄧ\u0301','ㄨˋ','ㄨ\u0300','ㄩˇ','ㄩ\u030c','ㄧ˪','ㄧ˫']:
                for direction in ['ltr','ttb']:
                    shaped=shape(text,loc,language='zh-TW',direction=direction)
                    assert any(x[0].startswith('zhTone') for x in shaped),(text,loc,direction,shaped)
                    assert shaped[1][4]!=0 and shaped[1][5]!=0,(text,loc,direction,shaped)
    woff=path.with_suffix('.woff2');wf=TTFont(woff)
    assert wf.getBestCmap()==actual
    assert abs(wf['head'].fontRevision-FONT_REVISION)<.00002
    assert wf['name'].getDebugName(5).startswith(FONT_VERSION)
    # Compare original table bytes, rather than a decompile/recompile round trip.
    for tag in ['GSUB','GPOS','GDEF','gvar','fvar','avar']+(['MVAR'] if 'MVAR' in font else []):assert wf.reader[tag]==font.reader[tag],tag
    result={'region':region,'family':family,'compiler':'Glyphs 4.1.1 (4108), native Variable TrueType Export','axes':AXES,'codepoints':len(actual),'glyphs':len(font.getGlyphOrder()),'latinShapingCases':latin_cases,'maxLatinPositionError':max_position_error,'outlineMasterCases':outline_cases,'maxBoundsError':max_bounds_error,'maxAreaError':max_area_error,'featureTags':sorted(tags),'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [path,woff]}}
    result.update({'numericColonCases':72,'chineseWidthCases':18,'punctuationWidthCases':18,'verticalOriginCases':18,'bopomofoCases':288,'fixedWidth':100})
    result.update({'release':RELEASE,'sourceSHA256':source_hash(src),'baselineSHA256':file_hash(BASE/'fonts/InterludeVariable.ttf')})
    font.close();wf.close();baseline.close()
    print(region,'native source, names, axes, versions, layout and outlines verified',flush=True)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--record',action='store_true',help='Record checked native exports and source hashes')
    args=parser.parse_args()
    actual={'release':RELEASE,'regions':{r:verify(r) for r in REGIONS}}
    actual=json.loads(json.dumps(actual))
    path=ROOT/'fonts/chinese-export-manifest.json'
    if args.record:
        path.write_text(json.dumps(actual,indent=2)+'\n')
        print('Recorded regional native export manifest')
    else:
        assert actual==json.loads(path.read_text()),'Chinese source/export mismatch; export in Glyphs and run make record-chinese-export'
        print('All three Chinese native source/export records match')

if __name__=='__main__':main()
