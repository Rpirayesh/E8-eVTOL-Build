# Manufacturing guide
Every in-house part, how to make it and with which settings. Files: `cad/parts/<ID>/<ID>.stl` (printing) and `<ID>.step` (CAM). Units are mm. Quantities are per aircraft.
## Equipment and materials
- **FDM printer** with at least 256 x 256 x 256 mm build volume, hardened 0.4 mm nozzle and an enclosure for PA6-CF (e.g. Bambu X1C/P1S, Prusa Core One). Dry PA6-CF at 80 °C for 8 h before printing.
- **LW-PLA** (foaming PLA) for skins: calibrate flow for ~50 % expansion at about 230-245 °C; one perimeter gives the modelled 0.6 mm skin. Print segments standing on their root rib; no supports.
- **3-axis CNC**: router for birch plywood; aluminium parts need a spindle and machine able to cut 6061 (light DOC, mist or air blast). If your CNC cannot cut aluminium, use a local job shop for the four aluminium parts — they are simple 2- and 2.5-D parts.
- Carbon tubes are cut with a fine abrasive disc; wear a respirator and cut wet.

## Wing

### W-R — Wing root segment
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 74.7 g · **Envelope:** 320.2 x 240.0 x 49.8 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Note: Carries the two bulkhead towers through lower-skin slots; bond to W-C with epoxy.
- Files: [cad/parts/W-R/W-R.stl](cad/parts/W-R/W-R.stl), [cad/parts/W-R/W-R.step](cad/parts/W-R/W-R.step)

### W-C — Wing centre segment
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 4 · **Mass each:** 78.6 g · **Envelope:** 320.2 x 238.5 x 49.8 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Note: Four identical; slide on spars, bond to neighbours.
- Files: [cad/parts/W-C/W-C.stl](cad/parts/W-C/W-C.stl), [cad/parts/W-C/W-C.step](cad/parts/W-C/W-C.step)

### W-O — Outer wing segment
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 4 · **Mass each:** 67.8 g · **Envelope:** 320.2 x 204.2 x 49.8 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Note: Outer panels are removable: spar joiners slide into the centre spars.
- Files: [cad/parts/W-O/W-O.stl](cad/parts/W-O/W-O.stl), [cad/parts/W-O/W-O.step](cad/parts/W-O/W-O.step)

### W-A1 — Aileron bay segment with servo pocket
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 2 · **Mass each:** 57.0 g · **Envelope:** 232.7 x 204.2 x 49.8 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Note: Servo pocket opens on the lower skin.
- Files: [cad/parts/W-A1/W-A1.stl](cad/parts/W-A1/W-A1.stl), [cad/parts/W-A1/W-A1.step](cad/parts/W-A1/W-A1.step)

### W-A2 — Aileron bay segment
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 2 · **Mass each:** 57.2 g · **Envelope:** 232.7 x 204.2 x 49.8 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Files: [cad/parts/W-A2/W-A2.stl](cad/parts/W-A2/W-A2.stl), [cad/parts/W-A2/W-A2.step](cad/parts/W-A2/W-A2.step)

### AIL — Aileron segment
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 4 · **Mass each:** 21.7 g · **Envelope:** 86.0 x 203.2 x 26.9 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on end
- Supports: none
- Note: Two per side bonded on a 4 mm carbon torque rod; tape or printed pin hinge on the upper surface. Horn on the inner piece.
- Files: [cad/parts/AIL/AIL.stl](cad/parts/AIL/AIL.stl), [cad/parts/AIL/AIL.step](cad/parts/AIL/AIL.step)

### W-T — Wing tip, starboard
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 13.1 g · **Envelope:** 324.4 x 30.0 x 49.8 mm
- Printer: any FDM
- Material: LW-PLA
- Walls: 1 perimeter
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Print wall mm: 0.6
- Note: Printed hollow (slicer walls only).
- Files: [cad/parts/W-T/W-T.stl](cad/parts/W-T/W-T.stl), [cad/parts/W-T/W-T.step](cad/parts/W-T/W-T.step)

