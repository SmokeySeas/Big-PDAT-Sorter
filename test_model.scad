// model.scad
// Parametric demo part: a plate with 4 corner holes + optional rib

plate_x = 80;
plate_y = 50;
plate_z = 5;

hole_d = 5;
hole_edge = 8;     // distance from edge to hole center

rib_on = true;
rib_h = 10;
rib_t = 3;

module plate() {
  difference() {
    cube([plate_x, plate_y, plate_z], center=false);

    // 4 corner holes
    for (x = [hole_edge, plate_x - hole_edge])
      for (y = [hole_edge, plate_y - hole_edge])
        translate([x, y, -1])
          cylinder(h=plate_z + 2, d=hole_d, $fn=64);
  }
}

module rib() {
  // center rib along X axis
  translate([0, plate_y/2 - rib_t/2, plate_z])
    cube([plate_x, rib_t, rib_h], center=false);
}

union() {
  plate();
  if (rib_on) rib();
}