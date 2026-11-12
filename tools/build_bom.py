"""Bill of materials: purchased parts, raw stock (with cut lists), filament, fasteners, cost.

    python tools/build_bom.py      -> bom/BOM.csv, bom/cut_list.csv, docs/data/bom.json
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMP = json.loads((ROOT / "design" / "components.json").read_text())
SEL = json.loads((ROOT / "design" / "selected_design.json").read_text())
PARTS = json.loads((ROOT / "docs" / "data" / "parts.json").read_text())["parts"]

# raw stock: (description, stock length mm, price USD, source)
TUBE_STOCK = {
    "30x27": ("Roll-wrapped 3K carbon tube 30 x 27 mm", 2000, 58.0, "https://www.easycomposites.co.uk/"),
    "27x25": ("Roll-wrapped carbon tube 27 x 25 mm (joiners / sleeves)", 1000, 26.0, "https://www.easycomposites.co.uk/"),
    "12x10": ("Pultruded/roll-wrapped carbon tube 12 x 10 mm", 2000, 22.0, "https://www.easycomposites.co.uk/"),
    "rod10": ("Pultruded carbon rod 10 mm", 1000, 14.0, "https://www.easycomposites.co.uk/"),
    "rod6": ("Pultruded carbon rod 6 mm", 1500, 9.0, "https://www.easycomposites.co.uk/"),
    "rod4": ("Pultruded carbon rod 4 mm (torque rods, fin spars)", 1000, 4.0, "https://www.easycomposites.co.uk/"),
    "rod3": ("Pultruded carbon rod 3 mm (elevator torque rod)", 1500, 4.0, "https://www.easycomposites.co.uk/"),
}
FILAMENT = {  # material: (spool kg, USD per spool, example product)
    "LW-PLA (foamed)": (0.8, 45.0, "ColorFabb LW-PLA 1.75 mm"),
    "PA6-CF": (1.0, 70.0, "Bambu PAHT-CF / Polymaker PA6-CF"),
    "PETG": (1.0, 22.0, "any PETG 1.75 mm"),
    "PETG-CF": (1.0, 35.0, "Bambu PETG-CF"),
    "TPU 95A": (1.0, 30.0, "TPU 95A 1.75 mm"),
}


def cut_items():
    """Cut lengths per stock type from the CAD parts (COTS-cut)."""
    items = []
    for p in PARTS:
        if p["process"] != "COTS-cut":
            continue
        L = max(p["size_mm"])
        n = p["qty"]
        name = p["name"]
        if "30x27" in name:
            key = "30x27"
        elif "27x25" in name or "joiner (27" in name or "sleeve (27" in name:
            key = "27x25"
        elif "12x10" in name:
            key = "12x10"
        elif "10 mm CF rod" in name:
            key = "rod10"
        elif "6 mm CF rod" in name:
            key = "rod6"
        else:
            key = "12x10" if "Landing leg" in name else "rod6"
        items += [(key, round(L + 2), p["id"], name)] * n
    # torque rods and fin spars (not modelled as parts)
    span_ail = 2 * 216
    items += [("rod4", span_ail + 20, "AIL-ROD", "Aileron torque rod")] * 2
    items += [("rod4", 220, "FIN-SP", "Fin spar")] * 2
    items += [("rod3", int(2 * SEL["geometry"]["rotor_y"] * 1000), "ELV-ROD", "Elevator torque rod")]
    return items


def pack(items):
    """First-fit decreasing into stock lengths (3 mm kerf)."""
    out = {}
    for key in TUBE_STOCK:
        L = TUBE_STOCK[key][1]
        bins = []
        for (k, length, pid, name) in sorted([i for i in items if i[0] == key], key=lambda i: -i[1]):
            if length > L:
                raise ValueError(f"{pid} ({length} mm) longer than {key} stock ({L} mm)")
            for b in bins:
                if sum(x[1] + 3 for x in b) + length <= L:
                    b.append((pid, length, name))
                    break
            else:
                bins.append([(pid, length, name)])
        if bins:
            out[key] = bins
    return out


def main():
    rows = []
    add = lambda cat, item, qty, unit, price, src, note="": rows.append(
        dict(category=cat, item=item, qty=qty, unit=unit, unit_price_usd=price, total_usd=round(qty * price, 2), source=src, note=note))
    c = COMP
    bat = c[SEL["design"]["battery"]]
    add("Propulsion", c["lift_motor"]["name"], 8, "pc", c["lift_motor"]["price_usd"], c["lift_motor"]["source"], c["lift_motor"]["spec"])
    add("Propulsion", c["lift_prop"]["name"], 4, "pair", c["lift_prop"]["price_usd"], c["lift_prop"]["source"], "4 CW + 4 CCW; buy 1 spare pair")
    add("Propulsion", c["lift_esc"]["name"], 8, "pc", c["lift_esc"]["price_usd"], c["lift_esc"]["source"], c["lift_esc"]["spec"])
    add("Propulsion", c["cruise_motor"]["name"], 1, "pc", c["cruise_motor"]["price_usd"], c["cruise_motor"]["source"], c["cruise_motor"]["spec"])
    add("Propulsion", c["cruise_prop"]["name"], 2, "pc", c["cruise_prop"]["price_usd"], c["cruise_prop"]["source"], "1 + 1 spare")
    add("Propulsion", c["cruise_esc"]["name"], 1, "pc", c["cruise_esc"]["price_usd"], c["cruise_esc"]["source"], c["cruise_esc"]["spec"])
    add("Power", bat["name"], SEL["design"]["n_battery"], "pc", bat["price_usd"], bat["source"],
        "Two 6S packs in series = 12S 22 Ah; buy a second set for turnaround")
    for k in ("flight_controller", "gps", "airspeed", "power_sensor", "telemetry", "receiver", "bec"):
        add("Avionics", c[k]["name"], c[k]["qty"], "pc", c[k]["price_usd"], c[k]["source"], c[k].get("spec", ""))
    add("Avionics", c["servo"]["name"], 5, "pc", c["servo"]["price_usd"], c["servo"]["source"], c["servo"]["spec"])
    add("Power", c["harness"]["name"], 1, "set", c["harness"]["price_usd"], c["harness"]["source"], c["harness"]["spec"])
    add("Power", "12S LiPo balance charger (e.g. ISDT/ToolkitRC dual 6S) + LiPo safety bags", 1, "set", 260.0, "various", "ground equipment")
    add("Avionics", "RC transmitter with ExpressLRS (e.g. RadioMaster TX16S / Boxer)", 1, "pc", 160.0, "https://www.radiomasterrc.com/", "skip if already owned")

    bins = pack(cut_items())
    cut_rows = []
    for key, bl in bins.items():
        desc, L, price, src = TUBE_STOCK[key]
        add("Raw stock", f"{desc}, {L} mm", len(bl), "length", price, src, f"{len(bl)} lengths; see cut_list.csv")
        for i, b in enumerate(bl, 1):
            for pid, length, name in b:
                cut_rows.append(dict(stock=f"{desc} #{i}", part=pid, name=name, length_mm=length))
            cut_rows.append(dict(stock=f"{desc} #{i}", part="(offcut)", name="", length_mm=L - sum(x[1] + 3 for x in b)))

    # filament
    by_mat = {}
    for p in PARTS:
        if p["process"] == "FDM":
            by_mat[p["material"]] = by_mat.get(p["material"], 0) + p["mass_g_each"] * p["qty"] / 1000
    for mat, kg in by_mat.items():
        spool_kg, price, prod = FILAMENT[mat]
        n = math.ceil(kg * 1.35 / spool_kg)  # supports, brims, failed prints
        add("Filament", f"{prod} ({mat})", n, "spool", price, "various", f"{kg:.2f} kg in parts; 35 % allowance")
    # CNC stock
    add("CNC stock", "6061-T6 plate 6 mm, 350 x 150 mm (boom ribs)", 1, "pc", 32.0, "https://www.onlinemetals.com/", "2 ribs")
    add("CNC stock", "6061-T6 plate 3 mm, 120 x 120 mm (firewall)", 1, "pc", 9.0, "https://www.onlinemetals.com/", "")
    add("CNC stock", "6061-T6 bar 50 x 30 x 340 mm (two saddles)", 1, "pc", 28.0, "https://www.onlinemetals.com/", "")
    add("CNC stock", "Aircraft birch plywood 3 mm, 600 x 600 mm", 2, "sheet", 24.0, "various", "bulkheads 1, 2, 5, 6, tray, deck")
    add("CNC stock", "Aircraft birch plywood 6 mm, 300 x 300 mm", 1, "sheet", 18.0, "various", "bulkheads 3, 4 (wing carry)")
    # fasteners and consumables (counts from the CAD features)
    hw = [
        ("M3 x 40 socket head + nyloc (nacelle clamps)", 32, 0.18),
        ("M3 x 8 socket head, blue threadlocker (motor mounting)", 40, 0.08),
        ("M3 x 12 + nyloc (fuselage joints, 8 per joint)", 48, 0.10),
        ("M3 heat-set inserts (firewall boss, hatch, misc.)", 30, 0.10),
        ("M4 x 45 socket head + washers + nyloc (saddle clamps)", 12, 0.25),
        ("M4 heat-set inserts + M4 x 16 (spar caps)", 4, 0.30),
        ("M5 x 60 socket head + nyloc (saddle-rib cross bolts)", 4, 0.40),
        ("M3 x 30 + nyloc (tail blocks, leg sockets)", 12, 0.15),
        ("Neodymium magnets 10 x 3 mm (nose cone)", 4, 0.30),
    ]
    for name, n, p in hw:
        add("Fasteners", name, n, "pc", p, "McMaster-Carr / Bossard", "")
    for name, price in (("Laminating epoxy 500 g + slow hardener (spar/boom bonding, glass centre section)", 38.0),
                        ("Thick CA + activator", 15.0), ("Glass cloth 80 g/m2, 1 m2 (optional centre-section stiffening)", 12.0),
                        ("Velcro battery straps 25 mm x 4, anti-slip mat", 18.0), ("Servo extensions, Y-leads", 20.0),
                        ("Heat-shrink, cable ties, spiral wrap", 15.0)):
        add("Consumables", name, 1, "set", price, "various", "")

    total = sum(r["total_usd"] for r in rows)
    (ROOT / "bom").mkdir(exist_ok=True)
    with open(ROOT / "bom" / "BOM.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    with open(ROOT / "bom" / "cut_list.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cut_rows[0].keys())
        w.writeheader()
        w.writerows(cut_rows)
    made = [dict(id=p["id"], name=p["name"], process=p["process"], material=p["material"], qty=p["qty"],
                 mass_g_each=p["mass_g_each"], size_mm=p["size_mm"], files=p["files"]) for p in PARTS if p["process"] in ("FDM", "CNC")]
    (ROOT / "docs" / "data" / "bom.json").write_text(json.dumps(dict(rows=rows, cut_list=cut_rows, made=made, total_usd=total), indent=1))
    by_cat = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["total_usd"]
    print(json.dumps({k: round(v, 2) for k, v in by_cat.items()}, indent=1), f"\nTOTAL ${total:,.2f}")


if __name__ == "__main__":
    main()
