Goto [bearings-data.csv](./bearings-data.csv) to see the list of bearings.

I never found a great catalog of all metric bearings in one place so I've compiled a CSV here.

`bearing-template.FCStd` is a FreeCAD file with a bearing that has sketch constraints to model a parametric bearing.

My intention with [bearings.py](./bearings.py) was a command line tool that would modify the sketch and export a copy for use. Unforunately, I've hit some trouble with the constraint system and its hard to handle all cases well. Leaving it up for the time being as it demos some usage of the FreeCAD API and might be fixable.