### W-TP — Wing tip, port (mirror)
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 13.1 g · **Envelope:** 324.4 x 30.0 x 49.8 mm
- Printer: any FDM
- Material: LW-PLA
- Walls: 1 perimeter
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Print wall mm: 0.6
- Note: Printed hollow (slicer walls only).
- Files: [cad/parts/W-TP/W-TP.stl](cad/parts/W-TP/W-TP.stl), [cad/parts/W-TP/W-TP.step](cad/parts/W-TP/W-TP.step)

### RIB-B — Boom rib (wing-boom load fitting)
- **Process:** CNC · **Material:** 6061-T6 aluminium · **Qty:** 2 · **Mass each:** 129.3 g · **Envelope:** 316.2 x 6.0 x 61.4 mm
- Machine: 3-axis CNC
- Stock: 6 mm 6061-T6 plate
- Setups: 1
- Tools: 6 mm 2-flute carbide (profile, 12000 rpm, 1000 mm/min, 1 mm DOC), 3 mm (windows)
- Workholding: screwed to spoilboard through tab holes, onion-skin 0.3 mm
- Note: 2-D profile from 6 mm 6061-T6 plate: one setup, 6 mm flat end mill for the profile, 3 mm for windows, drill/ream spar bores to 20.05 / 10.05 mm.
- Files: [cad/parts/RIB-B/RIB-B.stl](cad/parts/RIB-B/RIB-B.stl), [cad/parts/RIB-B/RIB-B.step](cad/parts/RIB-B/RIB-B.step)

### SP-MC — Main spar, centre (30x27 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 1 · **Mass each:** 251.1 g · **Envelope:** 30.0 x 1206.0 x 30.0 mm
- Cut: 1206 mm, fine-tooth saw or abrasive disc, wet; sand ends
- Note: Cut to 1206 mm.
- Files: [cad/parts/SP-MC/SP-MC.stl](cad/parts/SP-MC/SP-MC.stl), [cad/parts/SP-MC/SP-MC.step](cad/parts/SP-MC/SP-MC.step)

### SP-RC — Rear spar, centre (12x10 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 1 · **Mass each:** 64.6 g · **Envelope:** 12.0 x 1206.0 x 12.0 mm
- Cut: 1206 mm, fine-tooth saw or abrasive disc, wet; sand ends
- Note: Cut to 1206 mm.
- Files: [cad/parts/SP-RC/SP-RC.stl](cad/parts/SP-RC/SP-RC.stl), [cad/parts/SP-RC/SP-RC.step](cad/parts/SP-RC/SP-RC.step)

### SP-MO — Main spar, outer panel (30x27 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 172.2 g · **Envelope:** 30.0 x 827.0 x 30.0 mm
- Cut: 827 mm x 2
- Note: Cut 2 to 827 mm.
- Files: [cad/parts/SP-MO/SP-MO.stl](cad/parts/SP-MO/SP-MO.stl), [cad/parts/SP-MO/SP-MO.step](cad/parts/SP-MO/SP-MO.step)

### SP-RO — Rear spar, outer panel (12x10 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 44.3 g · **Envelope:** 12.0 x 827.0 x 12.0 mm
- Cut: 827 mm x 2
- Note: Cut 2 to 827 mm.
- Files: [cad/parts/SP-RO/SP-RO.stl](cad/parts/SP-RO/SP-RO.stl), [cad/parts/SP-RO/SP-RO.step](cad/parts/SP-RO/SP-RO.step)

### SP-MJ — Main spar joiner (27x25 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 36.0 g · **Envelope:** 26.9 x 300.0 x 26.9 mm
- Cut: 300 mm x 2
- Note: Bonded into the centre spar, slip fit in the outer spar; retained by an M3 nylon bolt.
- Files: [cad/parts/SP-MJ/SP-MJ.stl](cad/parts/SP-MJ/SP-MJ.stl), [cad/parts/SP-MJ/SP-MJ.step](cad/parts/SP-MJ/SP-MJ.step)

