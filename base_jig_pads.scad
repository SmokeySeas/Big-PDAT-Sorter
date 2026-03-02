// base_jig_pads.scad
// expects in generated/jig_data.scad:
// plate = [plate_x, plate_y, plate_z]
// studs = [[x,y,d], ...]
// pads  = [[x,y,d,h], ...]  // underside standoffs

include <generated/jig_data.scad>;

$fn = 64;

module thru_hole(x,y,d,h){
  translate([x,y,-1]) cylinder(h=h+2, d=d);
}

module pad(x,y,d,h){
  // underside pad: extends downward from z=0
  translate([x,y,-h]) cylinder(h=h, d=d);
}

difference() {
  union() {
    // main plate
    cube([plate[0], plate[1], plate[2]], center=false);

    // underside pads
    for (p = pads) pad(p[0], p[1], p[2], p[3]);
  }

  // stud holes through plate
  for (s = studs) thru_hole(s[0], s[1], s[2], plate[2]);
}
