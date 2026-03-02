// base_jig_real.scad
// Production-style stud checker jig template
// Expects generated/jig_data_real.scad with:
//   plate, studs, pads, hook, handle_pos, label_lines

include <generated/jig_data_real.scad>;

$fn = 64;

// --- Bushing counterbore dimensions ---
bushing_od = 12.0;    // outer diameter of press-fit bushing
bushing_depth = 4.0;  // counterbore depth from top surface

// --- Main Body ---
module body() {
    // Rounded block body using minkowski with small sphere
    // (fallback: plain cube for speed)
    cube([plate[0], plate[1], plate[2]], center=false);
}

// --- Stud check hole with counterbore ---
module stud_hole(x, y, d, h) {
    // Through hole
    translate([x, y, -1])
        cylinder(h = h + 2, d = d);
    // Counterbore from top for bushing insert
    translate([x, y, h - bushing_depth])
        cylinder(h = bushing_depth + 1, d = bushing_od);
}

// --- Underside contact pad ---
module pad(x, y, d, h) {
    translate([x, y, -h])
        cylinder(h = h, d = d);
}

// --- Registration hook/ledge ---
module hook() {
    // hook = [x_offset, y_offset, width, depth, height]
    translate([hook[0], hook[1], 0])
        cube([hook[3], hook[2], hook[4]], center=false);
}

// --- Handle / grip knob ---
module handle() {
    // handle_pos = [x, y]
    hx = handle_pos[0];
    hy = handle_pos[1];
    stem_d = 14;
    stem_h = 20;
    knob_d = 22;
    knob_h = 10;

    // Stem
    translate([hx, hy, plate[2]])
        cylinder(h = stem_h, d = stem_d);
    // Knob (rounded top)
    translate([hx, hy, plate[2] + stem_h])
        cylinder(h = knob_h, d1 = knob_d, d2 = knob_d * 0.7);
}

// --- Embossed text on front face ---
module label() {
    text_depth = 1.2;
    font_size = 5;

    for (i = [0 : len(label_lines) - 1]) {
        translate([plate[0] / 2, -text_depth + 0.01, plate[2] - 8 - (i * 8)])
            rotate([90, 0, 0])
                linear_extrude(height = text_depth + 0.1)
                    text(label_lines[i], size = font_size, halign = "center",
                         font = "Liberation Sans:style=Bold");
    }
}

// --- Assembly ---
difference() {
    union() {
        // Main block
        body();

        // Underside pads
        for (p = pads)
            pad(p[0], p[1], p[2], p[3]);

        // Registration hook
        hook();

        // Handle
        handle();
    }

    // Stud check holes with counterbores
    for (s = studs)
        stud_hole(s[0], s[1], s[2], plate[2]);

    // Embossed text (cut into front face)
    label();
}