### SP-RJ — Rear spar joiner (10 mm CF rod)
- **Process:** COTS-cut · **Material:** Carbon fibre rod · **Qty:** 2 · **Mass each:** 23.9 g · **Envelope:** 9.9 x 200.0 x 9.9 mm
- Cut: 200 mm x 2
- Note: Bonded into the centre spar, slip fit in the outer spar; retained by an M3 nylon bolt.
- Files: [cad/parts/SP-RJ/SP-RJ.stl](cad/parts/SP-RJ/SP-RJ.stl), [cad/parts/SP-RJ/SP-RJ.step](cad/parts/SP-RJ/SP-RJ.step)

## Booms

### SAD-U — Boom saddle, upper half
- **Process:** CNC · **Material:** 6061-T6 aluminium · **Qty:** 2 · **Mass each:** 236.0 g · **Envelope:** 150.0 x 48.0 x 26.0 mm
- Machine: 3-axis CNC
- Stock: 6061-T6 bar 50 x 30 x 170 mm
- Setups: 2
- Ops: Op1 face, profile, side pockets 6 mm end mill, drill M4/M5; Op2 flip, 12 mm ball-nose half-bore R15.1 along x (0.5 mm step-over), slot 6.2 mm with 6 mm end mill
- Tolerance: half-bore R15.1 +0.05/-0; clamp gap 0.2 mm
- Note: Joins the boom halves (internal sleeve) and transfers boom loads into the boom rib via two M5 cross bolts.
- Files: [cad/parts/SAD-U/SAD-U.stl](cad/parts/SAD-U/SAD-U.stl), [cad/parts/SAD-U/SAD-U.step](cad/parts/SAD-U/SAD-U.step)

### SAD-L — Boom saddle, lower cap
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 2 · **Mass each:** 86.5 g · **Envelope:** 150.0 x 48.0 x 20.0 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 60 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Orientation: flat face down
- Note: 6 x M4 x 45 socket cap screws + washers + nyloc; torque 1.5 N m.
- Files: [cad/parts/SAD-L/SAD-L.stl](cad/parts/SAD-L/SAD-L.stl), [cad/parts/SAD-L/SAD-L.step](cad/parts/SAD-L/SAD-L.step)

### BM-F — Front boom (30x27 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 215.7 g · **Envelope:** 1036.1 x 30.0 x 30.0 mm
- Cut: 1036 mm x 2
- Note: Cut to 1036 mm; drill 8 mm wire exits under each motor.
- Files: [cad/parts/BM-F/BM-F.stl](cad/parts/BM-F/BM-F.stl), [cad/parts/BM-F/BM-F.step](cad/parts/BM-F/BM-F.step)

### BM-R — Rear boom (30x27 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 297.6 g · **Envelope:** 1429.4 x 30.0 x 30.0 mm
- Cut: 1429 mm x 2
- Note: Cut to 1429 mm.
- Files: [cad/parts/BM-R/BM-R.stl](cad/parts/BM-R/BM-R.stl), [cad/parts/BM-R/BM-R.step](cad/parts/BM-R/BM-R.step)

### BM-S — Boom joint sleeve (27x25 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 18.9 g · **Envelope:** 150.0 x 26.9 x 26.9 mm
- Cut: 150 mm x 2
- Note: Bonded into the rear boom, slip fit into the front boom inside the saddle.
- Files: [cad/parts/BM-S/BM-S.stl](cad/parts/BM-S/BM-S.stl), [cad/parts/BM-S/BM-S.step](cad/parts/BM-S/BM-S.step)

### BM-NC — Boom nose cone
- **Process:** FDM · **Material:** PETG · **Qty:** 2 · **Mass each:** 19.3 g · **Envelope:** 45.0 x 30.0 x 30.0 mm
- Printer: FDM with hardened nozzle
- Material: PETG
- Walls: 5 perimeters
- Infill: 20 %
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Note: Press fit + CA.
- Files: [cad/parts/BM-NC/BM-NC.stl](cad/parts/BM-NC/BM-NC.stl), [cad/parts/BM-NC/BM-NC.step](cad/parts/BM-NC/BM-NC.step)

## Propulsion

