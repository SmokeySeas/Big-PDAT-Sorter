$fn = 64;

module box_with_hole(width, depth, height, hole_diameter) {
    difference() {
        cube([width, depth, height], center=false);
        
        translate([(width/2)-hole_diameter/2, (depth/2)-hole_diameter/2, -1])
            cylinder(h=height+2, d=hole_diameter);
    }
}

box_with_hole(50, 30, 10, 8);