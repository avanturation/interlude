import math
from fontTools.pens.basePen import BasePen

def flatten_contours(glyf, gn, flatness=0.6):
    g=glyf[gn]
    if g.numberOfContours<=0:return []
    g.expand(glyf)
    coords=g.coordinates;flags=g.flags;ends=g.endPtsOfContours
    out=[];start=0
    for e in ends:
        m=e-start+1
        raw=[(coords[start+i][0],coords[start+i][1],bool(flags[start+i]&1)) for i in range(m)]
        start=e+1
        pts=_insert_implied(raw)
        m=len(pts)
        if m<2: continue
        first_on=next((k for k in range(m) if pts[k][2]),None)
        if first_on is None: continue
        seq=pts[first_on:]+pts[:first_on];m=len(seq)
        poly=[];k=0
        while k<m:
            x,y,on=seq[k]
            poly.append((x,y))
            nx,ny,non=seq[(k+1)%m]
            if not non:
                ex,ey,_=seq[(k+2)%m]
                _flatten_quad(poly,(x,y),(nx,ny),(ex,ey),flatness)
                k+=2
            else:
                k+=1
        out.append(poly)
    return out

def _insert_implied(raw):
    n=len(raw)
    if n==0: return []
    if not any(on for _,_,on in raw):
        out=[]
        for i in range(n):
            x0,y0,_=raw[i];x1,y1,_=raw[(i+1)%n]
            out.append(((x0+x1)/2,(y0+y1)/2,True));out.append(raw[(i+1)%n])
        return out
    out=[]
    for i in range(n):
        cur=raw[i];nxt=raw[(i+1)%n]
        out.append(cur)
        if (not cur[2]) and (not nxt[2]):
            out.append(((cur[0]+nxt[0])/2,(cur[1]+nxt[1])/2,True))
    return out

def _flatten_quad(poly,p0,p1,p2,flat):
    n=max(2,int(_quad_dev(p0,p1,p2)/flat)+1)
    n=min(n,24)
    for j in range(1,n+1):
        t=j/n
        mt=1-t
        bx=mt*mt*p0[0]+2*mt*t*p1[0]+t*t*p2[0]
        by=mt*mt*p0[1]+2*mt*t*p1[1]+t*t*p2[1]
        poly.append((bx,by))

def _quad_dev(p0,p1,p2):
    mx,my=(p0[0]+p2[0])/2,(p0[1]+p2[1])/2
    return math.hypot(p1[0]-mx,p1[1]-my)

# ---- geometry core ----
def _wind(polys, px, py):
    # nonzero winding number of point against all contours (y-up)
    w=0
    for poly in polys:
        n=len(poly)
        for i in range(n):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
            if y1<=py:
                if y2>py and ((x2-x1)*(py-y1)-(px-x1)*(y2-y1))>0: w+=1
            else:
                if y2<=py and ((x2-x1)*(py-y1)-(px-x1)*(y2-y1))<0: w-=1
    return w

def _dedupe(poly, tol=0.4):
    out=[]
    n=len(poly)
    for i in range(n):
        x,y=poly[i]
        if out and math.hypot(x-out[-1][0],y-out[-1][1])<tol: continue
        out.append((x,y))
    while len(out)>=2 and math.hypot(out[0][0]-out[-1][0],out[0][1]-out[-1][1])<tol:
        out.pop()
    return out

