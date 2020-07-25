import logging

from code_api import logger
from code_api.knowledge_base import KnowledgeBase


class Job(object):

    def __init__(self, name):
        self._name = name
        self._logger = logging.getLogger(self._name)
        self._logger.setLevel(logger.level)
        # register job
        KnowledgeBase.set('jobs', name, self)

    @property
    def name(self):
        return self._name

    def is_time(self):
        raise NotImplementedError("The method 'Job.is_time' must be redefined by the subclass.")

    def step(self):
        pass