### NAC-U — Lift motor nacelle, upper (motor pedestal)
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 8 · **Mass each:** 52.6 g · **Envelope:** 96.0 x 60.0 x 36.5 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Orientation: seat face down on the bed
- Inserts: none (through bolts)
- Note: Motor seat with radial slots for 4 x M3 on any 25-34 mm bolt circle: confirm against the delivered MN5008 before printing.
- Files: [cad/parts/NAC-U/NAC-U.stl](cad/parts/NAC-U/NAC-U.stl), [cad/parts/NAC-U/NAC-U.step](cad/parts/NAC-U/NAC-U.step)

### NAC-L — Lift motor nacelle, lower (ESC pod)
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 8 · **Mass each:** 34.2 g · **Envelope:** 100.0 x 47.0 x 39.0 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Orientation: split face down
- Note: Houses the FLAME 60A ESC in the rotor downwash; open aft end for cooling air.
- Files: [cad/parts/NAC-L/NAC-L.stl](cad/parts/NAC-L/NAC-L.stl), [cad/parts/NAC-L/NAC-L.step](cad/parts/NAC-L/NAC-L.step)

### FW — Pusher firewall plate
- **Process:** CNC · **Material:** 6061-T6 aluminium · **Qty:** 1 · **Mass each:** 53.6 g · **Envelope:** 3.0 x 94.0 x 94.0 mm
- Machine: 3-axis CNC
- Stock: 3 mm 6061-T6 plate
- Setups: 1
- Note: Bolts to the tail-cone boss ring (4 x M3 inserts). Motor cross-mount bolts on any 25-38 mm pattern (drilled pattern of holes).
- Files: [cad/parts/FW/FW.stl](cad/parts/FW/FW.stl), [cad/parts/FW/FW.step](cad/parts/FW/FW.step)

## Fuselage

### FUS-0 — Nose cone
- **Process:** FDM · **Material:** PETG · **Qty:** 1 · **Mass each:** 138.1 g · **Envelope:** 168.5 x 240.0 x 260.0 mm
- Printer: any FDM
- Material: PETG
- Walls: 2 perimeters (1.0 mm)
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Orientation: stand on the larger joint face
- Note: Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.
- Files: [cad/parts/FUS-0/FUS-0.stl](cad/parts/FUS-0/FUS-0.stl), [cad/parts/FUS-0/FUS-0.step](cad/parts/FUS-0/FUS-0.step)

### FUS-1 — Fuselage section 1 (avionics / hatch)
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 100.4 g · **Envelope:** 197.0 x 240.0 x 260.0 mm
- Printer: any FDM
- Material: LW-PLA (foamed)
- Walls: 2 perimeters (1.0 mm)
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Orientation: stand on the larger joint face
- Note: Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.
- Files: [cad/parts/FUS-1/FUS-1.stl](cad/parts/FUS-1/FUS-1.stl), [cad/parts/FUS-1/FUS-1.step](cad/parts/FUS-1/FUS-1.step)

### FUS-2 — Fuselage section 2 (battery bay)
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 81.1 g · **Envelope:** 129.5 x 240.0 x 260.0 mm
- Printer: any FDM
- Material: LW-PLA (foamed)
- Walls: 2 perimeters (1.0 mm)
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Orientation: stand on the larger joint face
- Note: Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.
- Files: [cad/parts/FUS-2/FUS-2.stl](cad/parts/FUS-2/FUS-2.stl), [cad/parts/FUS-2/FUS-2.step](cad/parts/FUS-2/FUS-2.step)

### FUS-3 — Fuselage section 3 (wing carry)
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 68.2 g · **Envelope:** 105.0 x 240.0 x 260.0 mm
- Printer: any FDM
- Material: LW-PLA (foamed)
- Walls: 2 perimeters (1.0 mm)
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Orientation: stand on the larger joint face
- Note: Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.
- Files: [cad/parts/FUS-3/FUS-3.stl](cad/parts/FUS-3/FUS-3.stl), [cad/parts/FUS-3/FUS-3.step](cad/parts/FUS-3/FUS-3.step)

### FUS-4 — Fuselage section 4
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 129.0 g · **Envelope:** 220.5 x 240.0 x 260.0 mm
- Printer: any FDM
- Material: LW-PLA (foamed)
- Walls: 2 perimeters (1.0 mm)
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Orientation: stand on the larger joint face
- Note: Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.
- Files: [cad/parts/FUS-4/FUS-4.stl](cad/parts/FUS-4/FUS-4.stl), [cad/parts/FUS-4/FUS-4.step](cad/parts/FUS-4/FUS-4.step)

