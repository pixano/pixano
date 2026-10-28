A `PUT` on a resource whose body carries another row's `id` is refused
with 400. It wrote the merged row over that other row, and answered 200.