def offset_contour(poly, allpolys, W, s, miter=6.0, eps=1e-6):
    poly=_dedupe(poly)
    n=len(poly)
    if n<3: return poly
    # per-edge tangent, white-pointing normal, offset distance
    edges=[]
    for i in range(n):
        x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
        ex,ey=x2-x1,y2-y1; L=math.hypot(ex,ey)
        if L<eps: continue
        tx,ty=ex/L,ey/L
        # candidate normals
        lx,ly=-ty,tx; rx,ry=ty,-tx
        mx,my=(x1+x2)/2,(y1+y2)/2
        probe=max(1.0,0.5)
        # test which side is white (winding==0)
        wl=_wind(allpolys, mx+lx*probe, my+ly*probe)
        wr=_wind(allpolys, mx+rx*probe, my+ry*probe)
        if wl==0 and wr!=0: nx,ny=lx,ly
        elif wr==0 and wl!=0: nx,ny=rx,ry
        else:
            # ambiguous; pick side with smaller |winding| (closer to white)
            nx,ny=(lx,ly) if abs(wl)<=abs(wr) else (rx,ry)
        d=W/2.0*(1.0-math.sqrt((s*nx)**2+ny**2))
        edges.append({'p':(x1,y1),'t':(tx,ty),'n':(nx,ny),'d':d})
    m=len(edges)
    if m<3: return poly
    # reconstruct vertices by intersecting adjacent offset lines
    out=[]
    for i in range(m):
        e0=edges[(i-1)%m]; e1=edges[i]
        p=e1['p']
        q0=(p[0]+e0['d']*e0['n'][0], p[1]+e0['d']*e0['n'][1])
        q1=(p[0]+e1['d']*e1['n'][0], p[1]+e1['d']*e1['n'][1])
        t0=e0['t']; t1=e1['t']
        den=t0[0]*t1[1]-t0[1]*t1[0]
        if abs(den)>eps:
            dx,dy=q1[0]-q0[0],q1[1]-q0[1]
            u=(dx*t1[1]-dy*t1[0])/den
            mxp=(q0[0]+u*t0[0], q0[1]+u*t0[1])
            mlen=math.hypot(mxp[0]-p[0],mxp[1]-p[1])
            dref=max(abs(e0['d']),abs(e1['d']),0.5)
            if mlen<=miter*dref:
                out.append(mxp)
            else:
                out.append(q0); out.append(q1)  # bevel
        else:
            if t0[0]*t1[0]+t0[1]*t1[1]>0:
                out.append(((q0[0]+q1[0])/2,(q0[1]+q1[1])/2))
            else:
                out.append(q0); out.append(q1)
    return _cleanup_collapse(out, eps)

def _cleanup_collapse(poly, eps=1e-6, passes=3):
    for _ in range(passes):
        n=len(poly)
        if n<4: break
        bad=-1
        for i in range(n):
            ax,ay=poly[i]; bx,by=poly[(i+1)%n]
            ex,ey=bx-ax,by-ay; L=math.hypot(ex,ey)
            if L<eps: bad=i; break
        if bad>=0:
            poly=poly[:bad]+poly[bad+1:]; continue
        break
    return poly

def despike(poly, min_edge=7.0, rev_cos=-0.97):
    changed=True
    while changed and len(poly)>=4:
        changed=False
        n=len(poly)
        for i in range(n):
            p=poly[(i-1)%n];c=poly[i];q=poly[(i+1)%n]
            v1x,v1y=c[0]-p[0],c[1]-p[1];v2x,v2y=q[0]-c[0],q[1]-c[1]
            l1=math.hypot(v1x,v1y);l2=math.hypot(v2x,v2y)
            if min(l1,l2)<min_edge:
                if l1<1e-6 or l2<1e-6:
                    poly=poly[:i]+poly[i+1:];changed=True;break
                cosang=(v1x*v2x+v1y*v2y)/(l1*l2)
                if cosang<rev_cos:
                    poly=poly[:i]+poly[i+1:];changed=True;break
    return poly

def _scan_white(polys, y):
    xs=[]
    for poly in polys:
        n=len(poly)
        for i in range(n):
            x1,y1=poly[i];x2,y2=poly[(i+1)%n]
            if (y1<=y<y2) or (y2<=y<y1):
                t=(y-y1)/(y2-y1);xs.append(x1+t*(x2-x1))
    xs.sort()
    return [(xs[i+1]-xs[i]) for i in range(1,len(xs)-1,2)]

def min_counter(polys):
    ys=[y for p in polys for x,y in p]
    if not ys: return 1e9
    ymin,ymax=min(ys),max(ys);span=ymax-ymin
    mc=1e9
    for r in (0.2,0.35,0.5,0.65,0.8):
        for w in _scan_white(polys, ymin+span*r):
            if w<mc: mc=w
    return mc

def cap_W(polys_scaled, W, s, floor=18.0):
    mc=min_counter(polys_scaled)
    if mc>=1e8: return W
    w_allow=(mc-floor)/(1.0-s) if (1.0-s)>1e-6 else W
    return max(0.0, min(W, w_allow))