### FUS-5 — Fuselage section 5 (tail taper)
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 108.2 g · **Envelope:** 217.0 x 239.9 x 259.8 mm
- Printer: any FDM
- Material: LW-PLA (foamed)
- Walls: 2 perimeters (1.0 mm)
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Orientation: stand on the larger joint face
- Note: Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.
- Files: [cad/parts/FUS-5/FUS-5.stl](cad/parts/FUS-5/FUS-5.stl), [cad/parts/FUS-5/FUS-5.step](cad/parts/FUS-5/FUS-5.step)

### FUS-6 — Tail cone (pusher mount)
- **Process:** FDM · **Material:** PETG-CF · **Qty:** 1 · **Mass each:** 124.7 g · **Envelope:** 188.5 x 164.5 x 170.2 mm
- Printer: FDM with hardened nozzle
- Material: PETG-CF
- Walls: 3 perimeters
- Infill: n/a (shell)
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Note: Bonded and bolted (8 x M3) to the plywood bulkheads at each joint.
- Files: [cad/parts/FUS-6/FUS-6.stl](cad/parts/FUS-6/FUS-6.stl), [cad/parts/FUS-6/FUS-6.step](cad/parts/FUS-6/FUS-6.step)

### FUS-H — Battery / avionics hatch
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 28.2 g · **Envelope:** 160.0 x 146.0 x 16.5 mm
- Printer: any FDM
- Material: LW-PLA (fuselage) or PETG (nose/tail where impact-prone)
- Walls: 2 perimeters (1.0 mm)
- Infill: 0 %
- Layer: 0.25 mm
- Supports: tree, under flanges
- Note: Two magnets forward, printed tongue aft.
- Files: [cad/parts/FUS-H/FUS-H.stl](cad/parts/FUS-H/FUS-H.stl), [cad/parts/FUS-H/FUS-H.step](cad/parts/FUS-H/FUS-H.step)

### BH-1 — Bulkhead 1 (avionics)
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 22.9 g · **Envelope:** 3.0 x 240.0 x 260.0 mm
- Machine: 3-axis CNC router
- Stock: 3 mm birch plywood (BS1088 / aircraft grade)
- Tools: 3.175 mm 2-flute upcut/downcut compression, 18000 rpm, 1500 mm/min
- Setups: 1
- Workholding: vacuum or screws in waste, 0.3 mm tabs
- Note: 3 mm aircraft birch plywood ring frame.
- Files: [cad/parts/BH-1/BH-1.stl](cad/parts/BH-1/BH-1.stl), [cad/parts/BH-1/BH-1.step](cad/parts/BH-1/BH-1.step)

### BH-2 — Bulkhead 2 (battery fwd)
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 22.9 g · **Envelope:** 3.0 x 240.0 x 260.0 mm
- Machine: 3-axis CNC router
- Stock: 3 mm birch plywood (BS1088 / aircraft grade)
- Tools: 3.175 mm 2-flute upcut/downcut compression, 18000 rpm, 1500 mm/min
- Setups: 1
- Workholding: vacuum or screws in waste, 0.3 mm tabs
- Note: 3 mm aircraft birch plywood ring frame.
- Files: [cad/parts/BH-2/BH-2.stl](cad/parts/BH-2/BH-2.stl), [cad/parts/BH-2/BH-2.step](cad/parts/BH-2/BH-2.step)

### BH-3 — Bulkhead 3 (main spar carry)
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 83.8 g · **Envelope:** 6.0 x 240.0 x 284.3 mm
- Machine: 3-axis CNC router
- Stock: 6 mm birch plywood (BS1088 / aircraft grade)
- Tools: 3.175 mm 2-flute upcut/downcut compression, 18000 rpm, 1500 mm/min
- Setups: 1
- Workholding: vacuum or screws in waste, 0.3 mm tabs
- Note: 6 mm aircraft birch plywood ring frame. Carries the wing: spar sits in the cradle under a printed cap.
- Files: [cad/parts/BH-3/BH-3.stl](cad/parts/BH-3/BH-3.stl), [cad/parts/BH-3/BH-3.step](cad/parts/BH-3/BH-3.step)

