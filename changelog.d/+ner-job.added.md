`pixano-worker` recognizes named entities: the `ner` job sends each text of a dataset to a NER
model the inference serves, and writes each entity it recognizes as an object, its class in a text
field of the object — `category`, or `name` on an entity linking dataset —, and the text span that
mentions it, with the model's provenance. A rerun replaces what the same model wrote and keeps
another model's proposals; a mention over a span a person marked or edited is never proposed,
whatever its class. The spans show in the legacy app's entity linking workspace, and stay out of
the review queue: no interface reviews a text span yet.
