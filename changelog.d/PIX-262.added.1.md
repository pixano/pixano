`pixano-worker` groups a dataset's records by their embeddings: the `clustering` job, with K-Means
into the number of groups asked, or HDBSCAN into as many as the embeddings hold, the records
between them in none. Groups are numbered by size, the largest first. Every run is kept beside the
others. It groups them by the embeddings of the model it names, or by the dataset's default ones;
a dataset holding none of that model's is refused when the job is planned.