### BH-4 — Bulkhead 4 (rear spar carry)
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 82.6 g · **Envelope:** 6.0 x 240.0 x 281.3 mm
- Machine: 3-axis CNC router
- Stock: 6 mm birch plywood (BS1088 / aircraft grade)
- Tools: 3.175 mm 2-flute upcut/downcut compression, 18000 rpm, 1500 mm/min
- Setups: 1
- Workholding: vacuum or screws in waste, 0.3 mm tabs
- Note: 6 mm aircraft birch plywood ring frame. Carries the wing: spar sits in the cradle under a printed cap.
- Files: [cad/parts/BH-4/BH-4.stl](cad/parts/BH-4/BH-4.stl), [cad/parts/BH-4/BH-4.step](cad/parts/BH-4/BH-4.step)

### BH-5 — Bulkhead 5
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 22.9 g · **Envelope:** 3.0 x 240.0 x 260.0 mm
- Machine: 3-axis CNC router
- Stock: 3 mm birch plywood (BS1088 / aircraft grade)
- Tools: 3.175 mm 2-flute upcut/downcut compression, 18000 rpm, 1500 mm/min
- Setups: 1
- Workholding: vacuum or screws in waste, 0.3 mm tabs
- Note: 3 mm aircraft birch plywood ring frame.
- Files: [cad/parts/BH-5/BH-5.stl](cad/parts/BH-5/BH-5.stl), [cad/parts/BH-5/BH-5.step](cad/parts/BH-5/BH-5.step)

### BH-6 — Bulkhead 6 (tail)
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 14.9 g · **Envelope:** 3.0 x 165.2 x 170.9 mm
- Machine: 3-axis CNC router
- Stock: 3 mm birch plywood (BS1088 / aircraft grade)
- Tools: 3.175 mm 2-flute upcut/downcut compression, 18000 rpm, 1500 mm/min
- Setups: 1
- Workholding: vacuum or screws in waste, 0.3 mm tabs
- Note: 3 mm aircraft birch plywood ring frame.
- Files: [cad/parts/BH-6/BH-6.stl](cad/parts/BH-6/BH-6.stl), [cad/parts/BH-6/BH-6.step](cad/parts/BH-6/BH-6.step)

### SC-1 — Spar cap (main spar)
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 1 · **Mass each:** 14.2 g · **Envelope:** 18.0 x 60.0 x 20.0 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Note: Clamps the spar into the bulkhead cradle; 2 x M4 into heat-set inserts in printed tower blocks.
- Files: [cad/parts/SC-1/SC-1.stl](cad/parts/SC-1/SC-1.stl), [cad/parts/SC-1/SC-1.step](cad/parts/SC-1/SC-1.step)

### SC-2 — Spar cap (rear spar)
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 1 · **Mass each:** 10.3 g · **Envelope:** 18.0 x 60.0 x 11.0 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Note: Clamps the spar into the bulkhead cradle; 2 x M4 into heat-set inserts in printed tower blocks.
- Files: [cad/parts/SC-2/SC-2.stl](cad/parts/SC-2/SC-2.stl), [cad/parts/SC-2/SC-2.step](cad/parts/SC-2/SC-2.step)

### TRAY — Battery tray
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 202.4 g · **Envelope:** 660.0 x 200.0 x 3.0 mm
- Machine: 3-axis CNC router
- Stock: 3 mm birch plywood
- Setups: 1
- Note: Carries four 6S packs (2 x 2) on velcro straps through the slots; rests on bulkhead rims.
- Files: [cad/parts/TRAY/TRAY.stl](cad/parts/TRAY/TRAY.stl), [cad/parts/TRAY/TRAY.step](cad/parts/TRAY/TRAY.step)

### DECK — Avionics deck
- **Process:** CNC · **Material:** Birch plywood · **Qty:** 1 · **Mass each:** 61.6 g · **Envelope:** 190.0 x 180.0 x 3.0 mm
- Machine: 3-axis CNC router
- Stock: 3 mm birch plywood
- Note: Pixhawk on 4 vibration dampers; receiver, telemetry and power module.
- Files: [cad/parts/DECK/DECK.stl](cad/parts/DECK/DECK.stl), [cad/parts/DECK/DECK.step](cad/parts/DECK/DECK.step)

