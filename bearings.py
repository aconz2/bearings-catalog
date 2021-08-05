import os
import sys
import csv

from subprocess import run, DEVNULL
from pathlib import Path

def remove_objects_not_in(doc, keep, type_id='PartDesign::Body'):
    rem = []
    for obj in doc.Objects:
        if obj.TypeId == type_id and obj.label not in keep:
            rem.append(obj)

    for r in rem:
        doc.removeObject(r)

def make_bearing(doc, template, id, od, width, radius, name=None):
    ret = doc.copyObject(template, True)
    sketch = [x for x in ret.Group if x.TypeId == 'Sketcher::SketchObject'][0]

    if name is None:
        name = f'{id}x{od}x{width}'
    ret.Label = name

    # l = lambda *args: print(*args, file=sys.stderr)
    # l('broken constraint is ', sketch.Constraints[24].Name)

    # l(id, od, width, radius)
    # setting_to = {'OR': od / 2, 'IR': id / 2, 'Width': width, 'Radius': radius}
    # for k in ['OR', 'IR', 'Width', 'Radius']:
    #     l('{:<8} {:<8} -> {:<8}'.format(k, str(sketch.getDatum(k)), setting_to[k]))

    # l(dir(sketch))

    sketch.setDatum('Width', width)
    sketch.setDatum('Radius', .001)  # set the radius to something very small so it doesn't affect sketch validity
    ret.recompute(True)

    set_ir = False

    def do_set_ir():
        nonlocal set_ir
        try:
            sketch.setDatum('IR', id / 8)
            ret.recompute(True)
            sketch.setDatum('IR', id / 4)
            ret.recompute(True)
            sketch.setDatum('IR', id / 2)
            ret.recompute(True)
            set_ir = True
        except Exception:
            pass

    # kinda hacky but ensures that whether OD/ID are larger/smaller we just try both
    do_set_ir()

    # for whatever reason this has to happen in steps to succeed
    increment = 0.5
    target_or = od / 2
    while True:
        d = sketch.getDatum('OR')
        unit = str(d.Unit)
        assert unit.startswith('Unit: mm')
        cur = d.Value
        # cur, units = sketch.getDatum('OR').split(' ')[0]
        if abs(target_or - cur) < increment:
            sketch.setDatum('OR', target_or)
            break
        else:
            sign = 1 if target_or > cur else -1
            sketch.setDatum('OR', cur + sign * increment)
            ret.recompute(True)

    ret.recompute(True)

    do_set_ir()

    if not set_ir:
        raise Exception('Failed to set IR')

    sketch.setDatum('Radius', radius / 8)
    sketch.setDatum('Radius', radius / 4)
    sketch.setDatum('Radius', radius / 2)
    sketch.setDatum('Radius', radius)

    ret.recompute(True)

    return ret

# FreeCAD likes absolute filepaths

# works with stl, obj, ply
def export_mesh(obj, filename: Path):
    import Mesh
    Mesh.export([obj], str(filename.absolute()))
    # using obj.Shape.exportStl was giving ascii stl

def export_step(obj, filename: Path):
    obj.Shape.exportStep(str(filename.absolute()))

fields = {
    'Name': lambda s: s.replace('/', '_').replace(' ', '_'),
    'ID': float,
    'OD': float,
    'Width': float,
    'Radius': float,
}

def parse_row(row):
    return {k: fields[k](row[k]) for k in fields}

def load_bearing_data(filename='bearings-data.csv'):
    ret = {}
    ID = None
    with open(filename, newline='') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row['ID']:
                ID = fields['ID'](row['ID'])
            else:
                row['ID'] = str(ID)
            r = parse_row(row)
            ret[r['Name']] = r
    return ret

def run_in_freecad(name, export_type, outdir):
    env = dict(os.environ)
    env['OUTDIR'] = str(outdir)
    env['BEARING_NAME'] = name
    env['EXPORT_TYPE'] = export_type
    # unforuntately FreeCADCmd doesn't set returncode when we get an error
    proc = run(['FreeCADCmd', __file__], stdout=DEVNULL, env=env, check=True, timeout=30)


if 'BEARING_NAME' in os.environ:
    bearings_data = load_bearing_data()

    outdir      = Path(os.environ['OUTDIR'])
    name        = os.environ['BEARING_NAME']
    export_type = os.environ['EXPORT_TYPE']

    doc = App.openDocument('bearing-template.FCStd')
    template_obj = doc.getObjectsByLabel('template')[0]

    outdir.mkdir(exist_ok=True)

    if name == 'ALL' and export_type == 'fcstd':
        for name, d in bearings_data.items():
            print(f'Working on {name}', file=sys.stderr)
            _ = make_bearing(doc, template_obj, d['ID'], d['OD'], d['Width'], d['Radius'], name)

        doc.saveAs('bearings-catalog.FCStd')
        print('Wrote bearings-catalog.FCStd', file=sys.stderr)

    else:
        worklist = bearings_data.keys() if name == 'ALL' else [name]

        for name in worklist:
            d = bearings_data[name]  # expect KeyError
            print(f'Working on {name}', file=sys.stderr)
            bearing = make_bearing(doc, template_obj, d['ID'], d['OD'], d['Width'], d['Radius'], name)

            filename = outdir / f'{name}.{export_type}'

            if export_type == 'stp':
                export_step(bearing, filename)
            else:
                export_mesh(bearing, filename)

            print(f'Working on ')
            print(f'Wrote to   {filename}', file=sys.stderr)

elif __name__ == '__main__':
    bearings_data = load_bearing_data()

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('bearing_name', choices=list(bearings_data.keys()) + ['ALL'])
    parser.add_argument('--type', default='stl', choices=['stl', 'stp', 'obj', 'ply', 'fcstd'])
    parser.add_argument('--outdir', default=Path('./bearings').resolve(), type=Path)
    args = parser.parse_args()

    if args.type == 'fcstd' and args.bearing_name != 'ALL':
        raise ValueError('You can only use --type=fcstd with name ALL to export a freecad file with all bearings')

    args.outdir.mkdir(exist_ok=True)

    run_in_freecad(args.bearing_name, args.type, args.outdir.resolve())
