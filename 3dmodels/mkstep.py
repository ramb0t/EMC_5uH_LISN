#!/usr/bin/env python3
"""Minimal AP214 STEP writer for simple 3D models: coloured, extruded convex polygons.

Each solid is a convex polygon (CCW, in mm, model XY) extruded from z0 to z1.
Planar faces only, so any STEP reader (OpenCASCADE in KiCad) loads it.
Standard library only.
"""
import math


class Step:
    def __init__(self):
        self.lines = []

    def add(self, s):
        self.lines.append(s)
        return f"#{len(self.lines)}"

    def pt(self, p):
        return self.add("CARTESIAN_POINT('',(%s));" % ",".join(f"{v:.6f}" for v in p))

    def dir(self, d):
        return self.add("DIRECTION('',(%s));" % ",".join(f"{v:.6f}" for v in d))

    def axis(self, origin, z, x):
        return self.add(f"AXIS2_PLACEMENT_3D('',{self.pt(origin)},{self.dir(z)},{self.dir(x)});")


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def prism(st, poly, z0, z1):
    """Return MANIFOLD_SOLID_BREP id for polygon poly (CCW) extruded z0..z1."""
    n = len(poly)
    B = [(x, y, z0) for x, y in poly]
    T = [(x, y, z1) for x, y in poly]
    vb = [st.add(f"VERTEX_POINT('',{st.pt(p)});") for p in B]
    vt = [st.add(f"VERTEX_POINT('',{st.pt(p)});") for p in T]

    def edge(v1, v2, p1, p2):
        d = _norm(tuple(b - a for a, b in zip(p1, p2)))
        vec = st.add(f"VECTOR('',{st.dir(d)},1.);")
        line = st.add(f"LINE('',{st.pt(p1)},{vec});")
        return st.add(f"EDGE_CURVE('',{v1},{v2},{line},.T.);")

    eb = [edge(vb[i], vb[(i + 1) % n], B[i], B[(i + 1) % n]) for i in range(n)]
    et = [edge(vt[i], vt[(i + 1) % n], T[i], T[(i + 1) % n]) for i in range(n)]
    ev = [edge(vb[i], vt[i], B[i], T[i]) for i in range(n)]

    def oe(e, fwd):
        return st.add(f"ORIENTED_EDGE('',*,*,{e},{'.T.' if fwd else '.F.'});")

    def face(oes, origin, normal, ref):
        loop = st.add(f"EDGE_LOOP('',({','.join(oes)}));")
        bound = st.add(f"FACE_OUTER_BOUND('',{loop},.T.);")
        plane = st.add(f"PLANE('',{st.axis(origin, normal, ref)});")
        return st.add(f"ADVANCED_FACE('',({bound}),{plane},.T.);")

    faces = [
        face([oe(eb[i], False) for i in reversed(range(n))], B[0], (0, 0, -1), (1, 0, 0)),
        face([oe(et[i], True) for i in range(n)], T[0], (0, 0, 1), (1, 0, 0)),
    ]
    for i in range(n):
        j = (i + 1) % n
        dx, dy = poly[j][0] - poly[i][0], poly[j][1] - poly[i][1]
        faces.append(face([oe(eb[i], True), oe(ev[j], True), oe(et[i], False), oe(ev[i], False)],
                          B[i], _norm((dy, -dx, 0)), _norm((dx, dy, 0))))
    shell = st.add(f"CLOSED_SHELL('',({','.join(faces)}));")
    return st.add(f"MANIFOLD_SOLID_BREP('',{shell});")


def box(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def ngon(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def write(path, name, solids):
    """solids: list of (polygon, z0, z1, (r, g, b))."""
    st = Step()
    ctx_app = st.add("APPLICATION_CONTEXT('core data for automotive mechanical design processes');")
    st.add(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,{ctx_app});")
    pctx = st.add(f"PRODUCT_CONTEXT('',{ctx_app},'mechanical');")
    prod = st.add(f"PRODUCT('{name}','{name}','',({pctx}));")
    pdf = st.add(f"PRODUCT_DEFINITION_FORMATION('','',{prod});")
    pdc = st.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',{ctx_app},'design');")
    pd = st.add(f"PRODUCT_DEFINITION('design','',{pdf},{pdc});")
    pds = st.add(f"PRODUCT_DEFINITION_SHAPE('','',{pd});")
    lu = st.add("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );")
    au = st.add("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) );")
    su = st.add("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() );")
    unc = st.add(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),{lu},'distance_accuracy_value','');")
    ctx = st.add(f"( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({unc})) "
                 f"GLOBAL_UNIT_ASSIGNED_CONTEXT(({lu},{au},{su})) REPRESENTATION_CONTEXT('',''));")
    origin = st.axis((0, 0, 0), (0, 0, 1), (1, 0, 0))
    breps, styled = [], []
    for poly, z0, z1, rgb in solids:
        b = prism(st, poly, z0, z1)
        breps.append(b)
        col = st.add("COLOUR_RGB('',%.4f,%.4f,%.4f);" % rgb)
        fac = st.add(f"FILL_AREA_STYLE_COLOUR('',{col});")
        fas = st.add(f"FILL_AREA_STYLE('',({fac}));")
        ssf = st.add(f"SURFACE_STYLE_FILL_AREA({fas});")
        sss = st.add(f"SURFACE_SIDE_STYLE('',({ssf}));")
        ssu = st.add(f"SURFACE_STYLE_USAGE(.BOTH.,{sss});")
        psa = st.add(f"PRESENTATION_STYLE_ASSIGNMENT(({ssu}));")
        styled.append(st.add(f"STYLED_ITEM('color',({psa}),{b});"))
    rep = st.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',({origin},{','.join(breps)}),{ctx});")
    st.add(f"SHAPE_DEFINITION_REPRESENTATION({pds},{rep});")
    st.add(f"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join(styled)}),{ctx});")
    head = ("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('simplified model'),'2;1');\n"
            f"FILE_NAME('{name}.step','2026-11-04T00:00:00',(''),(''),'mkstep.py','mkstep.py','');\n"
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n")
    body = "".join(f"#{i}={s}\n" for i, s in enumerate(st.lines, start=1))
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(head + body + "ENDSEC;\nEND-ISO-10303-21;\n")