### GPS-M — GPS mast
- **Process:** FDM · **Material:** PETG · **Qty:** 1 · **Mass each:** 13.9 g · **Envelope:** 44.0 x 44.0 x 114.0 mm
- Printer: FDM with hardened nozzle
- Material: PETG
- Walls: 5 perimeters
- Infill: 100 %
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Note: Raises the GPS above the wing and away from the ESC fields.
- Files: [cad/parts/GPS-M/GPS-M.stl](cad/parts/GPS-M/GPS-M.stl), [cad/parts/GPS-M/GPS-M.step](cad/parts/GPS-M/GPS-M.step)

## Tail

### TB-S — Tail block, starboard
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 1 · **Mass each:** 122.4 g · **Envelope:** 182.5 x 60.0 x 57.0 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Orientation: boom axis vertical
- Note: Slides over the boom end; 2 x M3 cross bolts. Stab and fin sockets bonded.
- Files: [cad/parts/TB-S/TB-S.stl](cad/parts/TB-S/TB-S.stl), [cad/parts/TB-S/TB-S.step](cad/parts/TB-S/TB-S.step)

### TB-P — Tail block, port (mirror)
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 1 · **Mass each:** 122.4 g · **Envelope:** 182.5 x 60.0 x 57.0 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Orientation: boom axis vertical
- Files: [cad/parts/TB-P/TB-P.stl](cad/parts/TB-P/TB-P.stl), [cad/parts/TB-P/TB-P.step](cad/parts/TB-P/TB-P.step)

### HS — Horizontal stabiliser segment
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 4 · **Mass each:** 20.8 g · **Envelope:** 70.7 x 232.8 x 11.0 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Note: Threaded on a 6 mm CF rod spar (1170 mm).
- Files: [cad/parts/HS/HS.stl](cad/parts/HS/HS.stl), [cad/parts/HS/HS.step](cad/parts/HS/HS.step)

### HS-C — Horizontal stabiliser centre (elevator servo)
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 1 · **Mass each:** 20.6 g · **Envelope:** 70.7 x 232.8 x 11.0 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Note: Elevator servo pocket on the lower skin (servo partly protrudes into the stab; fair with tape).
- Files: [cad/parts/HS-C/HS-C.stl](cad/parts/HS-C/HS-C.stl), [cad/parts/HS-C/HS-C.step](cad/parts/HS-C/HS-C.step)

### ELV — Elevator segment
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 5 · **Mass each:** 9.0 g · **Envelope:** 38.0 x 231.8 x 7.5 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 1 perimeter (0.6 mm foamed skin is modelled)
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: stand on root rib (span vertical)
- Supports: none
- Note: Five segments on a 3 mm CF torque rod; horn on the centre piece.
- Files: [cad/parts/ELV/ELV.stl](cad/parts/ELV/ELV.stl), [cad/parts/ELV/ELV.step](cad/parts/ELV/ELV.step)

### HS-SP — Stabiliser spar (6 mm CF rod)
- **Process:** COTS-cut · **Material:** Carbon fibre rod · **Qty:** 1 · **Mass each:** 52.8 g · **Envelope:** 6.0 x 1204.0 x 6.0 mm
- Cut: 1204 mm
- Files: [cad/parts/HS-SP/HS-SP.stl](cad/parts/HS-SP/HS-SP.stl), [cad/parts/HS-SP/HS-SP.step](cad/parts/HS-SP/HS-SP.step)

### FIN — Vertical fin
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 2 · **Mass each:** 28.7 g · **Envelope:** 123.2 x 17.0 x 230.0 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 2 perimeters
- Infill: 0 %
- Layer: 0.25 mm
- Orientation: root down
- Supports: none
- Print wall mm: 1.0
- Note: Printed hollow with 2 perimeters: 4 mm CF rod spar at 30 % chord; rudder servo at the root.
- Files: [cad/parts/FIN/FIN.stl](cad/parts/FIN/FIN.stl), [cad/parts/FIN/FIN.step](cad/parts/FIN/FIN.step)

