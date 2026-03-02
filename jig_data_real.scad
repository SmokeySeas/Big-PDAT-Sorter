// Auto-generated for Jig #1 — Firewall
// Stud 10009: T5x14.2 @ global (-145.89, -322.00, 626.00)
// Stud 10122: M6x16   @ global (-145.89, -250.87, 579.29)
//
// Local coordinate system:
//   Origin = bottom-left of plate
//   Local X = global Y direction (lateral along firewall)
//   Local Y = global Z direction (vertical)
//   Stud spacing: ~71.1mm lateral, ~46.7mm vertical

// Plate: thick block body (not a thin plate)
// Width=120, Depth=45, Height=25
plate = [120.0, 45.0, 25.0];

// Stud check holes: [local_x, local_y, clearance_diameter]
// 10009 T5 stud: 5mm nominal → 6mm clearance
// 10122 M6 stud: 6mm nominal → 7mm clearance
studs = [
    [25.0,  22.5, 6.0],   // 10009 T5x14.2
    [95.0,  22.5, 7.0]    // 10122 M6x16
];

// Underside contact pads: [x, y, diameter, height]
// 3-point contact for stable seating on firewall
pads = [
    [20.0,  10.0, 18.0, 8.0],   // front-left
    [100.0, 10.0, 18.0, 8.0],   // front-right
    [60.0,  38.0, 18.0, 8.0]    // rear-center
];

// Registration hook/ledge: [x_offset, y_offset, width, depth, height]
// Keys against a panel edge for repeatable placement
hook = [120.0, 5.0, 35.0, 20.0, 40.0];

// Handle position: [x, y] on top surface
handle_pos = [60.0, 22.5];

// Embossed text lines on front face
label_lines = ["JIG #1", "F541071111252", "FIREWALL", "T5+M6"];
