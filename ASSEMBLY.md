# Assembly and test plan

Part IDs refer to the [3-D viewer](https://rpirayesh.github.io/E8-eVTOL-Build/) and [MANUFACTURING.md](MANUFACTURING.md).
Use slow epoxy (laminating epoxy thickened with cotton flock) for structural bonds, CA only for printed-to-printed tacking.
Scuff carbon tubes with 180 grit and clean with isopropanol before bonding.

## 1. Wing

1. Cut the spars from the cut list (`bom/cut_list.csv`). Bond the 27 x 25 main-spar joiners (SP-MJ) and 10 mm rear joiners
   (SP-RJ) 150 / 100 mm into the ends of the centre spars (SP-MC, SP-RC).
2. Slide the boom ribs (RIB-B) onto the centre spars at ±600 mm (check with a tape against the centreline mark) and bond.
3. Thread the printed segments onto the spars from the centre out: W-R (centre), two W-C each side, butting against the
   ribs. Bond each segment to its neighbour and to the spars through the spar sleeves (inject epoxy with a long needle).
4. Outer panels: thread W-O, W-O, W-A1, W-A2 onto SP-MO / SP-RO, add the wing tips (W-T starboard, W-TP port).
   Ailerons: bond two AIL pieces on a 4 mm carbon torque rod, hinge on the upper surface with hinge tape, servo in the W-A1
   pocket. The outer panels slide onto the joiners and are retained by an M3 nylon bolt — they come off for transport.
5. Optional, recommended: two layers of 80 g/m² glass at ±45° over the centre section (between the ribs) — raises skin
   shear stiffness about seven-fold for ~150 g.

## 2. Fuselage

1. Bond the plywood bulkheads BH-1…BH-6 into the printed sections in order (nose cone FUS-0 is left removable: it is the
   battery hatch, held by four magnets and two M3 screws).
2. Bolt sections together through the flanges (8 x M3 per joint). Fit the battery tray (TRAY) and avionics deck (DECK).
3. Lower the wing onto BH-3 / BH-4: the bulkhead towers pass through the slots in W-R; fit the spar caps SC-1 / SC-2
   (2 x M4 each into heat-set inserts).
4. Pusher: bolt the firewall (FW) to the tail-cone boss (4 x M3 inserts), then the AT4130 cross-mount to the firewall.

## 3. Booms and propulsion

1. Bond the boom sleeve (BM-S) 75 mm into each rear boom. Drill 8 mm wire exits under each motor station.
2. Clamp the boom halves into the saddles (SAD-U aluminium + SAD-L printed cap, 6 x M4 x 45, 1.5 N m) and bolt the saddles to
   the boom ribs with 2 x M5 x 60 cross bolts each.
3. Nacelles: clamp NAC-U / NAC-L at the rotor stations (centres in `design/selected_design.json`, 4 x M3 x 40 each). Mount the
   MN5008 motors with M3 x 8 + threadlocker; check the screw does not touch the windings (max 3 mm engagement below the seat).
4. **Rotor directions** (seen from above): port boom front to back CCW, CW, CCW, CW; starboard boom CW, CCW, CW, CCW.
   Fit CW propellers on CW motors only.
5. Tail: slide the tail blocks (TB-S, TB-P) onto the boom ends, thread the stabiliser segments on the 6 mm spar between
   them, bond the fins and rudders.
6. Landing legs: leg sockets at x = -150 and +420 mm on each boom, 12 x 10 legs bonded in, TPU feet.

## 4. Electrical (12S)

- Two 6S packs in series via an AS150 series link; main XT90-S to a 200 A power module (PM08D) and the distribution board.
- Each boom carries a 10 AWG pair inside the tube to its four ESCs (in the nacelle pods, cooled by the downwash).
- Servos on a separate 5.3 V UBEC; Pixhawk on the power module's regulated supply.
- Pusher ESC (FLAME 80A) in the tail cone, airflow through the cooling slots.

## 5. Checks before flight

1. **Weight and CG**: target CG 142 mm aft of the wing leading edge (±10 mm), on the centreline; move the packs on the tray to trim.
2. **Proof load**: support the aircraft under the wing at the boom ribs and hang 1.5 x the aircraft weight from each boom
   tip for 30 s (simulates max thrust); inspect saddles, ribs and bulkhead towers.
3. **Tap test**: tape a phone (accelerometer app) or the Pixhawk to a boom end, tap the tail and read the first frequency.
   Set `IMU_GYRO_NF0_FRQ` to it (FEA predicts about 6 Hz) — see [firmware/README.md](firmware/README.md).
4. **Prop spin test**: run each motor to 100 % behind a guard with the prop fitted, check for vibration and balance.
5. **Motor order and direction** in QGroundControl's actuator test; control-surface directions in fixed-wing mode.
6. **First hovers tethered** (ropes at the boom ends, 1 m slack), then free hover, then transition at a safe altitude
   (VT_ARSP_TRANS ≈ 1.25 x stall speed).

## Legal and safety

Register the aircraft, fly under the applicable unmanned-aircraft rules (FAA Part 107 in the USA: < 25 kg, line of sight,
not over people), store and charge LiPo packs in fire-safe bags.
