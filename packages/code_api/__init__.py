import os
import logging

from .knowledge_base import KnowledgeBase

logging.basicConfig()
logger = logging.getLogger('CodeAPI:API')
logger.setLevel(
    logging.DEBUG if os.environ.get('DEBUG', '0').lower() in ['1', 'yes', 'true'] else logging.INFO
)