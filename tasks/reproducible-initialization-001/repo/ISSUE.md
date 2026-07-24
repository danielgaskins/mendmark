# A seeded training run changes unrelated randomness and input order

`initialize_centroids` calls the module-level random generator and shuffles the
training points in place. A reproducible model component must not alter its caller
or contaminate randomness used elsewhere in the process.

Repair it so that:

- The same points, `k`, and seed produce the same centroids.
- Different seeds can produce different selections.
- Input order and values are not mutated.
- Module-level `random` state is not read or changed.
- Selected centroids are distinct by value.
- `k` must be positive and cannot exceed the number of distinct points.
- Returned points are independent lists, not aliases into the input.

Do not add third-party dependencies.

