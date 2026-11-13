# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The statistics every dataset gets once imported, for its overview (backend-processing §22.7).

A person composes statistics from fixed choices (`definitions`); these are composed the same way,
so that the overview's are columns of the explorer like any other — filtered on, sorted on — and a
person composing the same choices gets the same column. They are what an overview of a dataset
counts and cannot read from a table as it is: how many objects, boxes and masks each record holds,
and the share of its image each object's box covers. What a table holds as it is — a record's
fields, an image's size, an object's class — the overview reads at once, without them.
"""

from __future__ import annotations

from .definitions import (
    BOX_ELEMENT,
    ENTITY_ELEMENT,
    MASK_ELEMENT,
    StatisticAggregation,
    StatisticChoices,
    StatisticLevel,
    StatisticMeasure,
)


#: The default statistics, in the order the overview shows them. A dataset gets those that apply to
#: it (`pixano.datasets.statistic_choices.default_statistics`): a dataset of masks counts no box.
DEFAULT_STATISTIC_CHOICES: tuple[StatisticChoices, ...] = (
    StatisticChoices(level=StatisticLevel.RECORD, element=ENTITY_ELEMENT, measure=StatisticMeasure.COUNT),
    StatisticChoices(level=StatisticLevel.RECORD, element=BOX_ELEMENT, measure=StatisticMeasure.COUNT),
    StatisticChoices(level=StatisticLevel.RECORD, element=MASK_ELEMENT, measure=StatisticMeasure.COUNT),
    # An object holds one box in most datasets: the mean of its boxes is that box.
    StatisticChoices(
        level=StatisticLevel.ENTITY,
        element=BOX_ELEMENT,
        measure=StatisticMeasure.IMAGE_RATIO,
        aggregation=StatisticAggregation.MEAN,
    ),
)
