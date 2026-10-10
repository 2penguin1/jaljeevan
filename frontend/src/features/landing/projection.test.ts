import { BBOX, PLANE, project } from "./projection";

test("India's bounding box maps onto the edges of the relief plane", () => {
  const [x0, z0] = project(BBOX.lon0, BBOX.lat1); // north-west corner
  const [x1, z1] = project(BBOX.lon1, BBOX.lat0); // south-east corner
  expect(x0).toBeCloseTo(-PLANE.w / 2);
  expect(z0).toBeCloseTo(-PLANE.h / 2); // north is away from the camera (-z)
  expect(x1).toBeCloseTo(PLANE.w / 2);
  expect(z1).toBeCloseTo(PLANE.h / 2);
});

test("the centre of the box is the origin, and the plane keeps real proportions", () => {
  const [x, z] = project((BBOX.lon0 + BBOX.lon1) / 2, (BBOX.lat0 + BBOX.lat1) / 2);
  expect(Math.abs(x)).toBeLessThan(1e-9);
  expect(Math.abs(z)).toBeLessThan(1e-9);
  expect(PLANE.w).toBeCloseTo(1.799, 2); // same as the bake script reports
});
