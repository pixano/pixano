# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a dataset keeps of the statistics it holds the values of (backend-processing §22).

A dataset keeps, for each statistic column of its tables, the statistic as it was composed when its
values were computed, the job that computed them last and when: what names a column and dates
it, whatever the library's statistic became since.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .definitions import StatisticDefinition


class ComputedStatistic(BaseModel):
    """A statistic a dataset holds the values of.

    Attributes:
        definition: The statistic as it was composed when its values were computed. Its name is
            the column of the dataset's table of its level.
        job_id: The job that computed them last.
        computed_at: When that job ended.
    """

    model_config = ConfigDict(frozen=True)

    definition: StatisticDefinition
    job_id: str
    computed_at: datetime
