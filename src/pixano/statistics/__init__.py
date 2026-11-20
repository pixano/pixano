# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Statistics computed per record or per object from a dataset's annotations (backend-processing §22).

Import from the modules: `definitions` for what a statistic is made of, `compute` for its values,
`registry` for the library's statistics. They depend on the schemas alone: the datasets, which keep
what they computed, import them, and what a dataset offers to compose from is the datasets' own
(`pixano.datasets.statistic_choices`).
"""