### RUD — Rudder
- **Process:** FDM · **Material:** LW-PLA (foamed) · **Qty:** 2 · **Mass each:** 15.6 g · **Envelope:** 59.4 x 11.7 x 230.0 mm
- Printer: any FDM with >= 256 mm Z and 0.4 mm nozzle
- Material: LW-PLA (foaming, ~230 C for ~50 % expansion)
- Walls: 2 perimeters
- Infill: 0 % (internal ribs/webs are modelled)
- Layer: 0.25 mm
- Orientation: root down
- Supports: none
- Print wall mm: 1.0
- Files: [cad/parts/RUD/RUD.stl](cad/parts/RUD/RUD.stl), [cad/parts/RUD/RUD.step](cad/parts/RUD/RUD.step)

## Landing gear

### LG-S — Landing leg socket, starboard
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 2 · **Mass each:** 23.7 g · **Envelope:** 40.0 x 39.0 x 69.7 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Orientation: boom axis vertical
- Note: Clamped to the boom with 2 x M3; leg bonded with epoxy.
- Files: [cad/parts/LG-S/LG-S.stl](cad/parts/LG-S/LG-S.stl), [cad/parts/LG-S/LG-S.step](cad/parts/LG-S/LG-S.step)

### LG-P — Landing leg socket, port (mirror)
- **Process:** FDM · **Material:** PA6-CF · **Qty:** 2 · **Mass each:** 23.7 g · **Envelope:** 40.0 x 39.0 x 69.7 mm
- Printer: FDM with hardened nozzle
- Material: PA6-CF or PETG-CF, dried
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Orientation: boom axis vertical
- Files: [cad/parts/LG-P/LG-P.stl](cad/parts/LG-P/LG-P.stl), [cad/parts/LG-P/LG-P.step](cad/parts/LG-P/LG-P.step)

### LG-T — Landing leg (12x10 CF tube)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 15.4 g · **Envelope:** 12.0 x 61.4 x 283.1 mm
- Cut: 285 mm x 4
- Note: Cut 4 to 285 mm.
- Files: [cad/parts/LG-T/LG-T.stl](cad/parts/LG-T/LG-T.stl), [cad/parts/LG-T/LG-T.step](cad/parts/LG-T/LG-T.step)

### LG-F — Landing foot
- **Process:** FDM · **Material:** TPU 95A · **Qty:** 2 · **Mass each:** 14.7 g · **Envelope:** 32.0 x 32.0 x 31.6 mm
- Printer: FDM with hardened nozzle
- Material: TPU 95A
- Walls: 3
- Infill: 25 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Note: Shock-absorbing foot; 3 walls, 25 % gyroid.
- Files: [cad/parts/LG-F/LG-F.stl](cad/parts/LG-F/LG-F.stl), [cad/parts/LG-F/LG-F.step](cad/parts/LG-F/LG-F.step)

### LG-TP — Landing leg (port)
- **Process:** COTS-cut · **Material:** Carbon fibre tube · **Qty:** 2 · **Mass each:** 15.4 g · **Envelope:** 12.0 x 61.4 x 283.1 mm
- Cut: same as LG-T
- Files: [cad/parts/LG-TP/LG-TP.stl](cad/parts/LG-TP/LG-TP.stl), [cad/parts/LG-TP/LG-TP.step](cad/parts/LG-TP/LG-TP.step)

### LG-FP — Landing foot (port)
- **Process:** FDM · **Material:** TPU 95A · **Qty:** 2 · **Mass each:** 14.7 g · **Envelope:** 32.0 x 32.0 x 31.6 mm
- Printer: FDM with hardened nozzle
- Material: TPU 95A
- Walls: 5 perimeters
- Infill: 40 % gyroid
- Layer: 0.2 mm
- Supports: as needed
- Post: heat-set M3 inserts where noted
- Files: [cad/parts/LG-FP/LG-FP.stl](cad/parts/LG-FP/LG-FP.stl), [cad/parts/LG-FP/LG-FP.step](cad/parts/LG-FP/LG-FP.step)
