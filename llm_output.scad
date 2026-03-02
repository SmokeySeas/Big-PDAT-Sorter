$fn = 64;

module centered_hole(x, y, d) {
    translate([x, y, -1]) cylinder(h=14, d=d);
}

difference() {
    cube([30, 45, 12], center=false);

    // Center of the box
    for (i = [-2.25, 2.25]) {
        centered_hole(15 + i, 22.5, 6);
        centered_hole(15 + i, 20.25, 4);
    }
}